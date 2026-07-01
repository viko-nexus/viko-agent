#!/usr/bin/env python3
"""Prune idle chat sessions dari semua project Hermes-Project.

Logic:
- Baca sessions.json tiap project
- Hapus session yang updated_at > IDLE_HOURS jam lalu
- Session owner (caller pattern beda) tidak disentuh — owner punya sender=Eksa
  tapi kita prune berdasarkan idle time saja, semua session kena kalau idle
- Backup sessions.json.bak sebelum modifikasi
- Log hasil ke stdout

Usage:
    python3 prune-idle-sessions.py [--idle-hours N] [--dry-run]
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add repo root to path so dream_sessions can be imported
sys.path.insert(0, str(Path(__file__).parent))
try:
    from dream_sessions import dream_session
    _DREAMING_AVAILABLE = True
except ImportError:
    _DREAMING_AVAILABLE = False

DATA_ROOT = Path("/home/deploy/viko-agent/data")
# Long enough that a same-day gap in chat activity doesn't wipe the session (and
# lose "today's" context); short enough that idle sessions still get pruned and
# dreamed within the same day. Longer gaps are bridged by patch-session-context-inject.py
# reading the dreamed summary back in when a fresh session starts.
DEFAULT_IDLE_HOURS = 6


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--idle-hours", type=float, default=DEFAULT_IDLE_HOURS,
                   help=f"Hapus session idle lebih dari N jam (default: {DEFAULT_IDLE_HOURS})")
    p.add_argument("--dry-run", action="store_true",
                   help="Simulasi saja, tidak tulis perubahan")
    return p.parse_args()


def utcnow():
    return datetime.now(timezone.utc)


def parse_dt(s):
    """Parse ISO timestamp, support dengan/tanpa timezone."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def prune_project(sessions_file: Path, idle_threshold_hours: float, dry_run: bool):
    try:
        data = json.loads(sessions_file.read_text())
    except Exception as e:
        print(f"  ERROR baca {sessions_file}: {e}")
        return 0, 0

    now = utcnow()
    cutoff_seconds = idle_threshold_hours * 3600

    pruned = []
    kept = []

    for key, session in data.items():
        updated_at = parse_dt(session.get("updated_at"))
        if updated_at is None:
            kept.append(key)
            continue

        idle_secs = (now - updated_at).total_seconds()
        if idle_secs > cutoff_seconds:
            pruned.append((key, idle_secs))
        else:
            kept.append(key)

    if pruned:
        if not dry_run:
            # Dream (summarize) each session before deleting it
            if _DREAMING_AVAILABLE:
                slug = sessions_file.parts[-3].removeprefix("hermes-")
                for key, _ in pruned:
                    session_data = data.get(key, {})
                    dream_session(slug, sessions_file, key, session_data)

            # Backup dulu
            backup = sessions_file.with_suffix(".json.bak")
            shutil.copy2(sessions_file, backup)
            # Tulis ulang tanpa session yang dipruned
            pruned_keys = {k for k, _ in pruned}
            new_data = {k: v for k, v in data.items() if k not in pruned_keys}
            sessions_file.write_text(json.dumps(new_data, indent=2))

        for key, idle_secs in pruned:
            idle_h = idle_secs / 3600
            print(f"  {'[DRY]' if dry_run else '[PRUNED]'} {key[-30:]} (idle {idle_h:.1f}h)")

    return len(pruned), len(kept)


def main():
    args = parse_args()
    print(f"=== prune-idle-sessions | idle>{args.idle_hours}h | {'DRY RUN' if args.dry_run else 'LIVE'} | {utcnow().isoformat()} ===")

    projects = sorted(DATA_ROOT.glob("hermes-*/sessions/sessions.json"))
    if not projects:
        print("Tidak ada sessions.json ditemukan.")
        sys.exit(0)

    total_pruned = 0
    total_kept = 0

    for sf in projects:
        slug = sf.parts[-3]  # hermes-<slug>
        print(f"\n{slug}:")
        pruned, kept = prune_project(sf, args.idle_hours, args.dry_run)
        print(f"  -> pruned={pruned} kept={kept}")
        total_pruned += pruned
        total_kept += kept

    print(f"\nTotal: pruned={total_pruned} kept={total_kept}")


if __name__ == "__main__":
    main()
