#!/usr/bin/env python3
"""Patch: Improve handling of malformed tool call JSON in mini_swe_runner.py.

Instead of silently swallowing JSONDecodeError with args = {}, this patch:
1. Tries json.loads() first (existing behaviour)
2. On JSONDecodeError, tries ast.literal_eval() as a fallback
3. Logs the repair attempt either way
4. Falls back to args = {} only if both attempts fail (same end result, now visible)

Idempotent: skips if MARKER is already in the file.
"""
import sys
from pathlib import Path

TARGET = Path("/opt/hermes/mini_swe_runner.py")
MARKER = "_viko_tool_repair"

INJECT_AFTER = (
    "                    for tc in assistant_message.tool_calls:\n"
    "                        try:\n"
    "                            args = json.loads(tc.function.arguments)\n"
    "                        except json.JSONDecodeError:\n"
    "                            args = {}"
)

INJECT_CODE = (
    "                    for tc in assistant_message.tool_calls:\n"
    "                        try:\n"
    "                            args = json.loads(tc.function.arguments)\n"
    "                        except json.JSONDecodeError as _viko_tool_repair_exc:\n"
    "                            # VIKO PATCH: tool call repair — ast fallback + logging\n"
    "                            try:\n"
    "                                args = ast.literal_eval(tc.function.arguments)\n"
    "                                print(\n"
    "                                    f'[viko-tool-repair] repaired malformed JSON via ast.literal_eval: '\n"
    "                                    f'{tc.function.arguments!r:.120}'\n"
    "                                )\n"
    "                            except Exception:\n"
    "                                print(\n"
    "                                    f'[viko-tool-repair] could not repair malformed JSON, using {{}}: '\n"
    "                                    f'{_viko_tool_repair_exc} | raw={tc.function.arguments!r:.120}'\n"
    "                                )\n"
    "                                args = {}\n"
    "                            # END VIKO PATCH"
)


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1

    content = TARGET.read_text(encoding="utf-8")

    if MARKER in content:
        print("✓ patch-tool-call-repair: already applied")
        return 0

    if INJECT_AFTER not in content:
        print(
            "ERROR: injection point not found — hermes upstream changed; patch must be updated",
            file=sys.stderr,
        )
        return 1

    content = content.replace(INJECT_AFTER, INJECT_CODE, 1)
    TARGET.write_text(content, encoding="utf-8")
    print("✓ patch-tool-call-repair: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
