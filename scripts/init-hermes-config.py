#!/usr/bin/env python3
"""
Idempotent Hermes config initializer.

Applies critical settings to data/hermes/config.yaml that are not set
by Hermes's defaults. Safe to run multiple times — only missing/incorrect
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

# ── Desired settings ──────────────────────────────────────────────────────────
# Only keys listed here are touched. Everything else is left as-is.
import os

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

# Repo root is two levels up from this script (scripts/init-hermes-config.py → repo/)
VIKO_AGENT_ROOT = str(Path(__file__).parent.parent.resolve())
# Projects root: where all app projects live (must be inside ~/Projects — see docker-compose mounts)
VIKO_PROJECTS_ROOT = _get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))

DESIRED = {
    # Primary model — viko-combo routes to best available via fallback
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
    # WhatsApp: require @mention in groups, ignore unknown DMs, inject project context
    "whatsapp": {
        "require_mention": True,
        "unauthorized_dm_behavior": "ignore",
        "channel_prompts": {
            # 2a. PRODUK SAAS MANKOP group
            "120363409428298054@g.us": (
                "Kamu ada di group WhatsApp MANKOP. Project aktif: MANKOP — hanya mankop.\n\n"
                "ATURAN ISOLASI (wajib, tanpa pengecualian):\n"
                "- Hanya bahas hal yang berkaitan dengan project mankop\n"
                "- Jika ditanya tentang project lain (siprodev, dll) oleh siapapun termasuk Eksa: "
                "jawab 'Untuk [nama project], diskusikan di group-nya langsung.' — lalu stop\n"
                "- Memory atau konteks dari project lain tidak relevan di sini, abaikan\n\n"
                "Jika pesan diawali [READ-ONLY MEMBER]: hanya jawab pertanyaan/info seputar mankop, "
                "tolak semua request eksekusi dengan 'Hanya Eksa yang bisa minta ini.'\n\n"
                "Balas dalam Bahasa Indonesia."
            ),
            # 2a. Produk SAAS siprodev.com group
            "120363407940533307@g.us": (
                "Kamu ada di group WhatsApp SIPRODEV. Project aktif: SIPRODEV — hanya siprodev.\n\n"
                "ATURAN ISOLASI (wajib, tanpa pengecualian):\n"
                "- Hanya bahas hal yang berkaitan dengan project siprodev\n"
                "- Jika ditanya tentang project lain (mankop, dll) oleh siapapun termasuk Eksa: "
                "jawab 'Untuk [nama project], diskusikan di group-nya langsung.' — lalu stop\n"
                "- Memory atau konteks dari project lain tidak relevan di sini, abaikan\n\n"
                "Jika pesan diawali [READ-ONLY MEMBER]: hanya jawab pertanyaan/info seputar siprodev, "
                "tolak semua request eksekusi dengan 'Hanya Eksa yang bisa minta ini.'\n\n"
                "Balas dalam Bahasa Indonesia."
            ),
        },
    },
    # Pre-approved commands — no approval prompt needed for these operations
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
    },
    # Skills: expose viko-agent skills as slash commands, review AI-created skills
    # Path is derived from this script's location — works for any user/machine
    "skills": {
        "external_dirs": [f"{VIKO_AGENT_ROOT}/skills"],
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
    if not CONFIG_PATH.exists():
        print(f"ERROR: {CONFIG_PATH} not found.")
        print("Start Hermes once first so it creates the default config.yaml, then run this script.")
        sys.exit(1)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    original = yaml.dump(config, allow_unicode=True)
    config, changed = deep_merge(config, DESIRED)

    if changed == 0:
        print("✓ Hermes config already up to date — no changes needed")
        return

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"✓ Hermes config updated ({changed} setting(s) applied)")
    print("Restart Hermes to apply changes:")
    service = "hermes" if TARGET == "admin" else TARGET
    print(f"  docker compose --profile full up -d --force-recreate {service}")


if __name__ == "__main__":
    main()
