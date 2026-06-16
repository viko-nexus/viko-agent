#!/usr/bin/env python3
"""
Spawn a new isolated Hermes container for a project.

Run on trahku as viko user:
  python3 ~/projects/viko-agent/scripts/spawn-hermes.py <slug> <group_jid>

What this does:
  1. Allocate next available port (starts at 8101)
  2. Create data/hermes-{slug}/ with isolated config.yaml + .env
  3. Run docker run -d to start the container
  4. Update data/bridge/routing.json atomically (bridge hot-reloads in <1s)
  5. Print the allocated port

Port allocation: scans routing.json for highest used port, increments.
Container name: viko-hermes-{slug}
Docker network: viko_default (created by docker compose)
Image: viko-viko-hermes (built by docker compose build hermes)
"""

import sys
import os
import json
import subprocess
import yaml
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.resolve()
ROUTING_FILE = REPO_DIR / "data" / "bridge" / "routing.json"
MIN_PORT = 8101
HERMES_IMAGE = "viko-viko-hermes"


def _read_env() -> dict:
    env_path = REPO_DIR / ".env"
    result = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def load_routing() -> dict:
    if ROUTING_FILE.exists():
        try:
            return json.loads(ROUTING_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_routing(routing: dict) -> None:
    ROUTING_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ROUTING_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(routing, indent=2))
    tmp.rename(ROUTING_FILE)


def next_port(routing: dict) -> int:
    used = set(int(v) for v in routing.values() if str(v).isdigit())
    port = MIN_PORT
    while port in used:
        port += 1
    return port


def _build_project_config(slug: str, group_jid: str, env: dict) -> dict:
    ninerouter_url = env.get("OPENAI_BASE_URL", "http://viko-9router:20128/v1")
    ninerouter_key = env.get("OPENAI_API_KEY", "")

    prompt = (
        f"Kamu ada di group WhatsApp {slug.upper()}. Project aktif: {slug.upper()} — hanya {slug}.\n\n"
        f"ATURAN ISOLASI (wajib, tanpa pengecualian):\n"
        f"- Hanya bahas hal yang berkaitan dengan project {slug}\n"
        f"- Jika ditanya tentang project lain: jawab 'Untuk [nama project], diskusikan di group-nya langsung.' — lalu stop\n"
        f"- Memory atau konteks dari project lain tidak relevan di sini, abaikan\n\n"
        f"Siapapun boleh bertanya — hanya Eksa yang bisa authorize eksekusi (deploy, kode, infra).\n"
        f"Jika pesan diawali [READ-ONLY MEMBER]: hanya jawab pertanyaan/info, "
        f"tolak eksekusi dengan 'Hanya Eksa yang bisa minta ini.'\n\n"
        f"Balas dalam Bahasa Indonesia."
    )

    return {
        "model": {
            "default": "viko-combo",
            "provider": "openai",
            "base_url": ninerouter_url,
        },
        "providers": {
            "openai": {"api_key": ninerouter_key, "base_url": ninerouter_url}
        },
        "web": {"extract_backend": "https://r.jina.ai/"},
        "whatsapp": {
            "require_mention": True,
            "unauthorized_dm_behavior": "ignore",
            "channel_prompts": {group_jid: prompt},
        },
        "skills": {
            "external_dirs": ["/opt/viko/skills"],
            "guard_agent_created": True,
        },
        "terminal": {
            "cwd": env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))
        },
        "timezone": "Asia/Makassar",
        "kanban": {"auto_decompose": False, "max_in_progress_per_profile": 1},
        "display": {
            "language": "id",
            "runtime_footer": {"enabled": False, "fields": ["model", "context_pct"]},
        },
        "auxiliary": {
            "vision": {
                "provider": "openai",
                "model": "cc/claude-sonnet-4-6",
                "base_url": ninerouter_url,
                "api_key": ninerouter_key,
                "timeout": 120,
                "extra_body": {},
                "download_timeout": 30,
            },
            "compression": {
                "provider": "openai",
                "model": "cc/claude-haiku-4-5-20251001",
                "base_url": ninerouter_url,
                "api_key": ninerouter_key,
                "timeout": 120,
                "extra_body": {},
            },
        },
        "memory": {"provider": "holographic"},
        "command_allowlist": [
            "script execution via -e/-c flag",
            "script execution via heredoc",
            "docker restart/stop/kill (container lifecycle)",
            "hermes kanban",
            "execute_code",
            "overwrite system file via redirection",
            f"git clone to VIKO_PROJECTS_ROOT (project onboarding)",
            f"ssh {slug}-vps (deploy to {slug} VPS)",
        ],
    }


def create_hermes_data_dir(slug: str, port: int, group_jid: str, env: dict) -> Path:
    data_dir = REPO_DIR / "data" / f"hermes-{slug}"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Write .env
    (data_dir / ".env").write_text(
        f"WHATSAPP_MODE=bot\n"
        f"WHATSAPP_RELAY_MODE=true\n"
        f"WHATSAPP_RELAY_TARGET=http://viko-hermes-admin:3000\n"
        f"WHATSAPP_PORT_FILTER={port}\n"
        f"WHATSAPP_ENABLED=true\n"
        f"WHATSAPP_HOME_CHANNEL={env.get('WHATSAPP_HOME_CHANNEL', '')}\n"
    )

    # Write config.yaml
    config = _build_project_config(slug, group_jid, env)
    (data_dir / "config.yaml").write_text(
        yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
    )

    return data_dir


def spawn_container(slug: str, port: int, data_dir: Path, env: dict) -> str:
    projects_root = env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))
    home = str(Path.home())
    uid = env.get("HERMES_UID", "1000")
    gid = env.get("HERMES_GID", "1000")
    ninerouter_key = env.get("OPENAI_API_KEY", "")
    home_channel = env.get("WHATSAPP_HOME_CHANNEL", "")

    cmd = [
        "docker", "run", "-d",
        "--name", f"viko-hermes-{slug}",
        "--restart", "unless-stopped",
        "--network", "viko_default",
        "-p", f"127.0.0.1:{port + 900}:9119",
        # Volumes
        "-v", f"{data_dir}:/opt/data",
        "-v", f"{projects_root}:{projects_root}:rw",
        "-v", f"{home}/.viko/ssh:/opt/data/.ssh:ro",
        "-v", f"{home}/.viko/ssh:/opt/data/home/.ssh:ro",
        "-v", f"{REPO_DIR}/hooks:/opt/data/hooks:ro",
        "-v", f"{REPO_DIR}/mcp-servers:/opt/viko/mcp-servers:ro",
        "-v", f"{REPO_DIR}/skills:/opt/viko/skills:ro",
        # Environment
        "-e", f"HERMES_UID={uid}",
        "-e", f"HERMES_GID={gid}",
        "-e", f"OPENAI_BASE_URL=http://viko-9router:20128/v1",
        "-e", f"OPENAI_API_KEY={ninerouter_key}",
        "-e", f"WHATSAPP_HOME_CHANNEL={home_channel}",
        "-e", f"WHATSAPP_RELAY_MODE=true",
        "-e", f"WHATSAPP_RELAY_TARGET=http://viko-hermes-admin:3000",
        "-e", f"WHATSAPP_PORT_FILTER={port}",
        "-e", f"NINEROUTER_URL=http://viko-9router:20128",
        "-e", f"NINEROUTER_KEY={ninerouter_key}",
        "-e", f"VIKO_PROJECTS_ROOT={projects_root}",
        "-e", f"SSL_CERT_FILE=/opt/hermes/.venv/lib/python3.13/site-packages/certifi/cacert.pem",
        "-e", f"REQUESTS_CA_BUNDLE=/opt/hermes/.venv/lib/python3.13/site-packages/certifi/cacert.pem",
        "-e", f"HERMES_DASHBOARD=true",
        "-e", f"HERMES_DASHBOARD_INSECURE=true",
        "-e", f"HERMES_DASHBOARD_HOST=127.0.0.1",
        "-e", f"HERMES_DASHBOARD_PORT=9119",
        HERMES_IMAGE,
        "gateway", "run",
    ]

    # Remove existing container if present (idempotent)
    subprocess.run(
        ["docker", "rm", "-f", f"viko-hermes-{slug}"],
        capture_output=True
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    slug = sys.argv[1].lower().strip()
    group_jid = sys.argv[2].strip()

    env = _read_env()
    routing = load_routing()

    if group_jid in routing:
        port = int(routing[group_jid])
        print(f"✓ {slug} already routed to port {port} — no changes needed.")
        return

    port = next_port(routing)
    print(f"\n=== Spawning Hermes-{slug} on port {port} ===")

    data_dir = create_hermes_data_dir(slug, port, group_jid, env)
    print(f"  ✓ Config created at {data_dir}")

    container_id = spawn_container(slug, port, data_dir, env)
    print(f"  ✓ Container started: {container_id[:12]}")

    routing[group_jid] = port
    save_routing(routing)
    print(f"  ✓ routing.json updated (bridge hot-reloads automatically)")

    print(f"\nHermes-{slug} running on port {port}")
    print(f"Dashboard: http://localhost:{port + 900}")
    print(f"SPAWN_COMPLETE port={port}")


if __name__ == "__main__":
    main()
