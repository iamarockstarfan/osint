from pyrogram import Client
import asyncio

# Your real API credentials (already filled)
API_ID = 32506403
API_HASH = "ab7c68b910b929608adc731023d0cf97"

# Session name — can be anything (used for local storage, but we export string anyway)
app = Client("my_temp_session", api_id=API_ID, api_hash=API_HASH)

async def main():
    print("Starting Pyrogram client...")
    await app.start()
    
    print("Client started! If prompted, enter your phone number and code.")
    
    # Export the session as a string (this is what we need for .env)
    session_string = await app.export_session_string()
    
    print("\n" + "=" * 80)
    print("YOUR SESSION STRING (COPY EVERYTHING BELOW THIS LINE):")
    print(session_string)
    print("=" * 80)
    print("\nSAVE THIS STRING SECURELY! Paste it into your .env file like:")
    print("SESSION_STRING=" + session_string)
    print("\nAfter saving, press Ctrl+C to exit or just close the window.")
    
    # Optional: stop the client cleanly
    await app.stop()

# Run the async function
asyncio.run(main())