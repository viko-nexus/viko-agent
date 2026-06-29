#!/usr/bin/env python3
"""Patch: Soft-trim stale tool results from context before each LLM call.

Keeps the first 200 and last 200 characters of each tool result message that
falls outside the most recent TOOL_RESULT_PRUNE_KEEP results (default: 3).
Inserts "...[trimmed]..." between the kept segments.

Operates only on the in-memory api_kwargs["messages"] list — the on-disk
transcript is never modified.

Idempotent: skips if MARKER is already in the file.
"""
import sys
from pathlib import Path

TARGET = Path("/opt/hermes/agent/chat_completion_helpers.py")
MARKER = "_viko_tool_prune"

INJECT_AFTER = (
    '                )\n'
    '                result["response"] = request_client.chat.completions.create(**api_kwargs)'
)

INJECT_CODE = (
    '                )\n'
    '                # VIKO PATCH: soft-trim old tool results before LLM call _viko_tool_prune\n'
    '                _viko_keep = int(__import__("os").environ.get("TOOL_RESULT_PRUNE_KEEP", "3"))\n'
    '                _viko_msgs = api_kwargs.get("messages", [])\n'
    '                _viko_tool_indices = [\n'
    '                    _i for _i, _m in enumerate(_viko_msgs)\n'
    '                    if isinstance(_m, dict) and _m.get("role") == "tool"\n'
    '                ]\n'
    '                _viko_trim_set = set(_viko_tool_indices[:-_viko_keep] if _viko_keep else _viko_tool_indices)\n'
    '                for _viko_i in _viko_trim_set:\n'
    '                    _viko_m = _viko_msgs[_viko_i]\n'
    '                    _viko_c = _viko_m.get("content", "")\n'
    '                    if isinstance(_viko_c, str) and len(_viko_c) > 410:\n'
    '                        _viko_m["content"] = _viko_c[:200] + "\\n...[trimmed]...\\n" + _viko_c[-200:]\n'
    '                    elif isinstance(_viko_c, list):\n'
    '                        for _viko_part in _viko_c:\n'
    '                            if isinstance(_viko_part, dict) and _viko_part.get("type") == "text":\n'
    '                                _viko_t = _viko_part.get("text", "")\n'
    '                                if len(_viko_t) > 410:\n'
    '                                    _viko_part["text"] = _viko_t[:200] + "\\n...[trimmed]...\\n" + _viko_t[-200:]\n'
    '                # END VIKO PATCH\n'
    '                result["response"] = request_client.chat.completions.create(**api_kwargs)'
)


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1

    content = TARGET.read_text(encoding="utf-8")

    if MARKER in content:
        print("✓ patch-tool-result-pruning: already applied")
        return 0

    if INJECT_AFTER not in content:
        print(
            "ERROR: injection point not found — hermes upstream changed; patch must be updated",
            file=sys.stderr,
        )
        return 1

    content = content.replace(INJECT_AFTER, INJECT_CODE, 1)
    TARGET.write_text(content, encoding="utf-8")
    print("✓ patch-tool-result-pruning: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
