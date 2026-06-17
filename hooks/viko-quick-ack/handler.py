"""Deferred WhatsApp "working on it" ack.

The old version guessed from keywords whether a message was "complex" and acked
immediately — which misfired on ordinary Indonesian chat ("dan", "buat", "agent",
"approve", ...). Instead, schedule the ack on ``agent:start`` and CANCEL it on
``agent:end``. Fast replies finish before the delay and stay silent; only
genuinely slow turns (tools, long generation) ever announce a wait.

Tune with env vars:
  VIKO_ACK_DELAY_SECONDS  — how long a turn must run before we announce (default 4)
  VIKO_ACK_TEXT           — the message text
"""
import asyncio
import json
import os
import urllib.request

_DELAY = float(os.environ.get("VIKO_ACK_DELAY_SECONDS", "4"))
_ACK_TEXT = os.environ.get("VIKO_ACK_TEXT", "Sebentar ya, lagi saya kerjain... 🔄")

# chat_id -> scheduled (not-yet-sent) ack task
_pending: dict = {}


def _post_ack(chat_id: str) -> None:
    payload = json.dumps({"chatId": chat_id, "message": _ACK_TEXT}).encode()
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


async def _deferred_ack(chat_id: str) -> None:
    try:
        await asyncio.sleep(_DELAY)
    except asyncio.CancelledError:
        return  # reply landed before the delay → stay quiet
    try:
        # urlopen blocks; keep it off the event loop
        await asyncio.get_running_loop().run_in_executor(None, _post_ack, chat_id)
    finally:
        _pending.pop(chat_id, None)


async def handle(event_type, context):
    if context.get("platform") != "whatsapp":
        return
    chat_id = (context.get("chat_id") or "").strip()
    if not chat_id:
        return

    if event_type == "agent:start":
        prev = _pending.pop(chat_id, None)
        if prev and not prev.done():
            prev.cancel()
        _pending[chat_id] = asyncio.create_task(_deferred_ack(chat_id))
    elif event_type == "agent:end":
        task = _pending.pop(chat_id, None)
        if task and not task.done():
            task.cancel()
