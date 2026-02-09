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

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

TARGET = "WeLeakInfo_BOT"          # ← change if needed

API_ID = 32506403
API_HASH = "ab7c68b910b929608adc731023d0cf97"

SESSION_STRING = os.getenv("SESSION_STRING")

# Use Desktop folder — usually has fewer permission issues
DOWNLOAD_DIR = Path.home() / "Desktop" / "BotFiles"
DOWNLOAD_DIR.mkdir(exist_ok=True)

client = None
recent_messages = []

@app.on_event("startup")
async def startup():
    global client

    if not SESSION_STRING:
        print("!!! NO SESSION_STRING IN .env !!!")
        return

    try:
        client = Client(
            "my_account",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING
        )
        await client.start()
        print("Telegram client started ✓")
        print(f"Proxy active for chat: @{TARGET}")
        print(f"Files will be saved to: {DOWNLOAD_DIR}")

        @client.on_message(filters.chat(TARGET))
        async def handle_message(c, message):
            global recent_messages

            sender = "You" if message.outgoing else "Bot"
            time_str = message.date.strftime("%Y-%m-%d %H:%M:%S")
            text = message.text or message.caption or "[No text]"
            file_saved = None

            # AUTO-CLICK BUTTONS
            if message.reply_markup and message.reply_markup.inline_keyboard:
                for row_idx, row in enumerate(message.reply_markup.inline_keyboard):
                    for col_idx, btn in enumerate(row):
                        btn_text = (btn.text or "").lower()
                        if any(word in btn_text for word in ["download", "export", "get file", "save", "txt", "html", "data"]):
                            print(f"\n>>> Found button: {btn.text} (row {row_idx}, col {col_idx})")
                            try:
                                await message.click(btn.text)
                                print("    → clicked successfully")
                            except Exception as e:
                                print(f"    click failed: {e}")

            # HANDLE DOCUMENT
            if message.document:
                orig_name = message.document.file_name or f"file_{message.id}"
                mime = message.document.mime_type or ""
                size_kb = message.document.file_size / 1024 if message.document.file_size else 0

                print(f"Bot sent document: {orig_name} | size: {size_kb:.1f} KB | mime: {mime}")

                save_name = f"downloaded_{message.id}.html" if "text" in mime.lower() or "html" in mime.lower() or orig_name.lower().endswith((".txt",".html")) else orig_name

                file_path = DOWNLOAD_DIR / save_name

                print(f"Trying to download to: {file_path}")

                try:
                    # First try memory download (more reliable in many cases)
                    file_obj = await message.download(in_memory=True)
                    if file_obj and isinstance(file_obj, BytesIO):
                        file_bytes = file_obj.getvalue()
                        print(f"Memory download OK: {len(file_bytes):,} bytes")

                        # Then save to disk
                        file_path.write_bytes(file_bytes)
                        if file_path.exists():
                            file_saved = file_path.name
                            text += f"\n[FILE SAVED: {file_saved}] ({len(file_bytes)/1024:.1f} KB)"
                            print(f"Successfully saved to disk → {file_path}")
                        else:
                            text += "\n[Memory OK but disk write failed]"
                            print("Disk write failed after memory download")
                    else:
                        text += "\n[Download returned no data]"
                        print("message.download(in_memory=True) returned None or wrong type")
                except Exception as e:
                    text += f"\n[Download error: {str(e)}]"
                    print(f"Download exception: {type(e).__name__}: {str(e)}")

            # SAVE TO HISTORY
            recent_messages.append({
                "sender": sender,
                "text": text,
                "time": time_str,
                "file_path": file_saved   # only filename or None
            })

            print(f"[{time_str}] {sender}: {text[:120]}{'...' if len(text)>120 else ''}")

            if len(recent_messages) > 1000:
                recent_messages[:] = recent_messages[-1000:]

    except Exception as e:
        print(f"Startup failed: {str(e)}")


# ──────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    html_path = "index.html"
    if not os.path.exists(html_path):
        return "<h1>index.html not found!</h1>"
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/send")
async def send(text: str = Form(...)):
    if not client:
        raise HTTPException(500, "Telegram client not started")
    try:
        await client.send_message(TARGET, text)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/messages")
async def get_messages():
    return {"messages": recent_messages}


@app.get("/file/{filename}")
async def get_file(filename: str):
    file_path = DOWNLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found on server")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"  # force download
    )


print("Run with:   py -3.11 -m uvicorn main:app --reload")
print("Open:       http://127.0.0.1:8000")
print(f"Files saved to: {DOWNLOAD_DIR}")