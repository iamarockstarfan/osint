from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from pyrogram import Client, filters
import os
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from io import BytesIO

load_dotenv()

app = FastAPI()

TARGET = "WeLeakInfo_BOT"

API_ID = int(os.getenv("API_ID") or "0")
API_HASH = os.getenv("API_HASH") or ""
SESSION_STRING = os.getenv("SESSION_STRING") or ""

DOWNLOAD_DIR = Path("/tmp") / "BotFiles"
DOWNLOAD_DIR.mkdir(exist_ok=True)

client = None
recent_messages = []

@app.on_event("startup")
async def startup():
    global client
    if not API_ID or not API_HASH or not SESSION_STRING:
        print("ERROR: Missing required environment variables!")
        print("Please set in Render dashboard:")
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

        @client.on_message(filters.chat(TARGET))
        async def handle_message(c: Client, message):
            global recent_messages
            sender = "You" if message.outgoing else "Bot"
            time_str = message.date.strftime("%Y-%m-%d %H:%M:%S")
            text = message.text or message.caption or "[No text/content]"
            file_saved = None

            # Auto-click buttons...
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

            # Handle documents...
            if message.document:
                # ... (your existing file handling code remains unchanged)
                pass  # shortened for brevity – keep your full code here

            recent_messages.append({
                "sender": sender,
                "text": text,
                "time": time_str,
                "file_path": file_saved
            })

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

# NEW: Clear history endpoint
@app.post("/clear")
async def clear_history():
    global recent_messages
    old_count = len(recent_messages)
    recent_messages = []
    print(f"[CLEAR] History cleared – removed {old_count} messages")
    return {"status": "cleared", "removed": old_count}

@app.get("/health")
async def health():
    return {"status": "ok", "client_running": bool(client)}
