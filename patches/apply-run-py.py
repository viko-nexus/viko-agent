#!/usr/bin/env python3
"""Patch gateway/run.py — translate system notifications to Indonesian."""
import sys
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes" / "hermes-agent"
TARGET = HERMES_HOME / "gateway" / "run.py"

PATCHES = [
    (
        'action = "restarting" if self._restart_requested else "shutting down"\n'
        '        hint = (\n'
        '            "Your current task will be interrupted. "\n'
        '            "Send any message after restart and I\'ll try to resume where you left off."\n'
        '            if self._restart_requested\n'
        '            else "Your current task will be interrupted."\n'
        '        )\n'
        '        msg = f"⚠️ Gateway {action} — {hint}"',

        'action = "restart sebentar ya" if self._restart_requested else "mau offline dulu"\n'
        '        hint = (\n'
        '            "Task kamu diinterrupt. Kirim pesan lagi setelah restart, nanti aku lanjutin 🔄"\n'
        '            if self._restart_requested\n'
        '            else "Task yang lagi jalan bakal dihentiin ya."\n'
        '        )\n'
        '        msg = f"⚠️ Viko {action} — {hint}"',
    ),
    (
        'response = (response or "") + (\n'
        '                    "\\n\\n🔄 Session auto-reset — the conversation exceeded the "\n'
        '                    "maximum context size and could not be compressed further. "\n'
        '                    "Your next message will start a fresh session."\n'
        '                )',

        'response = (response or "") + (\n'
        '                    "\\n\\n🔄 Sesi direset — konteks udah penuh banget, terpaksa mulai segar. "\n'
        '                    "Pesan berikutnya mulai sesi baru ya!"\n'
        '                )',
    ),
    (
        'message = "♻️ Gateway online — Hermes is back and ready."',
        'message = "Online lagi! Siap nerima perintah 🟢"',
    ),
]

def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")
    applied = 0

    for old, new in PATCHES:
        if old in content:
            content = content.replace(old, new)
            applied += 1
        elif new in content:
            applied += 1  # already patched
        else:
            print(f"WARNING: patch not found (may have changed upstream): {old[:60]}...")

    TARGET.write_text(content, encoding="utf-8")
    print(f"✓ run.py patched ({applied}/{len(PATCHES)} applied)")

if __name__ == "__main__":
    main()
