"""Deterministic safety-net for outbound files.

The model sometimes claims it "sent / attached" a file (a screenshot, PDF, video,
report) but forgets to emit the `MEDIA:<path>` tag, so nothing is actually delivered.
On agent:end, if the reply claims a file was sent but contains NO `MEDIA:` tag, find
the file the agent just produced (a deliverable created within this turn) and send it
via the bridge. This only RECOVERS a real, freshly-made file — it never invents one,
so if the agent didn't actually produce anything, nothing is sent.
"""
import asyncio
import json
import os
import re
import time
import urllib.request

# The reply claims a file went out (Indonesian + English).
_CLAIM_RE = re.compile(
    r'(screenshot|gambar|foto|file|pdf|dokumen|docx|video|mp4|excel|xlsx|laporan|quotation|report)'
    r'[\s\S]{0,40}(di ?kirim|terkirim|ke ?attach|ter ?attach|sudah dikirim|udah dikirim|sent|delivered|ke group|ke sini)'
    r'|(di ?kirim|terkirim|sent|attached?|share)[\s\S]{0,40}'
    r'(screenshot|gambar|foto|file|pdf|dokumen|video|laporan|report)',
    re.IGNORECASE,
)

_DELIVERABLE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx",
                    ".xlsx", ".pptx", ".mp4", ".csv"}
_MAX_AGE = 180  # only a file produced in this turn (seconds)


def _home():
    return os.environ.get("HOME") or "/opt/data/home"


def _search_dirs():
    home = _home()
    dirs = [
        "/opt/data/cache/screenshots",
        os.path.join(home, ".hermes", "document_cache"),
        os.path.join(home, ".hermes", "image_cache"),
        "/opt/data/browser_recordings",
        os.path.join(home, ".hermes", "browser_recordings"),
        "/tmp",
    ]
    root = os.environ.get("VIKO_PROJECTS_ROOT")
    slug = os.environ.get("VIKO_PROJECT_SLUG")
    if root and slug:
        dirs.append(os.path.join(root, slug, "docs"))
    return dirs


def _recent_deliverable():
    now = time.time()
    best, best_mt = None, 0.0
    for d in _search_dirs():
        if not os.path.isdir(d):
            continue
        for dirpath, dirnames, files in os.walk(d):
            dirnames[:] = [x for x in dirnames
                           if x not in (".git", "node_modules", ".venv", "__pycache__")]
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in _DELIVERABLE_EXT:
                    continue
                if fn.startswith("outbox_"):  # our own temp send artifacts
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    mt = os.path.getmtime(fp)
                except OSError:
                    continue
                if (now - mt) <= _MAX_AGE and mt > best_mt:
                    best, best_mt = fp, mt
    return best


def _autosend(chat_id):
    fp = _recent_deliverable()
    if not fp:
        return
    payload = json.dumps({
        "chatId": chat_id,
        "filePath": fp,
        "fileName": os.path.basename(fp),
    }).encode()
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:3000/send-media",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=25)
        print(f"[viko-media-autosend] recovered + sent {fp}", flush=True)
    except Exception as e:
        print(f"[viko-media-autosend] failed: {e}", flush=True)


async def handle(event_type, context):
    if event_type != "agent:end" or context.get("platform") != "whatsapp":
        return
    chat_id = (context.get("chat_id") or "").strip()
    resp = context.get("response") or ""
    if not chat_id or not resp:
        return
    if "MEDIA:" in resp:        # the agent delivered it correctly
        return
    if not _CLAIM_RE.search(resp):
        return
    await asyncio.get_running_loop().run_in_executor(None, _autosend, chat_id)
