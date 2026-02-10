from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from pyrogram import Client, filters
import os
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from io import BytesIO

# Load .env only if running locally (on Render/Railway we use dashboard env vars)
load_dotenv()  # safe to call even if no .env file exists

app = FastAPI()

# ──────────────────────────────────────────────
# CONFIG – ALL SECRETS COME FROM ENVIRONMENT VARIABLES
# ──────────────────────────────────────────────
TARGET = "WeLeakInfo_BOT"  # the bot username you're interacting with

# These MUST be set in Render/Railway dashboard → Environment Variables
API_ID = int(os.getenv("API_ID") or "0")                # will crash if missing → good for catching errors
API_HASH = os.getenv("API_HASH") or ""
SESSION_STRING = os.getenv("SESSION_STRING") or ""

# Use /tmp on Render/Railway (ephemeral filesystem – files disappear on restart/sleep)
DOWNLOAD_DIR = Path("/tmp") / "BotFiles"
DOWNLOAD_DIR.mkdir(exist_ok=True)

client = None
recent_messages = []  # in-memory message history (lost on restart – fine for this use-case)

# ──────────────────────────────────────────────
# STARTUP – Initialize Pyrogram client
# ──────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global client

    if not API_ID or not API_HASH or not SESSION_STRING:
        print("ERROR: Missing required environment variables!")
        print("Please set in Render/Railway dashboard:")
        print("  API_ID         (your Telegram API ID)")
        print("  API_HASH       (your Telegram API hash)")
        print("  SESSION_STRING (your Pyrogram session string)")
        return

    try:
        client = Client(
            name="tomar_osint_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING
        )

        await client.start()
        print("Telegram client started successfully ✓")
        print(f"Connected to target: @{TARGET}")
        print(f"Downloaded files will be saved temporarily to: {DOWNLOAD_DIR}")

        # ──────────────────────────────────────────────
        # MESSAGE HANDLER – only messages from the target bot
        # ──────────────────────────────────────────────
        @client.on_message(filters.chat(TARGET))
        async def handle_message(c: Client, message):
            global recent_messages

            sender = "You" if message.outgoing else "Bot"
            time_str = message.date.strftime("%Y-%m-%d %H:%M:%S")
            text = message.text or message.caption or "[No text/content]"
            file_saved = None

            # Auto-click useful buttons (download/export/get file/etc.)
            if message.reply_markup and message.reply_markup.inline_keyboard:
                for row in message.reply_markup.inline_keyboard:
                    for btn in row:
                        btn_text = (btn.text or "").lower()
                        if any(word in btn_text for word in ["download", "export", "get file", "save", "txt", "html", "data"]):
                            print(f"Found clickable button: {btn.text}")
                            try:
                                await message.click(btn.text)
                                print("→ Button clicked successfully")
                            except Exception as e:
                                print(f"Button click failed: {e}")

            # Handle documents/files sent by the bot
            if message.document:
                orig_name = message.document.file_name or f"file_{message.id}"
                mime = message.document.mime_type or ""
                size_kb = message.document.file_size / 1024 if message.document.file_size else 0
                print(f"Received document: {orig_name} | {size_kb:.1f} KB | mime: {mime}")

                # Choose filename (prefer .html/.txt for text content)
                save_name = (
                    f"downloaded_{message.id}.html"
                    if "text" in mime.lower() or "html" in mime.lower() or orig_name.lower().endswith((".txt", ".html", ".json"))
                    else orig_name
                )
                file_path = DOWNLOAD_DIR / save_name

                try:
                    # Download to memory first (safer on free tier)
                    file_obj = await message.download(in_memory=True)
                    if file_obj and isinstance(file_obj, BytesIO):
                        file_bytes = file_obj.getvalue()
                        if len(file_bytes) == 0:
                            text += "\n[Downloaded file is empty - 0 bytes]"
                            print("Downloaded file is empty (0 bytes)")
                        else:
                            file_path.write_bytes(file_bytes)
                            # Double-check existence and size after write
                            if file_path.exists() and file_path.stat().st_size > 0:
                                file_saved = file_path.name
                                text += f"\n\n[FILE SAVED: {file_saved}] ({len(file_bytes)/1024:.1f} KB)"
                                print(f"File saved OK: {file_path} | size: {file_path.stat().st_size} bytes")
                            else:
                                text += "\n[File write succeeded but file not found or empty on disk]"
                                print(f"Write OK but exists() or size check failed: {file_path}")
                    else:
                        text += "\n[Download returned empty/invalid object]"
                        print("message.download(in_memory=True) returned None or invalid")
                except Exception as e:
                    text += f"\n[File download/save failed: {str(e)}]"
                    print(f"File handling error: {type(e).__name__}: {str(e)}")

            # Store in memory (for frontend to display)
            recent_messages.append({
                "sender": sender,
                "text": text,
                "time": time_str,
                "file_path": file_saved
            })

            # Keep only last 1000 messages (memory safety)
            if len(recent_messages) > 1000:
                recent_messages[:] = recent_messages[-1000:]

            print(f"[{time_str}] {sender}: {text[:120]}{'...' if len(text)>120 else ''}")

    except Exception as e:
        print(f"Startup / client error: {str(e)}")


# ──────────────────────────────────────────────
# FASTAPI ROUTES
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error: index.html not found in project root</h1>"


@app.post("/send")
async def send(text: str = Form(...)):
    if not client:
        raise HTTPException(500, "Telegram client not initialized")
    try:
        await client.send_message(TARGET, text)
        return {"status": "sent"}
    except Exception as e:
        raise HTTPException(500, f"Send failed: {str(e)}")


@app.get("/messages")
async def get_messages():
    return {"messages": recent_messages}


@app.get("/file/{filename}")
async def get_file(filename: str):
    file_path = DOWNLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found (files are temporary on free hosting)")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


# NEW: Endpoint to allow frontend to clear server-side message history
@app.post("/clear")
async def clear_history():
    global recent_messages
    old_count = len(recent_messages)
    recent_messages = []
    print(f"[CLEAR REQUEST] Server history wiped – removed {old_count} messages")
    return {"status": "cleared", "removed": old_count}


# Optional: health check endpoint (useful for cron pings)
@app.get("/health")
async def health():
    return {"status": "ok", "client_running": bool(client)}
