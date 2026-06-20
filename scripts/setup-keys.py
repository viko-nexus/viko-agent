#!/usr/bin/env python3
"""
Configure SSH aliases for a new project.

Adds Host entries to ~/.viko/ssh/config using Viko's master key (id_viko).
No keypair generation needed — user adds id_viko.pub to the VPS user once.

Run on the deploy VPS host (not inside a container):
  python3 ~/projects/viko-agent/scripts/setup-keys.py <slug> <github_url> [vps_host] [vps_user]

GitHub access uses HTTPS + GITHUB_TOKEN — no deploy key needed.
VPS SSH uses ~/.viko/ssh/id_viko for all projects.
"""

import sys
import os
import re
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.resolve()


def _get_ssh_dir() -> Path:
    ssh_dir = Path.home() / ".viko" / "ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    return ssh_dir


def _remove_ssh_host_block(text: str, host_name: str) -> str:
    return re.sub(rf'\nHost {re.escape(host_name)}\n(?:[ \t]+.*\n)*', '', text)


def update_ssh_config(slug: str, vps_host: str, ssh_dir: Path, vps_user: str = "viko-exec") -> None:
    """Add or update SSH Host alias for project VPS in ~/.viko/ssh/config."""
    if not vps_host:
        print("  No VPS host specified — skipping SSH config")
        return

    config_path = ssh_dir / "config"
    existing = config_path.read_text() if config_path.exists() else ""
    updated = existing

    host_name = f"{slug}-vps"
    action = "updated" if f"Host {host_name}" in updated else "new"
    if action == "updated":
        updated = _remove_ssh_host_block(updated, host_name)

    updated += (
        f"\nHost {slug}-vps\n"
        f"    HostName {vps_host}\n"
        f"    User {vps_user}\n"
        f"    IdentityFile /opt/data/.ssh/id_viko\n"
        f"    IdentitiesOnly yes\n"
        f"    StrictHostKeyChecking accept-new\n"
        f"    UserKnownHostsFile /opt/data/.ssh/known_hosts\n"
    )

    config_path.write_text(updated)
    print(f"  SSH config: {slug}-vps ({action}) → {vps_user}@{vps_host} via id_viko")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    # Guard: must run on host, not inside container
    ssh_dir_check = Path(os.environ.get("HOME", "/root")) / ".viko" / "ssh"
    if not ssh_dir_check.exists():
        print("ERROR: ~/.viko/ssh/ not found.")
        print("Run on the VPS host, not inside the Hermes container.")
        sys.exit(1)

    slug = sys.argv[1].lower().strip()
    vps_host = sys.argv[3].strip() if len(sys.argv) > 3 else ""
    vps_user = sys.argv[4].strip() if len(sys.argv) > 4 else "viko-exec"

    ssh_dir = _get_ssh_dir()

    print(f"\n=== SSH config: {slug} ===")
    update_ssh_config(slug, vps_host, ssh_dir, vps_user)

    print(f"\n{'='*50}")
    print("PHASE1_COMPLETE")
    print(f"VPS_KEY_REQUIRED={'true' if vps_host else 'false'}")
    print(f"{'='*50}")

    if vps_host:
        pub_key_path = ssh_dir / "id_viko.pub"
        pub_key = pub_key_path.read_text().strip() if pub_key_path.exists() else "(id_viko.pub not found)"
        print(f"\n⚠ VPS SSH key — pastikan key ini sudah di authorized_keys {vps_user}@{vps_host}:")
        print(f"  {pub_key}")
        print("\n  Kalau belum, tambahkan:")
        print(f'  echo "{pub_key}" >> ~/.ssh/authorized_keys')
        print("\nBalas 'done' setelah selesai.")
    else:
        print("\nTidak ada VPS — GitHub via HTTPS + token, langsung lanjut Phase 2.")


if __name__ == "__main__":
    main()
