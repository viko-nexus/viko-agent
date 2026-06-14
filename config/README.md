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
# Copy secrets template and fill in keys
cp .env.example .env

# Build Hermes image (required once, and after patch changes)
docker compose build hermes

# Start everything
docker compose --profile full up -d
# → 9router starts → 9router-init creates combos → Hermes starts

# View logs
docker compose logs -f hermes
docker compose logs -f 9router

# Rebuild + restart Hermes after patch changes
docker compose build hermes && docker compose --profile full up -d --force-recreate hermes
```

## After a Reset (data/ wiped)

### 9router reset
Combos are recreated **automatically** by `9router-init` on next `docker compose up`.
API keys must be re-added manually via dashboard:
```
http://localhost:20128 → Providers → Claude Code (OAuth) + Groq
```

### Hermes config reset
```bash
# 1. Start Hermes once (creates fresh config.yaml)
docker compose --profile full up -d

# 2. Apply critical settings
python3 scripts/init-hermes-config.py

# 3. Restart
docker compose --profile full up -d --force-recreate hermes
```

### WhatsApp re-pair
```bash
docker exec -u root viko-hermes chown -R hermes:hermes /opt/hermes/scripts/whatsapp-bridge
docker exec -it -u hermes viko-hermes hermes whatsapp
```

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
    ├── memory_store.db       ← Holographic memory (SQLite)
    └── platforms/
        └── whatsapp/
            └── session/creds.json  ← WhatsApp session (re-pair if deleted)
```

## Security

- All secrets in `.env` — never committed to git
- `data/` gitignored — contains credentials, session tokens, API keys
- `.env.example` documents required variables without values
- 9router API key (`OPENAI_API_KEY` in `.env`) is scoped to local 9router only
