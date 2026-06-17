"""Deterministic safety-net for outbound files.

The gateway's normal `MEDIA:<path>` delivery is occasionally skipped (long / multi-part
replies), and the model sometimes pastes the file path or claims it "sent" something
without a working tag — so the user gets no attachment. On agent:end, recover the file:
  1. paths inside any `MEDIA:` tag still in the reply,
  2. deliverable file paths pasted in prose,
  3. fallback: if it claimed/intended to send but no valid path resolved, the freshest
     deliverable produced this turn.
Every send goes through the bridge, which de-dups (same chat+name+size), so a file the
gateway already delivered is never sent twice. It only ever sends a real file on disk.
"""
import asyncio
import os
import re
import time
import json
import urllib.request

_MEDIA_TAG_RE = re.compile(r'MEDIA:\s*([^\s\]\)]+)', re.IGNORECASE)
_PATH_RE = re.compile(
    r'(/[A-Za-z0-9._/\-]+\.(?:png|jpe?g|webp|pdf|docx?|xlsx?|pptx?|mp4|mov|m4a|ogg|csv))',
    re.IGNORECASE,
)
_CLAIM_RE = re.compile(
    r'(screenshot|gambar|foto|file|pdf|dokumen|docx|video|mp4|excel|xlsx|laporan|report|quotation)'
    r'[\s\S]{0,40}(di ?kirim|terkirim|ke ?attach|sudah dikirim|udah dikirim|sent|delivered|ke group|ke sini|tersimpan|download)'
    r'|(di ?kirim|terkirim|sent|attached?|share)[\s\S]{0,40}'
    r'(screenshot|gambar|foto|file|pdf|dokumen|video|laporan|report)',
    re.IGNORECASE,
)

_DELIVERABLE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".doc",
                    ".xlsx", ".xls", ".pptx", ".mp4", ".mov", ".m4a", ".ogg", ".csv"}
_MAX_AGE = 180


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
                if fn.startswith("outbox_"):
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
        body = json.dumps({
            "chatId": chat_id,
            "filePath": fp,
            "fileName": os.path.basename(fp),
        }).encode()
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3000/send-media",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=25)
            print(f"[viko-media-autosend] sent {fp}", flush=True)
        except Exception as e:
            print(f"[viko-media-autosend] failed for {fp}: {e}", flush=True)


async def handle(event_type, context):
    if event_type != "agent:end" or context.get("platform") != "whatsapp":
        return
    chat_id = (context.get("chat_id") or "").strip()
    resp = context.get("response") or ""
    if not chat_id or not resp:
        return

    paths = []
    saw_intent = False
    for p in _MEDIA_TAG_RE.findall(resp):
        saw_intent = True
        p = p.rstrip(".,;:)]}>\"'")
        if os.path.isfile(p) and p not in paths:
            paths.append(p)
    for m in _PATH_RE.findall(resp):
        if os.path.isfile(m) and m not in paths:
            paths.append(m)
    if not paths and (saw_intent or _CLAIM_RE.search(resp)):
        f = _recent_deliverable()
        if f:
            paths.append(f)
    if not paths:
        return
    await asyncio.get_running_loop().run_in_executor(None, _autosend, chat_id, paths[:3])
