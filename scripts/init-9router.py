#!/usr/bin/env python3
"""
Idempotent 9router initialization script.

Creates/updates all required combos in 9router's SQLite database.
Safe to run multiple times — existing records are updated, not duplicated.

Usage:
  python3 scripts/init-9router.py
  python3 scripts/init-9router.py /custom/path/to/data.sqlite

Run this after:
  - First-time setup
  - 9router data wipe (data/9router/ deleted)
  - Adding a new combo to this file

NOTE: Provider API keys (Anthropic Claude Code OAuth, Groq) must still be
configured manually via the 9router dashboard at http://localhost:20128.
Combos reference providers by model prefix — they work once API keys are added.
"""

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "9router" / "db" / "data.sqlite"

if len(sys.argv) > 1:
    DB_PATH = Path(sys.argv[1])

# ── Combo definitions ─────────────────────────────────────────────────────────
# Each combo: (name, models_list)
# Models are tried in order (fallback mode, Round Robin OFF).
# cc/ prefix = Claude Code OAuth (via 9router)
# groq/ prefix = Groq API

# Fallback ORDER matters: Claude → Claude → Groq. A transient single-model Claude
# blip falls to the OTHER Claude (still on-persona, follows SOUL.md), NOT straight to
# Groq/Llama — which ignores the Viko persona and bleeds generic "/help" / foreign-tool
# noise. Groq is the LAST-RESORT only (availability when ALL Claude is down): better a
# degraded reply than none.
COMBOS = [
    (
        "viko-chat",
        [
            "cc/claude-haiku-4-5-20251001",          # primary: fast, cheap
            "cc/claude-sonnet-4-6",                   # fallback: stay on Claude (quality)
            "groq/llama-3.3-70b-versatile",           # last-resort: all-Claude-down only
        ],
    ),
    (
        "viko-code",
        [
            "cc/claude-sonnet-4-6",                   # primary: smarter for code/analysis
            "cc/claude-haiku-4-5-20251001",          # fallback: stay on Claude
            "groq/llama-3.3-70b-versatile",           # last-resort
        ],
    ),
    (
        "viko-combo",
        [
            "cc/claude-haiku-4-5-20251001",          # primary: quality, follows persona
            "cc/claude-sonnet-4-6",                   # fallback: stay on Claude
            "groq/llama-3.3-70b-versatile",           # last-resort
        ],
    ),
]


def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Make sure 9router is running and has initialized its database.")
        sys.exit(1)

    db = sqlite3.connect(str(DB_PATH))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    for name, models in COMBOS:
        models_json = json.dumps(models)
        existing = db.execute("SELECT id FROM combos WHERE name=?", [name]).fetchone()
        if existing:
            db.execute(
                "UPDATE combos SET models=?, updatedAt=? WHERE name=?",
                [models_json, now, name],
            )
            print(f"  updated: {name}")
        else:
            db.execute(
                "INSERT INTO combos (id, name, kind, models, createdAt, updatedAt) VALUES (?, ?, '', ?, ?, ?)",
                [str(uuid.uuid4()), name, models_json, now, now],
            )
            print(f"  created: {name}")

    db.commit()
    db.close()
    print(f"✓ 9router combos initialized ({len(COMBOS)} combos)")
    print()
    print("Next step: ensure API keys are set in 9router dashboard (http://localhost:20128)")
    print("  → Providers → Claude Code (OAuth): connect your Anthropic account")
    print("  → Providers → Groq: add API key")


if __name__ == "__main__":
    main()
