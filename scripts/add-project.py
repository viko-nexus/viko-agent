#!/usr/bin/env python3
"""
Onboard a new project into Viko.

Run this on trahku as the viko user (Viko does this via SSH):
  python3 ~/projects/viko-agent/scripts/add-project.py \\
    <slug> <group_jid> <github_url> [member_phones]

Arguments:
  slug          Project slug (e.g. siprodev, mankop)
  group_jid     WhatsApp group JID (e.g. 120363407940533307@g.us)
  github_url    GitHub repo URL (e.g. https://github.com/forgeyard/siprodev)
  member_phones Comma-separated phone numbers to allow DM access (optional)
                e.g. "6282112124452,6281234567890"

What this does:
  1. Clone/pull repo to $VIKO_PROJECTS_ROOT/<slug>/
  2. Create projects/<slug>/context.md and steps.md stubs
  3. Add channel_prompts entry in data/hermes/config.yaml
  4. Add group JID to WHATSAPP_TRUSTED_GROUPS in data/hermes/.env
  5. Add member phones to WHATSAPP_ALLOWED_USERS in data/hermes/.env
  6. Print restart command (Viko runs this via SSH after script exits)
"""

import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml

REPO_DIR = Path(__file__).parent.parent.resolve()
CONFIG_PATH = REPO_DIR / "data" / "hermes" / "config.yaml"
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
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    slug = sys.argv[1].lower().strip()
    group_jid = sys.argv[2].strip()
    github_url = sys.argv[3].strip()
    member_phones_raw = sys.argv[4] if len(sys.argv) > 4 else ""
    member_phones = [p.strip().lstrip("+") for p in member_phones_raw.split(",") if p.strip()]

    # Resolve VIKO_PROJECTS_ROOT
    projects_root_str = _get_env_val(REPO_DIR / ".env", "VIKO_PROJECTS_ROOT")
    projects_root = Path(projects_root_str) if projects_root_str else REPO_DIR.parent
    project_dir = projects_root / slug

    print(f"\n=== Viko onboarding: {slug} ===")
    print(f"  Group JID : {group_jid}")
    print(f"  GitHub    : {github_url}")
    print(f"  Clone to  : {project_dir}")
    if member_phones:
        print(f"  DM access : {', '.join(member_phones)}")

    # ── 1. Clone or pull repo ─────────────────────────────────────────────────
    print("\n[1/5] Repository...")
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
    print("\n[2/5] Project context stubs...")
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

    # ── 3. Update config.yaml (channel_prompts) ───────────────────────────────
    print("\n[3/5] config.yaml — channel_prompts...")
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)

    prompt = (
        f"Kamu ada di group WhatsApp project {slug}. "
        f"Active project: {slug}. Load {slug} project context sebelum merespons. "
        f"Siapapun di group ini boleh bertanya — hanya Eksa yang bisa authorize eksekusi (deploy, kode, infra). "
        f"PENTING: Jangan membahas informasi dari project lain di group ini. "
        f"Fokus 100% pada project {slug}. Balas dalam Bahasa Indonesia."
    )

    if "whatsapp" not in cfg:
        cfg["whatsapp"] = {}
    if "channel_prompts" not in cfg["whatsapp"]:
        cfg["whatsapp"]["channel_prompts"] = {}

    cfg["whatsapp"]["channel_prompts"][group_jid] = prompt

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"      Added channel_prompt for {group_jid}")

    # ── 4. Update data/hermes/.env ────────────────────────────────────────────
    print("\n[4/5] data/hermes/.env — WHATSAPP_TRUSTED_GROUPS...")
    existing_trusted = _get_env_val(HERMES_ENV_PATH, "WHATSAPP_TRUSTED_GROUPS")
    trusted = [g.strip() for g in existing_trusted.split(",") if g.strip()]
    if group_jid not in trusted:
        trusted.append(group_jid)
    print(f"      WHATSAPP_TRUSTED_GROUPS={','.join(trusted)}")

    print("\n[5/5] data/hermes/.env — WHATSAPP_ALLOWED_USERS...")
    existing_allowed = _get_env_val(HERMES_ENV_PATH, "WHATSAPP_ALLOWED_USERS")
    allowed = [u.strip() for u in existing_allowed.split(",") if u.strip()]
    added = []
    for phone in member_phones:
        if phone not in allowed:
            allowed.append(phone)
            added.append(phone)
    if added:
        print(f"      Added: {', '.join(added)}")
    print(f"      WHATSAPP_ALLOWED_USERS={','.join(allowed)}")

    _update_env(HERMES_ENV_PATH, {
        "WHATSAPP_TRUSTED_GROUPS": ",".join(trusted),
        "WHATSAPP_ALLOWED_USERS": ",".join(allowed),
    })

    print(f"\n✓ Onboarding {slug} selesai.")
    print(f"\nLangkah Viko berikutnya:")
    print(f"  1. Scan codebase: ls {project_dir}/ dan baca file utama")
    print(f"  2. Update {context_dir}/context.md dengan stack dan info project")
    print(f"  3. Restart hermes (jalankan ini via SSH ke viko-vps):")
    print(f"     cd ~/projects/viko-agent && docker compose --profile full up -d --force-recreate hermes")


if __name__ == "__main__":
    main()
