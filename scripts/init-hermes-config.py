#!/usr/bin/env python3
"""
Idempotent Hermes config initializer.

Applies critical settings to data/hermes/config.yaml that are not set
by Hermes's defaults. Safe to run multiple times - only missing/incorrect
keys are changed.

Usage:
  python3 scripts/init-hermes-config.py
  python3 scripts/init-hermes-config.py /custom/path/to/config.yaml
  python3 scripts/init-hermes-config.py --target admin

  # --target admin: configure data/hermes-admin/ (for Option B multi-instance setup)

Run this after:
  - First-time setup (data/hermes/ initialized by Hermes, then apply overrides)
  - data/hermes/ wipe (Hermes creates fresh config.yaml on next start, then run this)

Hermes must have started at least once to create the config.yaml before this runs.
"""

import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml

TARGET = "admin"
CONFIG_PATH = Path(__file__).parent.parent / "data" / "hermes" / "config.yaml"

if len(sys.argv) > 1 and sys.argv[1] == "--target" and len(sys.argv) > 2:
    TARGET = sys.argv[2]
    CONFIG_PATH = Path(__file__).parent.parent / "data" / f"hermes-{TARGET}" / "config.yaml"
elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
    CONFIG_PATH = Path(sys.argv[1])

# ?? Desired settings ??????????????????????????????????????????????????????????
# Only keys listed here are touched. Everything else is left as-is.

def _read_env_file() -> dict:
    """Read key=value pairs from .env file in repo root."""
    env_path = Path(__file__).parent.parent / ".env"
    result = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result

_env = _read_env_file()

def _get(key: str, default: str = "") -> str:
    return _env.get(key) or os.environ.get(key, default)

NINEROUTER_API_KEY = _get("OPENAI_API_KEY")
NINEROUTER_URL = _get("OPENAI_BASE_URL", "http://viko-9router:20128/v1")

# Repo root is two levels up from this script (scripts/init-hermes-config.py -> repo/)
VIKO_AGENT_ROOT = str(Path(__file__).parent.parent.resolve())
# Projects root: where all app projects live (must be inside ~/Projects - see docker-compose mounts)
VIKO_PROJECTS_ROOT = _get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))

DESIRED = {
    # Primary model - viko-combo routes to best available via fallback
    "model": {
        "default": "viko-combo",
        "provider": "openai",
        "base_url": NINEROUTER_URL,
    },
    "providers": {
        "openai": {
            "api_key": NINEROUTER_API_KEY,
            "base_url": NINEROUTER_URL,
        }
    },
    # Web URL extraction via Jina Reader (free, no API key)
    "web": {
        "extract_backend": "https://r.jina.ai/",
    },
    # WhatsApp: require @mention in groups, ignore unknown DMs
    # channel_prompts.default applies to all chats - safe to set here.
    # Per-group JID prompts are deployment-specific -> configure directly in config.yaml.
    "whatsapp": {
        # Admin sees DMs + unregistered groups -> respond to any message (no @mention
        # gate). BUT this same override also runs (via cont-init 04) inside each PROJECT
        # container, which lives in a busy group chat and must ONLY answer when addressed.
        # VIKO_PROJECT_SLUG is set only in project containers -> gate on @mention there so
        # Viko doesn't butt into every group message. Without this it clobbers the
        # require_mention:True that spawn-hermes.py writes for projects.
        "require_mention": bool(os.environ.get("VIKO_PROJECT_SLUG")),
        "unauthorized_dm_behavior": "ignore",
        "channel_prompts": {
            "default": "Balas dalam Bahasa Indonesia. Jika pengguna menulis dalam English, balas dalam English. Jawa/Sunda -> Indonesia.",
        },
    },
    # Pre-approved commands - no approval prompt needed for these operations
    "command_allowlist": [
        "script execution via -e/-c flag",
        "script execution via heredoc",
        "docker restart/stop/kill (container lifecycle)",
        "hermes kanban",
        "execute_code",
        "overwrite system file via redirection",
        "git clone to VIKO_PROJECTS_ROOT (project onboarding)",
        "rm -rf in /tmp (clone verification during onboarding)",
        "python3 scripts/add-project.py (project onboarding)",
        "python3 scripts/allow-member.py (add member to DM allowlist)",
        "ssh viko-vps docker compose (remote hermes restart)",
        "python3 scripts/spawn-hermes.py (spawn isolated project hermes container)",
        "python3 scripts/setup-keys.py (generate SSH keys + GitHub deploy key for onboarding)",
        "ssh viko-vps python3 scripts/spawn-hermes.py (remote project hermes spawn)",
        "ssh viko-vps python3 scripts/setup-keys.py (remote key setup)",
        "curl https://api.github.com/repos (GitHub deploy key API)",
    ],
    # Display: language + runtime footer (model, context %)
    "display": {
        "language": "id",
        "runtime_footer": {
            "enabled": False,
            "fields": ["model", "context_pct"],
        },
        "platforms": {
            "whatsapp": {
                "tool_progress": "off",
                "interim_assistant_messages": False,
                "streaming": False,
            }
        },
    },
    # Skills: expose shared skills + admin-specific skills (onboarding)
    # Paths derived from script location - works for any user/machine
    "skills": {
        "external_dirs": [f"{VIKO_AGENT_ROOT}/skills", f"{VIKO_AGENT_ROOT}/admin/skills"],
        "guard_agent_created": True,
    },
    # Terminal starts in projects root so Viko can cd into any project
    "terminal": {
        "cwd": VIKO_PROJECTS_ROOT,
    },
    # Timezone for correct cron scheduling
    "timezone": "Asia/Makassar",
    # Kanban: manual control (no auto-decompose), one task at a time
    "kanban": {
        "auto_decompose": False,
        "max_in_progress_per_profile": 1,
    },
    # Auxiliary models: vision via Sonnet, compression via Haiku (cheaper)
    "auxiliary": {
        "vision": {
            "provider": "openai",
            "model": "cc/claude-sonnet-4-6",
            "base_url": NINEROUTER_URL,
            "api_key": NINEROUTER_API_KEY,
            "timeout": 120,
            "extra_body": {},
            "download_timeout": 30,
        },
        "compression": {
            "provider": "openai",
            "model": "cc/claude-haiku-4-5-20251001",
            "base_url": NINEROUTER_URL,
            "api_key": NINEROUTER_API_KEY,
            "timeout": 120,
            "extra_body": {},
        },
    },
}


def deep_merge(base: dict, override: dict) -> tuple[dict, int]:
    """Merge override into base. Returns (merged_dict, changed_count)."""
    changed = 0
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _, sub_changed = deep_merge(base[key], value)
            changed += sub_changed
        else:
            if base.get(key) != value:
                base[key] = value
                changed += 1
    return base, changed


def main():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        # Hermes hasn't created config.yaml yet - this happens when the script runs
        # from cont-init, which fires BEFORE the gateway's first start. Create the
        # file from our overrides; Hermes fills every other key from its defaults
        # (the config dataclasses use from_dict + default_factory), and it won't
        # overwrite an existing config.yaml on start. This makes the overrides apply
        # on a fresh setup instead of being silently skipped.
        print(f"{CONFIG_PATH} not found - creating it from Viko overrides.")
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        config = {}

    config, changed = deep_merge(config, DESIRED)

    if changed == 0:
        print("OK Hermes config already up to date - no changes needed")
        return

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"OK Hermes config updated ({changed} setting(s) applied)")
    print("Restart Hermes to apply changes:")
    service = "hermes" if TARGET == "admin" else TARGET
    print(f"  docker compose --profile full up -d --force-recreate {service}")


if __name__ == "__main__":
    main()
