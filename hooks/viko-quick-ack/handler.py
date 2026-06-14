import json
import urllib.request

# Keywords that indicate a complex task worth sending an ack for
COMPLEX_KEYWORDS = [
    # Task actions
    "plan", "develop", "deploy", "implement", "build", "analyze", "analyse",
    "review", "investigate", "debug", "fix", "refactor", "migrate", "create",
    "lanjutkan", "kerjakan", "buat", "analisa", "investigasi", "perbaiki",
    "selesaikan", "jalankan", "eksekusi",
    # Viko-specific
    "superpower", "subagent", "agent", "kanban", "tiket", "approve",
    # Long compound requests (contains "dan" = "and" suggesting multi-step)
    " dan ", " lalu ", " kemudian ",
]


async def handle(event_type, context):
    if event_type != "agent:start":
        return

    if context.get("platform") != "whatsapp":
        return

    chat_id = context.get("chat_id", "").strip()
    if not chat_id:
        return

    msg = (context.get("message") or "").lower()
    if not any(kw in msg for kw in COMPLEX_KEYWORDS):
        return

    payload = json.dumps({
        "chatId": chat_id,
        "message": "Mohon ditunggu sebentar... 🔄",
    }).encode()
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:3000/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass
