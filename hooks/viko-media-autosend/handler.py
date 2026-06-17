"""Deterministic safety-net for outbound files.

The model sometimes finishes a turn claiming it "sent" a file (a screenshot, PDF,
video, report) but never emits the `MEDIA:<path>` tag — so nothing is delivered, and
it often pastes the file path into the reply ("file tersimpan di /opt/.../x.png",
"download via path itu") or falsely claims "WhatsApp can't attach media".

On agent:end, if the reply has NO `MEDIA:` tag, recover the file two ways:
  1. Any deliverable file PATH the model pasted into its reply that exists on disk.
  2. Fallback: if it claims it sent something but pasted no path, the most recent
     deliverable produced this turn.
It only ever sends a real file that already exists — it never invents one.
"""
import asyncio
import json
import os
import re
import time
import urllib.request

# Absolute paths to deliverable files mentioned in the reply (gif excluded — bridge
# rejects it). Tolerant of a trailing ``.`` / ``)`` etc. via the explicit char class.
_PATH_RE = re.compile(
    r'(/[A-Za-z0-9._/\-]+\.(?:png|jpe?g|webp|pdf|docx?|xlsx?|pptx?|mp4|mov|m4a|ogg|csv))',
    re.IGNORECASE,
)

# Reply claims a file went out (Indonesian + English) — used only for the fallback.
_CLAIM_RE = re.compile(
    r'(screenshot|gambar|foto|file|pdf|dokumen|docx|video|mp4|excel|xlsx|laporan|report|quotation)'
    r'[\s\S]{0,40}(di ?kirim|terkirim|ke ?attach|sudah dikirim|udah dikirim|sent|delivered|ke group|ke sini|tersimpan|download)'
    r'|(di ?kirim|terkirim|sent|attached?|share)[\s\S]{0,40}'
    r'(screenshot|gambar|foto|file|pdf|dokumen|video|laporan|report)',
    re.IGNORECASE,
)

_DELIVERABLE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".doc",
                    ".xlsx", ".xls", ".pptx", ".mp4", ".mov", ".m4a", ".ogg", ".csv"}
_MAX_AGE = 180  # fallback: only a file produced this turn (seconds)


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


def _autosend(chat_id, paths):
    for fp in paths:
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
            print(f"[viko-media-autosend] failed for {fp}: {e}", flush=True)


async def handle(event_type, context):
    if event_type != "agent:end" or context.get("platform") != "whatsapp":
        return
    chat_id = (context.get("chat_id") or "").strip()
    resp = context.get("response") or ""
    if not chat_id or not resp:
        return
    if "MEDIA:" in resp:            # the agent delivered it correctly
        return

    paths = []
    for m in _PATH_RE.findall(resp):
        if m not in paths and os.path.isfile(m):
            paths.append(m)
    if not paths and _CLAIM_RE.search(resp):
        f = _recent_deliverable()
        if f:
            paths.append(f)
    if not paths:
        return
    await asyncio.get_running_loop().run_in_executor(None, _autosend, chat_id, paths[:3])
