#!/usr/bin/env python3
"""Patch: Inject recent dreamed context.md entries into a fresh session.

scripts/dream_sessions.py and patch-memory-flush-compact.py both append
timestamped blocks to /opt/data/context.md (session summaries before pruning,
snapshots before compaction) — but nothing read that file back, so once a
session was pruned (idle) the recap was write-only and Viko lost "today's"
conversation context.

This patch injects right after Hermes builds context_prompt for a message,
before the existing auto-reset notice is prepended. When the session is fresh
(_is_new_session) and NOT one of Hermes' own auto-resets (which already gets
its own notice), it reads context.md, keeps only blocks timestamped within
the last VIKO_CONTEXT_INJECT_HOURS (default 24) hours, and prepends the most
recent ones as a system note — so a same-day gap in activity doesn't wipe
Viko's memory of the conversation.

context.md only ever grows (dream_sessions.py and patch-memory-flush-compact.py
append to it, nothing rotates it), so this patch skips reading it entirely once
it exceeds VIKO_CONTEXT_INJECT_MAX_BYTES (default 512KB) rather than re-parsing
an ever-larger file on every new session.

Idempotent: skips if MARKER is already in the file.
"""
import sys
from pathlib import Path

TARGET = Path("/opt/hermes/gateway/run.py")
MARKER = "_viko_session_context_inject"

INJECT_AFTER = (
    "        context_prompt = build_session_context_prompt(context, redact_pii=_redact_pii)"
)

INJECT_CODE = (
    "        context_prompt = build_session_context_prompt(context, redact_pii=_redact_pii)\n"
    "        # VIKO PATCH: recover dreamed context on a fresh session _viko_session_context_inject\n"
    "        if _is_new_session and not _was_auto_reset:\n"
    "            try:\n"
    "                _viko_ctx_file = Path('/opt/data/context.md')\n"
    "                _viko_max_bytes = int(os.environ.get('VIKO_CONTEXT_INJECT_MAX_BYTES', '524288'))\n"
    "                if _viko_ctx_file.exists() and _viko_ctx_file.stat().st_size <= _viko_max_bytes:\n"
    "                    from datetime import timezone as _viko_tz, timedelta as _viko_td\n"
    "                    _viko_hours = float(os.environ.get('VIKO_CONTEXT_INJECT_HOURS', '24'))\n"
    "                    _viko_cutoff = datetime.now(_viko_tz.utc) - _viko_td(hours=_viko_hours)\n"
    "                    _viko_text = _viko_ctx_file.read_text(encoding='utf-8')\n"
    "                    _viko_blocks = re.split(r'(?=^#{2,3} )', _viko_text, flags=re.MULTILINE)\n"
    "                    _viko_recent = []\n"
    "                    for _viko_b in _viko_blocks:\n"
    "                        _viko_m = re.search(r'(\\d{4}-\\d{2}-\\d{2}[ T]\\d{2}:\\d{2})', _viko_b)\n"
    "                        if not _viko_m:\n"
    "                            continue\n"
    "                        try:\n"
    "                            _viko_bt = datetime.fromisoformat(\n"
    "                                _viko_m.group(1).replace(' ', 'T')\n"
    "                            ).replace(tzinfo=_viko_tz.utc)\n"
    "                        except Exception:\n"
    "                            continue\n"
    "                        if _viko_bt >= _viko_cutoff:\n"
    "                            _viko_recent.append(_viko_b.strip())\n"
    "                    if _viko_recent:\n"
    "                        _viko_note = (\n"
    "                            '[System note: Ringkasan percakapan sebelumnya di chat ini dalam '\n"
    "                            f'{int(_viko_hours)} jam terakhir (dipulihkan setelah sesi baru):]\\n\\n'\n"
    "                            + '\\n\\n'.join(_viko_recent[-5:])\n"
    "                        )\n"
    "                        context_prompt = _viko_note + '\\n\\n' + context_prompt\n"
    "            except Exception as _viko_ctx_err:\n"
    "                print(f'[viko] session-context-inject failed (non-fatal): {_viko_ctx_err}')\n"
    "        # END VIKO PATCH"
)


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1

    content = TARGET.read_text(encoding="utf-8")

    if MARKER in content:
        print("✓ patch-session-context-inject: already applied")
        return 0

    if INJECT_AFTER not in content:
        print(
            "ERROR: injection point not found — hermes upstream changed; patch must be updated",
            file=sys.stderr,
        )
        return 1

    content = content.replace(INJECT_AFTER, INJECT_CODE, 1)
    TARGET.write_text(content, encoding="utf-8")
    print("✓ patch-session-context-inject: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
