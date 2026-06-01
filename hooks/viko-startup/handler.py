import asyncio
import os
import urllib.request
import json


async def handle(event_type, context):
    if event_type != "gateway:startup":
        return

    home_channel = os.getenv("WHATSAPP_HOME_CHANNEL", "").strip()
    if not home_channel:
        return

    message = "Online lagi! Siap nerima perintah 🟢"

    # Wait a moment for the bridge to be fully ready
    await asyncio.sleep(3)

    try:
        payload = json.dumps({"chatId": home_channel, "message": message}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:3000/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass
