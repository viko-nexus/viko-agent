#!/usr/bin/env python3
"""
Idempotent Hermes config initializer.

Applies critical settings to data/hermes/config.yaml that are not set
by Hermes's defaults. Safe to run multiple times — only missing/incorrect
keys are changed.

Usage:
  python3 scripts/init-hermes-config.py
  python3 scripts/init-hermes-config.py /custom/path/to/config.yaml

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

CONFIG_PATH = Path(__file__).parent.parent / "data" / "hermes" / "config.yaml"

if len(sys.argv) > 1:
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
    # Vision: use Claude Sonnet via 9router for image analysis
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
    },
    # WhatsApp: require @mention in groups, inject project context per channel
    "whatsapp": {
        "require_mention": True,
        "channel_prompts": {
            # 2a. PRODUK SAAS MANKOP group
            "120363409428298054@g.us": (
                "You are in the Mankop project group (2a. PRODUK SAAS MANKOP). "
                "Active project: mankop. Load mankop project context before responding. "
                "Anyone in this group can ask questions — only Eksa can authorize execution."
            ),
        },
    },
    # Language for Hermes UI
    "display": {
        "language": "id",
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
    print("  docker compose --profile full up -d --force-recreate hermes")


if __name__ == "__main__":
    main()
