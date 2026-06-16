#!/usr/bin/env python3
"""
Onboard a new project into Viko.

Run this on trahku as the viko user (Viko does this via SSH):
  python3 ~/projects/viko-agent/scripts/add-project.py \\
    <slug> <group_jid> <github_url> [--vps-host HOST] [--members PHONES]

Arguments:
  slug          Project slug (e.g. siprodev, mankop)
  group_jid     WhatsApp group JID (e.g. 120363407940533307@g.us)
  github_url    GitHub repo URL (e.g. https://github.com/forgeyard/siprodev)
  --vps-host    VPS hostname or IP for this project (optional)
  --members     Comma-separated phone numbers to allow DM access (optional)
                e.g. "6282112124452,6281234567890"

Backward compat: if 4th positional arg exists and doesn't start with --,
  treat as member_phones.

What this does:
  1. Clone/pull repo to $VIKO_PROJECTS_ROOT/<slug>/
  2. Create projects/<slug>/context.md and steps.md stubs
  3. Call spawn-hermes.py to create an isolated Hermes container for the project
  4. If --members provided, update WHATSAPP_ALLOWED_USERS in data/hermes-admin/.env
     (falls back to data/hermes/.env if hermes-admin/.env doesn't exist)
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

REPO_DIR = Path(__file__).parent.parent.resolve()
HERMES_ADMIN_ENV_PATH = REPO_DIR / "data" / "hermes-admin" / ".env"
HERMES_ENV_PATH = REPO_DIR / "data" / "hermes" / ".env"


def _load_env(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.exists() else []


def _update_env(path: Path, updates: dict[str, str]) -> None:
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


def _get_env_val(path: Path, key: str) -> str:
    for line in _load_env(path):
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def main():
    # Handle backward compat: if 4th positional arg exists and doesn't start with --,
    # inject it as --members before argparse sees the args.
    args_in = sys.argv[1:]
    if len(args_in) >= 4 and not args_in[3].startswith("--"):
        args_in = args_in[:3] + ["--members", args_in[3]] + args_in[4:]

    parser = argparse.ArgumentParser(
        description="Onboard a new project into Viko.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("slug", help="Project slug (e.g. siprodev)")
    parser.add_argument("group_jid", help="WhatsApp group JID")
    parser.add_argument("github_url", help="GitHub repo URL")
    parser.add_argument("--vps-host", default="", help="VPS hostname or IP for this project")
    parser.add_argument("--members", default="", help="Comma-separated phone numbers for DM access")
    args = parser.parse_args(args_in)

    slug = args.slug.lower().strip()
    group_jid = args.group_jid.strip()
    github_url = args.github_url.strip()
    vps_host = args.vps_host.strip()
    member_phones = [p.strip().lstrip("+") for p in args.members.split(",") if p.strip()]

    # Resolve VIKO_PROJECTS_ROOT
    projects_root_str = _get_env_val(REPO_DIR / ".env", "VIKO_PROJECTS_ROOT")
    projects_root = Path(projects_root_str) if projects_root_str else REPO_DIR.parent
    project_dir = projects_root / slug

    print(f"\n=== Viko onboarding: {slug} ===")
    print(f"  Group JID : {group_jid}")
    print(f"  GitHub    : {github_url}")
    print(f"  Clone to  : {project_dir}")
    if vps_host:
        print(f"  VPS host  : {vps_host}")
    if member_phones:
        print(f"  DM access : {', '.join(member_phones)}")

    # ── 1. Clone or pull repo ─────────────────────────────────────────────────
    print("\n[1/4] Repository...")
    if (project_dir / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(project_dir), "pull", "--ff-only"],
            capture_output=True, text=True
        )
        print(f"      {(result.stdout or result.stderr).strip()}")
    else:
        project_dir.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", github_url, str(project_dir)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"      ERROR: {result.stderr.strip()}")
            sys.exit(1)
        print(f"      Cloned to {project_dir}")

    # ── 2. Create context.md and steps.md stubs ───────────────────────────────
    print("\n[2/4] Project context stubs...")
    context_dir = REPO_DIR / "projects" / slug
    context_dir.mkdir(parents=True, exist_ok=True)

    context_file = context_dir / "context.md"
    if not context_file.exists():
        context_file.write_text(
            f"# Project: {slug}\n\n"
            f"## Info\n"
            f"- GitHub: {github_url}\n"
            f"- WA Group JID: {group_jid}\n"
            f"- Onboarded: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"## Stack\n(Scan codebase dulu — jalankan: `cat {project_dir}/package.json` atau `ls {project_dir}/`)\n\n"
            f"## Notes\n(Tambahkan konteks project di sini)\n"
        )
        print(f"      Created context.md")
    else:
        print(f"      context.md exists, skipping.")

    steps_file = context_dir / "steps.md"
    if not steps_file.exists():
        steps_file.write_text(f"# Steps: {slug}\n\n## Active Tasks\n(Belum ada — tambahkan saat mulai kerja)\n")
        print(f"      Created steps.md")
    else:
        print(f"      steps.md exists, skipping.")

    # ── 3. Spawn isolated Hermes container for this project ───────────────────
    print("\n[3/4] Spawning Hermes instance...")
    spawn_cmd = [sys.executable, str(REPO_DIR / "scripts" / "spawn-hermes.py"), slug, group_jid]
    if vps_host:
        spawn_cmd += ["--vps-host", vps_host]
    result = subprocess.run(spawn_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR spawning Hermes: {result.stderr}")
        sys.exit(1)

    # ── 4. Update WHATSAPP_ALLOWED_USERS for DM access ────────────────────────
    if member_phones:
        print("\n[4/4] WHATSAPP_ALLOWED_USERS — DM access...")
        # Use hermes-admin/.env; fall back to hermes/.env for migration compat
        env_path = HERMES_ADMIN_ENV_PATH if HERMES_ADMIN_ENV_PATH.exists() else HERMES_ENV_PATH
        print(f"      Writing to: {env_path}")
        existing_allowed = _get_env_val(env_path, "WHATSAPP_ALLOWED_USERS")
        allowed = [u.strip() for u in existing_allowed.split(",") if u.strip()]
        added = []
        for phone in member_phones:
            if phone not in allowed:
                allowed.append(phone)
                added.append(phone)
        if added:
            print(f"      Added: {', '.join(added)}")
        print(f"      WHATSAPP_ALLOWED_USERS={','.join(allowed)}")
        _update_env(env_path, {"WHATSAPP_ALLOWED_USERS": ",".join(allowed)})
    else:
        print("\n[4/4] No members specified — skipping WHATSAPP_ALLOWED_USERS update.")

    print(f"\n✓ Onboarding {slug} selesai.")
    print(f"\nLangkah Viko berikutnya:")
    print(f"  1. Scan codebase: ls {project_dir}/ dan baca file utama")
    print(f"  2. Update {context_dir}/context.md dengan stack dan info project")
    print(f"  3. Restart hermes (admin instance) jika WHATSAPP_ALLOWED_USERS diubah:")
    print(f"     cd ~/projects/viko-agent && docker compose --profile full up -d --force-recreate hermes-admin")
    print(f"  (spawn-hermes.py output above shows status of isolated Hermes instance)")


if __name__ == "__main__":
    main()
