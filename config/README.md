# Config

Infrastructure configuration for the Viko agent stack.
All services run in Docker. Compose file: `../docker-compose.yml`

## Services

| Service | Role | Port | Profile |
|---------|------|------|---------|
| ChromaDB | Vector DB for persistent memory | 8000 | default |
| 9router | LLM gateway with provider fallback | 20128 | `gateway`, `full` |
| Hermes | AI orchestrator (brain) | 9119 | `full` |

## Quick Start

```bash
# Copy secrets template and fill in keys
cp .env.example .env

# Start everything
docker compose --profile full up -d

# Start only gateway (9router + ChromaDB, no Hermes)
docker compose --profile gateway up -d

# View logs
docker compose logs -f hermes
docker compose logs -f 9router

# Restart a single service
docker compose restart hermes

# Rebuild Hermes image after code/patch changes
docker compose build hermes && docker compose --profile full up -d hermes
```

## Data (Bind Mounts)

All persistent state lives in `../data/` — gitignored, survives container restarts.

```
data/
├── 9router/         ← 9router database (provider credentials, API keys, usage)
│   └── db/data.sqlite
└── hermes/          ← Hermes runtime state
    ├── config.yaml  ← ⚠️  CRITICAL — see section below
    ├── .env         ← Hermes-specific env (WhatsApp allowlist, etc.)
    ├── sessions/    ← Active conversation sessions
    └── platforms/
        └── whatsapp/
            └── session/creds.json  ← WhatsApp session (re-pair if deleted)
```

## Hermes config.yaml (Critical — Not in Git)

`data/hermes/config.yaml` is gitignored but must be configured correctly.
If `data/` is ever wiped, recreate this section:

```yaml
model:
  default: anthropic/claude-sonnet-4-6
  provider: openai        # Use OpenAI-compatible format (9router speaks OpenAI)
  base_url: http://viko-9router:20128/v1
providers:
  openai:
    api_key: <OPENAI_API_KEY from .env>   # 9router API key, not OpenAI's
    base_url: http://viko-9router:20128/v1
```

**Why `provider: openai` with an Anthropic model?**
9router exposes an OpenAI-compatible API. Hermes sends requests in OpenAI format
to 9router, which then routes them to the real Anthropic API. The model prefix
`anthropic/` tells 9router which backend provider to use.

## LLM Routing (9router)

9router routes by model name prefix:

| Priority | Provider | Prefix | Backend |
|----------|----------|--------|---------|
| 1 | viko-anthropic | `anthropic/` | api.anthropic.com |
| 2 | viko-groq | `groq/` | api.groq.com |

Configured via 9router dashboard at `http://localhost:20128`.
Provider API keys (Anthropic, Groq) are stored in `data/9router/db/data.sqlite` —
configure once via dashboard, persists across restarts.

## WhatsApp Setup

WhatsApp credentials survive in `data/hermes/platforms/whatsapp/session/creds.json`.
If lost, re-pair:

```bash
# Fix permissions first (only needed once after fresh build)
docker exec -u root viko-hermes chown -R hermes:hermes /opt/hermes/scripts/whatsapp-bridge

# Pair WhatsApp (interactive — must run in your terminal, not a script)
docker exec -it -u hermes viko-hermes hermes whatsapp
```

Scan QR with the **bot's dedicated number** (not your personal number).
Allowed users are configured in `data/hermes/.env` as `WHATSAPP_ALLOWED_USERS`.

## Security

- All secrets in `.env` — never committed to git
- `data/` gitignored — contains credentials, session tokens, API keys
- `.env.example` documents required variables without values
- 9router API key (`OPENAI_API_KEY` in `.env`) is scoped to local 9router only
