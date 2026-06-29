"""Detect commitment language in agent replies and store to commitments.json.

Fires on agent:end. Uses simple pattern matching first; skips LLM call for speed.
Commitment patterns (Indonesian + English): "besok", "nanti", "follow up", etc.
"""
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_COMMITMENT_PATTERNS = re.compile(
    r"\b(?:"
    r"besok|lusa|minggu depan|bulan depan|nanti|sebentar|ntar|"
    r"follow.?up|tindak lanjut|follow up|cek lagi|dicek|check back|"
    r"akan (?:saya|ku|kita|aku)|saya akan|aku akan|kita akan|"
    r"remind|ingatkan|pengingat|reminder|"
    r"setelah deploy|setelah selesai|after deploy|once it.s done"
    r")\b",
    re.IGNORECASE,
)

_DUE_OFFSET = {
    "besok": timedelta(days=1),
    "lusa": timedelta(days=2),
    "minggu depan": timedelta(weeks=1),
    "bulan depan": timedelta(days=30),
    "setelah deploy": timedelta(hours=2),
    "after deploy": timedelta(hours=2),
}

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))


def _detect_commitment(text: str) -> str | None:
    """Return the matched commitment phrase or None."""
    m = _COMMITMENT_PATTERNS.search(text or "")
    return m.group(0) if m else None


def _due_at(phrase: str) -> datetime:
    """Estimate when to deliver the follow-up."""
    phrase_lower = phrase.lower()
    for key, delta in _DUE_OFFSET.items():
        if key in phrase_lower:
            return datetime.now(timezone.utc) + delta
    return datetime.now(timezone.utc) + timedelta(hours=24)  # default: next day


async def handle(event_type: str, context) -> None:
    if event_type != "agent:end":
        return

    # context is a dict (consistent with other viko hooks)
    reply_text = context.get("response") or ""
    if not reply_text:
        return

    phrase = _detect_commitment(reply_text)
    if not phrase:
        return

    # Determine slug from env
    slug = os.environ.get("VIKO_PROJECT_SLUG", "")
    if not slug:
        return

    # Write to /opt/data (mounted from host data/hermes-{slug}/) so deliver_commitments.py can read it
    commitments_file = HERMES_HOME / "commitments.json"
    commitments_file.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {"pending": []}
    if commitments_file.exists():
        try:
            data = json.loads(commitments_file.read_text())
        except Exception:
            data = {"pending": []}

    now = datetime.now(timezone.utc)
    commitment = {
        "id": str(uuid.uuid4())[:8],
        "text": f"Follow-up dari percakapan sebelumnya (trigger: \"{phrase}\"): {reply_text[:200]}",
        "due_at": _due_at(phrase).isoformat(),
        "created_at": now.isoformat(),
    }
    data["pending"].append(commitment)

    commitments_file.write_text(json.dumps(data, indent=2))
    print(f"[commitments] stored follow-up for {slug}: due {commitment['due_at']}", flush=True)
