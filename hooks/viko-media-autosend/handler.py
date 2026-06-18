"""Deterministic safety-net for outbound files (incl. browser-test videos).

The gateway's normal `MEDIA:<path>` delivery is occasionally skipped (long / multi-part
replies), and the model sometimes pastes the file path or claims it "sent" something
without a working tag — so the user gets no attachment. On agent:end, recover the file:
  1. paths inside any `MEDIA:` tag still in the reply,
  2. deliverable file paths pasted in prose,
  3. video: if the reply signals a recording/video and a fresh browser recording exists
     (record_sessions auto-records to browser_recordings/*.webm), convert the freshest
     webm to mp4 and send it — the model doesn't have to drive recording or convert,
  4. fallback: if it claimed/intended to send but no valid path resolved, the freshest
     deliverable produced this turn.
Every send goes through the bridge, which de-dups (same chat+name+size), so a file the
gateway already delivered is never sent twice. It only ever sends a real file on disk.
"""
import asyncio
import os
import re
import time
import json
import subprocess
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
# A reply that simply *presents* a deliverable — "ini screenshot-nya 👇", "berikut
# laporannya" — without a "sent/delivered" verb or a MEDIA: tag. The common case the
# model gets wrong. Only ever acts together with _recent_deliverable's <=180s freshness
# guard, so it just ships the file produced THIS turn, never a stale one.
_PRESENT_RE = re.compile(
    r'\b(?:screenshot|tangkapan\s*layar|gambar|foto|image|pdf|dokumen|docx|excel|xlsx|'
    r'spreadsheet|laporan|report|quotation|invoice|video|rekaman|grafik|chart|diagram)'
    r'(?:nya|ku|mu)?\b',  # allow clitics: screenshotnya / laporannya / gambarku
    re.IGNORECASE,
)
# A reply that talks about a recording/video — trigger for the webm->mp4 path. Pairs
# with the fresh-webm guard below, so a stray "video" with no recent recording is a no-op.
_VIDEO_INTENT_RE = re.compile(
    r'\b(?:video|rekam(?:an)?|kerekam|recording|recorded|record|mp4|tayangan|cuplikan)'
    r'(?:nya|ku|mu)?\b',  # allow Indonesian clitics: videonya / rekamannya / videoku
    re.IGNORECASE,
)

_DELIVERABLE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".doc",
                    ".xlsx", ".xls", ".pptx", ".mp4", ".mov", ".m4a", ".ogg", ".csv"}
_VIDEO_EXT = {".mp4", ".mov"}
_MAX_AGE = 180
_MAX_AGE_RESEND = 86400  # 24 h — resend scenarios reference files from earlier in the session
_WEBM_MAX_AGE = 300  # a browser test can run a few minutes before `browser close` finalizes it

# "kirim ulang / kirim lagi / resend" — user is asking Viko to resend a previously-delivered file
_RESEND_RE = re.compile(r'kirim\s*(?:ulang|lagi)\b|resend\b', re.IGNORECASE)


def _home():
    return os.environ.get("HOME") or "/opt/data/home"


def _recording_dirs():
    home = _home()
    return [
        "/opt/data/browser_recordings",
        os.path.join(home, ".hermes", "browser_recordings"),
        os.path.join(home, "browser_recordings"),
    ]


def _search_dirs():
    home = _home()
    dirs = [
        "/opt/data/cache/screenshots",
        os.path.join(home, ".hermes", "document_cache"),
        os.path.join(home, ".hermes", "image_cache"),
        "/tmp",
    ] + _recording_dirs()
    root = os.environ.get("VIKO_PROJECTS_ROOT")
    slug = os.environ.get("VIKO_PROJECT_SLUG")
    if root and slug:
        dirs.append(os.path.join(root, slug, "docs"))
    return dirs


def _recent_deliverable(max_age=_MAX_AGE):
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
                if (now - mt) <= max_age and mt > best_mt:
                    best, best_mt = fp, mt
    return best


def _recent_webm():
    """Freshest browser recording (.webm) produced this turn, or None."""
    now = time.time()
    best, best_mt = None, 0.0
    for d in _recording_dirs():
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.lower().endswith(".webm"):
                continue
            fp = os.path.join(d, fn)
            try:
                mt = os.path.getmtime(fp)
            except OSError:
                continue
            if (now - mt) <= _WEBM_MAX_AGE and mt > best_mt:
                best, best_mt = fp, mt
    return best


def _webm_to_mp4(webm):
    """Transcode a browser recording to a WhatsApp-friendly mp4. Best-effort."""
    base = os.path.splitext(os.path.basename(webm))[0]
    out = os.path.join("/tmp", "viko_vid_" + base + ".mp4")
    try:
        if os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(webm):
            return out  # already transcoded this recording
    except OSError:
        pass
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", webm, "-c:v", "libx264", "-preset", "fast",
             "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
            check=True, capture_output=True, timeout=180,
        )
    except Exception as e:
        print(f"[viko-media-autosend] ffmpeg webm->mp4 failed: {e}", flush=True)
        return None
    return out if (os.path.isfile(out) and os.path.getsize(out) > 0) else None


def _autosend(chat_id, paths):
    for fp in paths:
        payload = {"chatId": chat_id, "filePath": fp, "fileName": os.path.basename(fp)}
        if os.path.splitext(fp)[1].lower() in _VIDEO_EXT:
            payload["mediaType"] = "video"
        body = json.dumps(payload).encode()
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3000/send-media",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=60)
            print(f"[viko-media-autosend] sent {fp}", flush=True)
        except Exception as e:
            print(f"[viko-media-autosend] failed for {fp}: {e}", flush=True)


def _resolve_and_send(chat_id, resp):
    """Resolve every deliverable the reply references and send it. Runs off the event
    loop (does disk walks + ffmpeg)."""
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

    # Video: auto-convert the freshest recording when the reply signals one and no
    # video file was already resolved from the tag/prose.
    if _VIDEO_INTENT_RE.search(resp) and not any(
        os.path.splitext(p)[1].lower() in _VIDEO_EXT for p in paths
    ):
        webm = _recent_webm()
        if webm:
            mp4 = _webm_to_mp4(webm)
            if mp4 and mp4 not in paths:
                paths.append(mp4)

    is_resend = bool(_RESEND_RE.search(resp))
    if not paths and (saw_intent or is_resend or _CLAIM_RE.search(resp) or _PRESENT_RE.search(resp)):
        max_age = _MAX_AGE_RESEND if is_resend else _MAX_AGE
        f = _recent_deliverable(max_age=max_age)
        if f:
            paths.append(f)
    if not paths:
        return
    _autosend(chat_id, paths[:3])


async def handle(event_type, context):
    if event_type != "agent:end" or context.get("platform") != "whatsapp":
        return
    chat_id = (context.get("chat_id") or "").strip()
    resp = context.get("response") or ""
    if not chat_id or not resp:
        return
    await asyncio.get_running_loop().run_in_executor(None, _resolve_and_send, chat_id, resp)
