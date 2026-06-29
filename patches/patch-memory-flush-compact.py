#!/usr/bin/env python3
"""Patch: Flush recent conversation to context.md before hermes compacts.

When hermes is about to compact (summarize) the context window, we first
extract the last 20 messages and append a timestamped snapshot to
/opt/data/context.md. This preserves key facts that might otherwise be
lost in the compaction summary.

Uses direct file I/O — no async tool dispatch needed. The injection point
is in the synchronous run_conversation() function in conversation_loop.py,
between the _safe_print announcement and the _compress_context() call.

Idempotent: skips if MARKER is already in the file.
"""
import sys
from pathlib import Path

TARGET = Path("/opt/hermes/agent/conversation_loop.py")
MARKER = "_viko_flush_before_compact"

INJECT_AFTER = '                    agent._safe_print("  ⟳ compacting context…")'

INJECT_CODE = (
    '                    agent._safe_print("  ⟳ compacting context…")\n'
    '                    # VIKO PATCH: memory flush before compaction _viko_flush_before_compact\n'
    '                    try:\n'
    '                        import datetime as _viko_dt\n'
    '                        _viko_ctx_path = __import__("pathlib").Path("/opt/data/context.md")\n'
    '                        _viko_ctx_path.parent.mkdir(parents=True, exist_ok=True)\n'
    '                        _viko_recent = [\n'
    '                            _m for _m in (messages or [])[-20:]\n'
    '                            if isinstance(_m, dict) and _m.get("role") in ("user", "assistant")\n'
    '                        ]\n'
    '                        _viko_lines = []\n'
    '                        for _viko_m in _viko_recent:\n'
    '                            _viko_role = _viko_m.get("role", "?")\n'
    '                            _viko_content = _viko_m.get("content") or ""\n'
    '                            if isinstance(_viko_content, list):\n'
    '                                _viko_parts = [\n'
    '                                    _p.get("text", "") for _p in _viko_content\n'
    '                                    if isinstance(_p, dict) and _p.get("type") == "text"\n'
    '                                ]\n'
    '                                _viko_content = " ".join(_viko_parts)\n'
    '                            _viko_snippet = str(_viko_content).strip().replace("\\n", " ")[:300]\n'
    '                            if _viko_snippet:\n'
    '                                _viko_lines.append(f"- [{_viko_role}] {_viko_snippet}")\n'
    '                        _viko_ts = _viko_dt.datetime.now(_viko_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")\n'
    '                        _viko_block = f"\\n## Pre-Compact Snapshot {_viko_ts}\\n" + "\\n".join(_viko_lines) + "\\n"\n'
    '                        with open(_viko_ctx_path, "a", encoding="utf-8") as _viko_f:\n'
    '                            _viko_f.write(_viko_block)\n'
    '                        agent._safe_print(f"  [viko] memory flush before compaction complete ({len(_viko_lines)} messages written)")\n'
    '                    except Exception as _viko_flush_err:\n'
    '                        agent._safe_print(f"  [viko] memory flush pre-compact failed (non-fatal): {_viko_flush_err}")\n'
    '                    # END VIKO PATCH'
)


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1

    content = TARGET.read_text(encoding="utf-8")

    if MARKER in content:
        print("✓ patch-memory-flush-compact: already applied")
        return 0

    if INJECT_AFTER not in content:
        print(
            "ERROR: injection point not found — hermes upstream changed; patch must be updated",
            file=sys.stderr,
        )
        return 1

    content = content.replace(INJECT_AFTER, INJECT_CODE, 1)
    TARGET.write_text(content, encoding="utf-8")
    print("✓ patch-memory-flush-compact: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
