#!/usr/bin/env python3
"""
Phase 1 of project onboarding: generate SSH keys, add GitHub deploy key.

Run via Admin Hermes (via SSH to trahku):
  python3 ~/projects/viko-agent/scripts/setup-keys.py <slug> <github_url> <vps_host>

What this does:
  1. Generate ed25519 keypair: ~/.viko/ssh/{slug}-deploy (+ .pub)
  2. Add deploy key to GitHub repo automatically (requires GITHUB_TOKEN env var)
     GITHUB_TOKEN = Classic PAT with 'repo' scope. Works for personal + org repos.
     Get from: github.com/settings/tokens → New classic token → scope: repo
  3. Update ~/.viko/ssh/config with SSH Host aliases ({slug}-github, {slug}-vps)
  4. Save onboarding state to data/bridge/onboarding-{slug}.json

If GITHUB_TOKEN not set: prints instructions for manual deploy key addition.
VPS host is optional — skip if no VPS yet.
"""

import sys
import os
import re
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.resolve()


def _get_ssh_dir() -> Path:
    ssh_dir = Path.home() / ".viko" / "ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    return ssh_dir


def generate_keypair(slug: str, ssh_dir: Path) -> tuple:
    """Generate ed25519 keypair. Returns (key_path_str, public_key_str). Idempotent."""
    key_path = ssh_dir / f"{slug}-deploy"
    if key_path.exists():
        pub = (ssh_dir / f"{slug}-deploy.pub").read_text().strip()
        print(f"  Key already exists: {key_path}")
        return str(key_path), pub

    subprocess.run([
        "ssh-keygen", "-t", "ed25519", "-N", "",
        "-C", f"viko-deploy-{slug}",
        "-f", str(key_path)
    ], check=True, capture_output=True)

    pub = (ssh_dir / f"{slug}-deploy.pub").read_text().strip()
    return str(key_path), pub


def _parse_github_url(github_url: str) -> tuple:
    """Parse github URL to (owner, repo). Returns (None, None) if not parseable."""
    match = re.search(r'github\.com[/:]([\w.\-]+)/([\w.\-]+?)(\.git)?$', github_url)
    if match:
        return match.group(1), match.group(2)
    return None, None


def github_add_deploy_key(github_url: str, slug: str, public_key: str, token: str) -> bool:
    """Add read-only deploy key to GitHub repo via REST API. Idempotent."""
    owner, repo = _parse_github_url(github_url)
    if not owner:
        print(f"  Could not parse GitHub URL: {github_url}")
        return False

    # Check existing keys first (idempotency)
    list_req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/keys",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    try:
        with urllib.request.urlopen(list_req, timeout=10) as resp:
            existing = json.loads(resp.read())
            key_part = public_key.split()[1] if len(public_key.split()) >= 2 else public_key
            for k in existing:
                if key_part in k.get("key", ""):
                    print(f"  Deploy key already exists on GitHub (id={k['id']})")
                    return True
    except Exception:
        pass  # proceed to add

    payload = json.dumps({
        "title": f"viko-deploy-{slug}",
        "key": public_key,
        "read_only": False,  # False = read+write, needed for git push in future
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/keys",
        data=payload,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 201
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if "already in use" in body or "key is already in use" in body:
            return True  # idempotent
        print(f"  GitHub API error {e.code}: {body[:300]}")
        return False


def _remove_ssh_host_block(text: str, host_name: str) -> str:
    """Remove a Host block from SSH config text."""
    import re
    return re.sub(
        rf'\nHost {re.escape(host_name)}\n(?:[ \t]+.*\n)*',
        '', text
    )


def update_ssh_config(slug: str, github_url: str, vps_host: str, ssh_dir: Path, vps_user: str = "viko-exec") -> None:
    """Add or update SSH Host aliases in ~/.viko/ssh/config."""
    config_path = ssh_dir / "config"
    existing = config_path.read_text() if config_path.exists() else ""

    owner, repo = _parse_github_url(github_url)
    updated = existing
    changes = []

    github_block = (
        f"\nHost {slug}-github\n"
        f"    HostName github.com\n"
        f"    User git\n"
        f"    IdentityFile ~/.viko/ssh/{slug}-deploy\n"
        f"    IdentitiesOnly yes\n"
        f"    StrictHostKeyChecking yes\n"
    )
    if owner:
        if f"Host {slug}-github" in updated:
            updated = _remove_ssh_host_block(updated, f"{slug}-github")
            changes.append(f"{slug}-github (updated)")
        else:
            changes.append(f"{slug}-github (new)")
        updated += github_block

    if vps_host:
        vps_block = (
            f"\nHost {slug}-vps\n"
            f"    HostName {vps_host}\n"
            f"    User {vps_user}\n"
            f"    IdentityFile ~/.viko/ssh/{slug}-deploy\n"
            f"    IdentitiesOnly yes\n"
            f"    StrictHostKeyChecking accept-new\n"
            f"    UserKnownHostsFile ~/.viko/ssh/known_hosts\n"
        )
        if f"Host {slug}-vps" in updated:
            updated = _remove_ssh_host_block(updated, f"{slug}-vps")
            changes.append(f"{slug}-vps (updated)")
        else:
            changes.append(f"{slug}-vps (new)")
        updated += vps_block

    if updated != existing:
        config_path.write_text(updated)
        print(f"  SSH config: {', '.join(changes)}")
    else:
        print(f"  SSH config already up to date for {slug}")


def save_onboarding_state(slug: str, state: dict) -> None:
    bridge_dir = REPO_DIR / "data" / "bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    (bridge_dir / f"onboarding-{slug}.json").write_text(json.dumps(state, indent=2))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    slug = sys.argv[1].lower().strip()
    github_url = sys.argv[2].strip()
    vps_host = sys.argv[3].strip() if len(sys.argv) > 3 else ""
    vps_user = sys.argv[4].strip() if len(sys.argv) > 4 else "viko-exec"
    github_token = os.environ.get("GITHUB_TOKEN", "")

    ssh_dir = _get_ssh_dir()

    print(f"\n=== Onboarding Phase 1: {slug} ===")

    print(f"\n[1/3] Generating SSH keypair...")
    key_path, public_key = generate_keypair(slug, ssh_dir)
    print(f"  ✓ Key: {key_path}")

    print(f"\n[2/3] GitHub deploy key...")
    github_ok = False
    if github_token:
        github_ok = github_add_deploy_key(github_url, slug, public_key, github_token)
        if github_ok:
            print(f"  ✓ Deploy key added to GitHub automatically")
        else:
            print(f"  ✗ GitHub API failed — will show manual instructions")
    else:
        print(f"  ✗ GITHUB_TOKEN not set — will show manual instructions")

    print(f"\n[3/3] SSH config...")
    update_ssh_config(slug, github_url, vps_host, ssh_dir, vps_user)

    # Save state for Phase 2
    save_onboarding_state(slug, {
        "slug": slug,
        "github_url": github_url,
        "vps_host": vps_host,
        "vps_user": vps_user,
        "public_key": public_key,
        "github_deploy_key_added": github_ok,
        "phase": 1,
    })

    # Output for Viko to relay to WA group
    print(f"\n{'='*50}")
    print(f"PHASE1_COMPLETE")
    print(f"VPS_KEY_REQUIRED={'true' if vps_host else 'false'}")
    print(f"{'='*50}")

    if github_ok:
        print(f"\n✓ GitHub deploy key: ditambahkan otomatis ke {github_url}")
    else:
        owner, repo = _parse_github_url(github_url)
        print(f"\n⚠ GitHub deploy key — tambahkan manual:")
        print(f"  URL: https://github.com/{owner}/{repo}/settings/keys/new")
        print(f"  Key:\n  {public_key}")

    if vps_host:
        print(f"\n⚠ VPS SSH key — satu langkah manual:")
        print(f"  Server: {vps_host}")
        print(f"  Jalankan di VPS:")
        print(f'  echo "{public_key}" >> ~/.ssh/authorized_keys')
        print(f"\nBalas 'done' setelah selesai.")


if __name__ == "__main__":
    main()
