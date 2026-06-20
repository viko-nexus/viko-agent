# CLAUDE.md — viko-agent Developer Guide

This file tells Claude Code how to work in this repository.

## Repository

`https://github.com/viko-nexus/viko-agent`

## What This Repo Is

Source of truth for **Viko** — a self-hosted multi-project AI developer agent. It contains:
- Hermes-Admin identity and onboarding skill (`admin/`)
- WhatsApp bridge source (`bridge/`)
- Patches applied to the Hermes image at build time (`patches/`)
- Event hooks and MCP servers (`hooks/`, `mcp-servers/`)
- Onboarding and init scripts (`scripts/`)
- Docker build and service configs (`Dockerfile.hermes`, `docker-compose.yml`)

This is **not** app code. Project source code lives at `/home/deploy/{slug}/repo/` on the VPS.

## Architecture

```
VPS (Central)
├── viko-hermes     — Hermes-Admin + standalone WA bridge (port 3000)
├── viko-9router    — LLM gateway (port 20128)
└── viko-{slug}     — one isolated Hermes-Project per active project group

/home/deploy/{slug}/
├── .ssh/id_ed25519         ← per-project SSH key (generated at onboard)
├── config/                 ← Hermes-Project data dir (SOUL.md, rules/, skills/)
└── repo/                   ← git clone of project's GitHub repo
```

## Repository Structure

```
viko-agent/
├── admin/              ← Hermes-Admin identity (SOUL.md, rules/, skills/)
├── bridge/             ← Standalone WA bridge (Node.js/Baileys)
├── patches/            ← Python scripts applied to Hermes image at build time
├── hooks/              ← Event hooks mounted at /opt/data/hooks/
├── mcp-servers/        ← MCP server implementations
├── scripts/            ← Onboarding, spawning, init automation
├── skills/             ← Skill files exposed to Hermes-Admin
├── docs/overview/      ← Architecture, development, deployment docs
├── Dockerfile.hermes   ← Multi-stage build (Hermes source + patches + bridge)
├── docker-compose.yml  ← 9router + Hermes services (profiles: gateway, full)
└── .env.example        ← Environment variable reference
```

## Code Conventions

- **Language**: All code, comments, docstrings, variable names → **English**
- **No hardcoded values**: `OWNER_WA`, phone numbers, group JIDs, project slugs → always from env vars or config files
- **No comments explaining obvious code** — only add WHY a non-obvious choice was made
- **Never commit**: `.env`, `data/`, `backups/`, `projects/*/` (except viko-agent itself)

## Docker Operations

```bash
# Build Hermes image (required after patches/ or bridge/ changes)
docker compose build hermes

# Start everything (9router + Hermes)
docker compose --profile full up -d

# Restart Hermes only (after admin/ or config changes)
docker compose --profile full up -d --force-recreate hermes

# Start only 9router
docker compose --profile gateway up -d

# View logs
docker logs viko-hermes -f
docker logs viko-{slug} -f

# Stop all
docker compose --profile full down
```

## First-Time Setup (after first Hermes start)

```bash
# 1. Initialize 9router model combos
python3 scripts/init-9router.py

# 2. Apply Hermes config overrides
python3 scripts/init-hermes-config.py

# 3. Pair WhatsApp (scan QR from logs)
docker logs -f viko-hermes
```

## Key Files

| File | Purpose |
|------|---------|
| `admin/SOUL.md` | Hermes-Admin personality and behavior |
| `admin/rules/authorization.md` | Who can do what |
| `admin/skills/onboarding.md` | Onboarding skill (slash command) |
| `patches/isolation-guard.py` | Boot-time isolation check (fail-closed) |
| `patches/patch-model-router.py` | Auto-routes messages to viko-chat or viko-code combo |
| `bridge/whatsapp-bridge.js` | Admin + relay mode WA bridge; security gate |
| `scripts/init-9router.py` | Creates viko-chat + viko-code combos in 9router |
| `scripts/init-hermes-config.py` | Applies Hermes config overrides (idempotent) |
| `scripts/spawn-hermes.py` | Spawns an isolated Hermes-Project container |
| `scripts/add-project.py` | Full onboarding: clone repo + spawn container + register routing |
| `scripts/provision-env.sh` | VPS .env provisioning from CI secrets (used by deploy workflow) |
| `mcp-servers/projects-gateway.py` | SSH exec MCP server (loads projects from data/projects.json) |

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|----------|---------|
| `OWNER_WA` | Owner's WA number — only this number can issue commands. Never hardcode. |
| `VIKO_NAME` | Container/network prefix (default: `viko`) |
| `OPENAI_API_KEY` | 9router client API key (for Hermes to call 9router) |
| `OPENAI_BASE_URL` | 9router endpoint (`http://viko-9router:20128/v1`) |
| `WHATSAPP_HOME_CHANNEL` | Group JID for startup notifications |
| `GITHUB_TOKEN` | Fine-grained PAT for onboarding (repo clone + deploy key setup) |
| `NINEROUTER_JWT_SECRET` | 9router internal JWT secret |
| `NINEROUTER_INITIAL_PASSWORD` | 9router admin password |
| `NINEROUTER_API_KEY_SECRET` | 9router API key signing secret |

## Security Rules (never break these)

1. `OWNER_WA` must always come from env var — never a literal phone number in code
2. `bridge/whatsapp-bridge.js` relay token scope check is the real security gate — do not bypass
3. `patches/isolation-guard.py` verifies per-project isolation at boot — must run before gateway
4. `project.json` stores per-project DB credentials at mode 600 — never read from env vars
5. Relay tokens in `routing.json` are unique per project — never reuse or share between projects

## What NOT to Do

- Do not hardcode phone numbers, group JIDs, or project slugs in committed files
- Do not add `channel_prompts` to `scripts/init-hermes-config.py` (group JIDs are deployment-specific)
- Do not run `apt install`, `pip install -g`, or `npm install -g` inside containers at runtime
- Do not bypass the relay token scope check in the bridge — that's the security enforcement layer
- Do not commit `data/`, `backups/`, `.env`, or any `projects/*/` files other than `projects/viko-agent/`
- Do not use relative paths — always use `Path(__file__).parent.parent.resolve()` for the repo root

## Docs

- [docs/overview/ARCHITECTURE.md](docs/overview/ARCHITECTURE.md) — full system design
- [docs/overview/DEVELOPMENT.md](docs/overview/DEVELOPMENT.md) — local dev setup, building, patching
- [docs/overview/DEPLOYMENT.md](docs/overview/DEPLOYMENT.md) — VPS setup, CI/CD pipeline
- [docs/overview/CONTRIBUTING.md](docs/overview/CONTRIBUTING.md) — contribution guidelines
- [docs/overview/SECURITY.md](docs/overview/SECURITY.md) — security model, disclosure policy
