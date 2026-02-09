from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pyrogram import Client, filters
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from io import BytesIO
import os

# Load .env locally (Railway ignores this, it's fine)
load_dotenv()

app = FastAPI()

# ───────────────── CONFIG ─────────────────

TARGET = "WeLeakInfo_BOT"

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

DOWNLOAD_DIR = Path.home() / "BotFiles"
DOWNLOAD_DIR.mkdir(exist_ok=True)

client = None
recent_messages = []

# ─────────────── STARTUP ───────────────

@app.on_event("startup")
async def startup():
    global client

    if not API_ID or not API_HASH or not SESSION_STRING:
        print("❌ Missing environment variables")
        return

    client = Client(
        "my_account",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )

    await client.start()
    print("✅ Telegram client started")

    @client.on_message(filters.chat(TARGET))
    async def handle_message(c, message):
        global recent_messages

        sender = "You" if message.outgoing else "Bot"
        time_str = message.date.strftime("%Y-%m-%d %H:%M:%S")
        text = message.text or message.caption or "[No text]"
        file_saved = None

        # Handle documents
        if message.document:
            file_obj = await message.download(in_memory=True)
            if file_obj:
                file_path = DOWNLOAD_DIR / message.document.file_name
                file_path.write_bytes(file_obj.getvalue())
                file_saved = file_path.name
                text += f"\n[FILE SAVED: {file_saved}]"

        recent_messages.append({
            "sender": sender,
            "text": text,
            "time": time_str,
            "file_path": file_saved
        })

        recent_messages[:] = recent_messages[-1000:]

# ─────────────── ROUTES ───────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h1>Backend running</h1>"

@app.post("/send")
async def send(text: str = Form(...)):
    if not client:
        raise HTTPException(500, "Client not ready")
    await client.send_message(TARGET, text)
    return {"status": "ok"}

@app.get("/messages")
async def messages():
    return {"messages": recent_messages}

@app.get("/file/{filename}")
async def file(filename: str):
    file_path = DOWNLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404)
    return FileResponse(file_path)

# ─────────────── RUN (BOTTOM ONLY) ───────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
