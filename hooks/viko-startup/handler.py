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
    payload = json.dumps({"chatId": home_channel, "message": message}).encode()

    # Retry until the bridge is up (bridge can take up to 30s after gateway:startup)
    for attempt in range(12):
        await asyncio.sleep(5)
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3000/send",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            return
        except Exception:
            continue
