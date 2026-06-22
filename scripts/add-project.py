#!/usr/bin/env python3
"""
Onboard a new project into Viko.

Run this on the deploy VPS (Viko does this via SSH):
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
import re
import json
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

REPO_DIR = Path(__file__).parent.parent.resolve()
SSH_DIR = Path.home() / ".viko" / "ssh"
CORE_SSH_CMD = ("ssh -i /opt/data/.ssh/id_viko -o IdentitiesOnly=yes "
                "-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/opt/data/.ssh/known_hosts")
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


def _to_https_url(github_url: str, token: str) -> str:
    """Convert any GitHub URL (SSH or HTTPS) to HTTPS, optionally with token."""
    import re
    # git@github.com:org/repo.git → https://github.com/org/repo.git
    ssh_match = re.match(r'git@github\.com:([\w.\-]+/[\w.\-]+?)(?:\.git)?$', github_url)
    if ssh_match:
        path = ssh_match.group(1)
    else:
        # Already HTTPS — strip existing credentials
        https_match = re.match(r'https://(?:[^@]+@)?github\.com/([\w.\-]+/[\w.\-]+?)(?:\.git)?$', github_url)
        path = https_match.group(1) if https_match else None

    if not path:
        return github_url  # unrecognized format, return as-is

    if token:
        return f"https://{token}@github.com/{path}.git"
    return f"https://github.com/{path}.git"


def _gh_org_repo(github_url: str) -> str:
    m = re.search(r'github\.com[:/]([\w.\-]+/[\w.\-]+?)(?:\.git)?$', github_url)
    return m.group(1) if m else ""


def _enable_push(project_dir: Path, github_url: str, slug: str, token: str) -> None:
    """Give the project's container a SCOPED git-push capability: register its
    {slug}-deploy key as a write deploy key on THIS repo only, point the repo at
    an SSH remote, and pin git to the per-project key via core.sshCommand. The key
    is a deploy key on this repo alone, so the container cannot push anywhere else."""
    org_repo = _gh_org_repo(github_url)
    pub_path = SSH_DIR / f"{slug}-deploy.pub"
    if not org_repo or not pub_path.exists():
        print(f"      push: skipped (org_repo={org_repo or '?'}, key={'ok' if pub_path.exists() else 'missing'})")
        return

    # 1. Register the deploy key (write) — idempotent.
    if token:
        body = json.dumps({"title": f"viko-{slug}", "key": pub_path.read_text().strip(),
                           "read_only": False}).encode()
        req = urllib.request.Request(
            f"https://api.github.com/repos/{org_repo}/keys", data=body, method="POST",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        try:
            urllib.request.urlopen(req)
            print(f"      push: deploy key registered on {org_repo}")
        except urllib.error.HTTPError as e:
            msg = e.read().decode()
            print(f"      push: deploy key {'already present' if 'already in use' in msg else 'note ' + msg[:80]}")

    # 2. Point the repo at SSH + pin the per-project key + set a commit identity.
    ssh_url = f"git@github.com:{org_repo}.git"
    for args in (["remote", "set-url", "origin", ssh_url],
                 ["config", "core.sshCommand", CORE_SSH_CMD],
                 ["config", "user.name", "Viko"],
                 ["config", "user.email", f"viko-{slug}@local"]):
        subprocess.run(["git", "-C", str(project_dir)] + args, capture_output=True)
    print(f"      push: repo -> {ssh_url} (scoped key, identity Viko)")


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
    parser.add_argument("--repo-subdir", default="",
                        help="Clone into {slug}/{subdir}/ instead of {slug}/ (multi-repo projects)")
    parser.add_argument("--vps-host", default="", help="VPS hostname or IP for this project")
    parser.add_argument("--vps-user", default="viko-exec", help="SSH username on the project VPS")
    parser.add_argument("--vps-port", default="22", help="SSH port on the project VPS (default 22)")
    parser.add_argument("--members", default="", help="Comma-separated phone numbers for DM access")
    args = parser.parse_args(args_in)

    slug = args.slug.lower().strip()
    group_jid = args.group_jid.strip()
    github_url = args.github_url.strip()
    repo_subdir = args.repo_subdir.strip()
    vps_host = args.vps_host.strip()
    vps_user = args.vps_user.strip()
    vps_port = args.vps_port.strip()
    member_phones = [p.strip().lstrip("+") for p in args.members.split(",") if p.strip()]

    # Resolve VIKO_PROJECTS_ROOT
    projects_root_str = _get_env_val(REPO_DIR / ".env", "VIKO_PROJECTS_ROOT")
    projects_root = Path(projects_root_str) if projects_root_str else REPO_DIR.parent
    project_dir = projects_root / slug / repo_subdir if repo_subdir else projects_root / slug

    print(f"\n=== Viko onboarding: {slug} ===")
    print(f"  Group JID : {group_jid}")
    print(f"  GitHub    : {github_url}")
    print(f"  Clone to  : {project_dir}")
    if repo_subdir:
        print(f"  Subdir    : {repo_subdir}")
    if vps_host:
        print(f"  VPS host  : {vps_host}")
    if member_phones:
        print(f"  DM access : {', '.join(member_phones)}")

    # ── 1. Clone or pull repo via HTTPS + GITHUB_TOKEN ───────────────────────
    print("\n[1/4] Repository...")
    github_token = _get_env_val(REPO_DIR / ".env", "GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    clone_url = _to_https_url(github_url, github_token)

    if (project_dir / ".git").exists():
        # Pull from the tokenized URL explicitly — the stored remote is the clean
        # (token-less) URL, which can't authenticate non-interactively.
        result = subprocess.run(
            ["git", "-C", str(project_dir), "pull", "--ff-only", clone_url, "HEAD"],
            capture_output=True, text=True
        )
        print(f"      {(result.stdout or result.stderr).strip()}")
    else:
        project_dir.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", clone_url, str(project_dir)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"      ERROR: {result.stderr.strip()}")
            sys.exit(1)
        # Set remote back to clean HTTPS URL (without token in URL)
        clean_url = _to_https_url(github_url, "")
        subprocess.run(["git", "-C", str(project_dir), "remote", "set-url", "origin", clean_url],
                       capture_output=True)
        print(f"      Cloned to {project_dir}")

    # ── 2. Create context.md and steps.md stubs ───────────────────────────────
    print("\n[2/4] Project context stubs...")
    context_dir = REPO_DIR / "projects" / slug
    context_dir.mkdir(parents=True, exist_ok=True)

    # Inject the wizard-gathered data so Viko-Project starts informed. Idempotent
    # and accumulating: multi-repo onboarding calls add-project.py once per repo,
    # so each call appends its repo line; Info/Server/Members are written once.
    context_file = context_dir / "context.md"
    repo_label = repo_subdir or slug
    repo_line = f"- `{repo_label}`: {github_url}"
    server_line = f"{vps_user}@{vps_host}:{vps_port}" if vps_host else "Lokal (tanpa SSH)"
    members_line = ", ".join(member_phones) if member_phones else "(dibaca otomatis dari grup)"
    # Owner identity so Viko-Project knows WHO authorizes execution and can greet them
    # by name. The bridge stamps [CTX caller=owner] on the owner's messages; this line
    # lets the agent map that to a name + number instead of treating the owner as a stranger.
    owner_name = _get_env_val(REPO_DIR / ".env", "VIKO_OWNER_NAME") or os.environ.get("VIKO_OWNER_NAME", "")
    owner_number = _get_env_val(REPO_DIR / ".env", "WHATSAPP_OWNER_NUMBER") or os.environ.get("WHATSAPP_OWNER_NUMBER", "")
    owner_line = (
        f"{owner_name} ({owner_number})" if owner_name and owner_number
        else owner_number or owner_name or "(set WHATSAPP_OWNER_NUMBER / VIKO_OWNER_NAME)"
    )

    if context_file.exists():
        text = context_file.read_text()
        if repo_line not in text:
            if "## Repos\n" in text:
                text = text.replace("## Repos\n", f"## Repos\n{repo_line}\n", 1)
            else:
                text += f"\n## Repos\n{repo_line}\n"
            context_file.write_text(text)
            print(f"      context.md: added repo {repo_label}")
        else:
            print("      context.md: repo already listed")
    else:
        context_file.write_text(
            f"# Project: {slug}\n\n"
            f"## Info\n"
            f"- WA Group JID: {group_jid}\n"
            f"- Owner: {owner_line} — yang authorize eksekusi (deploy/infra/ops destruktif)\n"
            f"- Server: {server_line}\n"
            f"- Members: {members_line}\n"
            f"- Onboarded: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"## Repos\n{repo_line}\n\n"
            f"## Stack\n(Scan codebase dulu — jalankan: `ls {project_dir}/` atau `cat {project_dir}/package.json`)\n\n"
            f"## Notes\n(Tambahkan konteks project di sini)\n"
        )
        print("      Created context.md")

    steps_file = context_dir / "steps.md"
    if not steps_file.exists():
        steps_file.write_text(f"# Steps: {slug}\n\n## Active Tasks\n(Belum ada — tambahkan saat mulai kerja)\n")
        print("      Created steps.md")
    else:
        print("      steps.md exists, skipping.")

    # ── 3. Spawn isolated Hermes container for this project ───────────────────
    print("\n[3/4] Spawning Hermes instance...")
    spawn_cmd = [sys.executable, str(REPO_DIR / "scripts" / "spawn-hermes.py"), slug, group_jid]
    if vps_host:
        spawn_cmd += ["--vps-host", vps_host]
    if vps_user and vps_user != "viko-exec":
        spawn_cmd += ["--vps-user", vps_user]
    if vps_port and vps_port != "22":
        spawn_cmd += ["--vps-port", vps_port]
    result = subprocess.run(spawn_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR spawning Hermes: {result.stderr}")
        sys.exit(1)

    # ── 3b. Enable scoped git push for the container (deploy key + SSH remote) ─
    _enable_push(project_dir, github_url, slug, github_token)

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
    print("\nLangkah Viko berikutnya:")
    print(f"  1. Scan codebase: ls {project_dir}/ dan baca file utama")
    print(f"  2. Update {context_dir}/context.md dengan stack dan info project")
    print("  3. Restart hermes (admin instance) jika WHATSAPP_ALLOWED_USERS diubah:")
    print("     cd ~/projects/viko-agent && docker compose --profile full up -d --force-recreate hermes")
    print("  (spawn-hermes.py output above shows status of isolated Hermes instance)")


if __name__ == "__main__":
    main()
