#!/usr/bin/env python3
"""Patch agent notification messages to Indonesian."""
import sys
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes" / "hermes-agent"

PATCHES = {
    "agent/conversation_compression.py": [
        (
            '"🗜️ Compacting context — summarizing earlier conversation so I can continue..."',
            '"🗜️ Lagi ringkas konteks dulu ya, sebentar..."',
        ),
    ],
    "run_agent.py": [
        (
            'if self.status_callback:\n'
            '            try:\n'
            '                self.status_callback("lifecycle", message)\n'
            '            except Exception:\n'
            '                logger.debug("status_callback error in _emit_status", exc_info=True)',
            '# VIKO PATCH: suppress lifecycle status to gateway (WA) — log-only\n'
            '        if False and self.status_callback:\n'
            '            try:\n'
            '                self.status_callback("lifecycle", message)\n'
            '            except Exception:\n'
            '                logger.debug("status_callback error in _emit_status", exc_info=True)',
        ),
        (
            'if self.status_callback:\n'
            '            try:\n'
            '                self.status_callback("warn", message)\n'
            '            except Exception:\n'
            '                logger.debug("status_callback error in _emit_warning", exc_info=True)',
            '# VIKO PATCH: suppress warn status to gateway (WA) — log-only\n'
            '        if False and self.status_callback:\n'
            '            try:\n'
            '                self.status_callback("warn", message)\n'
            '            except Exception:\n'
            '                logger.debug("status_callback error in _emit_warning", exc_info=True)',
        ),
    ],
    "agent/conversation_loop.py": [
        (
            '"⚠️ Rate limited — switching to fallback provider..."',
            '"⚠️ Kena limit, pindah ke backup..."',
        ),
        (
            '"⚠️ Billing or credits exhausted — switching to fallback provider..."',
            '"⚠️ Kredit habis, pindah ke backup..."',
        ),
        (
            '"⚠️ Empty/malformed response — switching to fallback..."',
            '"⚠️ Respons rusak, coba backup..."',
        ),
        (
            'f"⚠️  Request payload too large (413) — compression attempt {compression_attempts}/{max_compression_attempts}..."',
            'f"⚠️ Konteks terlalu besar, lagi dikompresi ({compression_attempts}/{max_compression_attempts})..."',
        ),
        (
            'f"⚠️ Non-retryable error (HTTP {status_code}) — trying fallback..."',
            'f"⚠️ Error HTTP {status_code}, coba backup..."',
        ),
        (
            'f"⏱️ Rate limited. Waiting {wait_time:.1f}s (attempt {retry_count + 1}/{max_retries})..."',
            'f"⏱️ Kena limit, tunggu {wait_time:.1f}s ({retry_count + 1}/{max_retries})..."',
        ),
        (
            'f"❌ Rate limited after {max_retries} retries — {_final_summary}"',
            'f"❌ Gagal setelah {max_retries} percobaan — {_final_summary}"',
        ),
    ],
}

def patch_file(rel_path, patches):
    target = HERMES_HOME / rel_path
    if not target.exists():
        print(f"ERROR: {target} not found", file=sys.stderr)
        return 0

    content = target.read_text(encoding="utf-8")
    applied = 0
    for old, new in patches:
        if old in content:
            content = content.replace(old, new)
            applied += 1
        elif new in content:
            applied += 1  # already patched
        else:
            print(f"  WARNING: not found: {old[:60]}...")

    target.write_text(content, encoding="utf-8")

    # Clear pyc cache
    pyc_dir = target.parent / "__pycache__"
    stem = target.stem
    for pyc in pyc_dir.glob(f"{stem}*.pyc"):
        pyc.unlink()

    print(f"✓ {rel_path} ({applied}/{len(patches)} patched)")
    return applied

def main():
    total = 0
    for rel_path, patches in PATCHES.items():
        total += patch_file(rel_path, patches)
    print(f"\nDone — {total} patches applied")

if __name__ == "__main__":
    main()
