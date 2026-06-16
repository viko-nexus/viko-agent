#!/usr/bin/env python3
"""
Allow a phone number to DM Viko directly.

Run this on trahku (Viko does this via SSH):
  python3 ~/projects/viko-agent/scripts/allow-member.py <phone> [phone2 ...]

Phone format: with or without + prefix (e.g. 6287820001010 or +6287820001010).
Safe to run multiple times — only missing entries are added.

What this does:
  - Adds phone(s) to WHATSAPP_ALLOWED_USERS in data/hermes/.env
  - Hermes must be restarted to apply (script prints the command)
"""

import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.resolve()
HERMES_ENV_PATH = REPO_DIR / "data" / "hermes" / ".env"


def _load_env(path: Path) -> list:
    return path.read_text().splitlines() if path.exists() else []


def _get_env_val(path: Path, key: str) -> str:
    for line in _load_env(path):
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _update_env(path: Path, updates: dict) -> None:
    lines = _load_env(path)
    updated_keys = set()
    new_lines = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else None
        if key and key in updates:
            new_lines.append(f"{key}={updates[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")
    path.write_text("\n".join(new_lines) + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    phones = [p.strip().lstrip("+") for p in sys.argv[1:] if p.strip()]

    existing = _get_env_val(HERMES_ENV_PATH, "WHATSAPP_ALLOWED_USERS")
    allowed = [u.strip() for u in existing.split(",") if u.strip()]

    added = []
    for phone in phones:
        if phone not in allowed:
            allowed.append(phone)
            added.append(phone)

    if not added:
        print("✓ Semua nomor sudah ada di allowlist, tidak ada yang ditambah.")
        return

    _update_env(HERMES_ENV_PATH, {"WHATSAPP_ALLOWED_USERS": ",".join(allowed)})
    print(f"✓ Ditambahkan ke WHATSAPP_ALLOWED_USERS: {', '.join(added)}")
    print(f"  Full list: {','.join(allowed)}")
    print(f"\nRestart hermes untuk apply:")
    print(f"  cd ~/projects/viko-agent && docker compose --profile full up -d --force-recreate hermes")


if __name__ == "__main__":
    main()
