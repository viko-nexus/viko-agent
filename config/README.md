# Config

Infrastructure configuration for the Viko agent stack.
All services run in Docker. Compose file: `../docker-compose.yml`

## Services

| Service | Role | Port | Profile |
|---------|------|------|---------|
| 9router | LLM gateway with provider fallback | 20128 | `gateway`, `full` |
| 9router-init | One-time combo setup (auto-exits) | — | `gateway`, `full` |
| Hermes | AI orchestrator (brain) | 9119 | `full` |

## Quick Start

```bash
# 1. Copy secrets template and fill in values
cp .env.example .env

# 2. Build Hermes image (required once, and after patch changes)
docker compose build hermes

# 3. Start everything
docker compose --profile full up -d
# → 9router starts → 9router-init creates combos → Hermes starts

# 4. Apply critical Hermes config settings
python3 scripts/init-hermes-config.py
docker compose --profile full up -d --force-recreate hermes

# View logs
docker compose logs -f hermes
docker compose logs -f 9router
```

## After a Reset (data/ wiped)

### 9router reset
Combos are recreated **automatically** by `9router-init` on next `docker compose up`.
API keys must be re-added manually via dashboard:
```
http://localhost:20128 → Providers → Claude Code (OAuth) + Groq
```
Re-enable Caveman compression: **Endpoint → Compress LLM output → ON (Full)**.

### Hermes config reset
```bash
# 1. Start Hermes once (creates fresh config.yaml)
docker compose --profile full up -d

# 2. Apply critical settings (model routing, timezone, skills, WhatsApp, etc.)
python3 scripts/init-hermes-config.py

# 3. Restart to apply
docker compose --profile full up -d --force-recreate hermes
```

### Hermes image rebuild
Required after changes to `Dockerfile.hermes` or any file in `patches/`:
```bash
docker compose build hermes
docker compose --profile full up -d --force-recreate hermes
```

### WhatsApp re-pair
```bash
docker exec -u root viko-hermes chown -R hermes:hermes /opt/hermes/scripts/whatsapp-bridge
docker exec -it -u hermes viko-hermes hermes whatsapp
```
Scan QR with the bot's dedicated number.

## Full Documentation

| Topic | Doc |
|-------|-----|
| 9router combos + routing | [docs/9router/setup.md](../docs/9router/setup.md) |
| Hermes config + patches | [docs/hermes/setup.md](../docs/hermes/setup.md) |
| Init scripts | [scripts/](../scripts/) |

## Data (Bind Mounts)

All persistent state lives in `../data/` — gitignored, survives container restarts.

```
data/
├── 9router/
│   └── db/data.sqlite       ← combos, API keys, usage (auto-restored by 9router-init)
└── hermes/
    ├── config.yaml           ← ⚠️  critical — restore with scripts/init-hermes-config.py
    ├── SOUL.md               ← runtime persona (not in git — see soul/identity.md)
    ├── cron/jobs.json        ← cron job definitions
    ├── scripts/              ← cron helper scripts (e.g., cleanup-media.sh)
    ├── memory_store.db       ← Holographic memory (SQLite, local only)
    └── platforms/
        └── whatsapp/
            └── session/creds.json  ← WhatsApp session (re-pair if deleted)
```

## Security

- All secrets in `.env` — never committed to git
- `data/` gitignored — contains credentials, session tokens, API keys
- `projects/` gitignored (except `projects/viko-agent/`) — contains private client info
- `.env.example` documents all required variables without values
- `VIKO_PROJECTS_ROOT` in `.env` defines the local projects path — not hardcoded anywhere
