# viko-agent

Configuration and infrastructure for **Viko** — AI developer assistant powered by
Hermes (brain) and 9router (LLM gateway). All services run in Docker locally.

## Repository Purpose

This repo is Viko's "home" — it defines who Viko is, what Viko can do, and what Viko
knows about each project. Read by the orchestrator (Hermes). Not app code.

Exception: `patches/` and `hooks/` are operational — applied to Hermes at container
build time or loaded as event hooks. `scripts/` contains setup automation.

## Repository Structure

```
viko-agent/
│
├── soul/                  ← Who Viko is (identity, values, communication style)
│   └── identity.md
│
├── rules/                 ← How Viko behaves (authorization, approval, timeouts)
│   ├── authorization.md
│   ├── approval-format.md
│   ├── timeouts.md
│   └── project-detection.md
│
├── skills/                ← Domain knowledge per lifecycle stage
│   ├── planning.md
│   ├── debugging.md
│   ├── deployment.md
│   ├── testing.md
│   ├── monitoring.md
│   ├── self-monitoring.md
│   ├── web-research.md
│   └── media.md
│
├── projects/              ← Per-project context (dossier, not app code)
│   │                        gitignored except projects/viko-agent/
│   └── <slug>/
│       ├── context.md     ← team, paths, stack, session init
│       ├── steps.md       ← project-specific steps (Viko updates over time)
│       └── plans/         ← approved implementation plans
│
├── patches/               ← Applied to Hermes at container build time
│   ├── whatsapp-bridge.js
│   ├── apply-run-py.py
│   ├── apply-agent-msgs.py
│   ├── patch-ssh-guard.py
│   └── patch-model-router.py
│
├── hooks/                 ← Hermes event hooks (mounted into /opt/data/hooks at runtime)
│   └── viko-startup/      ← Send WA notification when Viko comes online
│
├── scripts/               ← Setup and restore automation
│   ├── init-9router.py    ← Idempotent combo setup for 9router
│   ├── init-hermes-config.py  ← Idempotent config restore for Hermes
│   ├── spawn-hermes.py    ← Spawn isolated Hermes container per project (Option B)
│   └── setup-keys.py     ← Generate SSH keys + GitHub deploy key for onboarding
│
├── docs/                  ← Setup and operational documentation
│   ├── 9router/setup.md
│   └── hermes/setup.md
│
├── docker-compose.yml     ← Hermes + 9router + 9router-init
├── Dockerfile.hermes      ← Hermes image with patches applied
├── .env.example           ← Secrets template (copy to .env, never commit)
└── data/                  ← Bind-mount targets — gitignored, persists on laptop
    ├── hermes/            ← HERMES_HOME: config.yaml, SOUL.md, state.db, memory
    ├── 9router/
    ├── bridge/            ← routing.json: group JID → Hermes port mapping
    ├── hermes-admin/      ← Admin Hermes: DMs + onboarding (HERMES_HOME)
    └── hermes-{slug}/     ← Per-project Hermes instances (created by spawn-hermes.py)
```

## Viko Startup Sequence

Hermes reads in this order on each session:
1. `AGENTS.md` — entry point: loads identity, rules, and skill references
2. `soul/identity.md` — who Viko is
3. `rules/` — all files (authorization, approval, timeouts, project detection)
4. `skills/` — relevant to the current task (exposed as slash commands via `skills.external_dirs`)
5. `projects/<active>/context.md` — discovered dynamically via `ls projects/`
6. Long-term memory from Holographic (`data/hermes/memory_store.db`)

## Memory

Viko uses **Holographic** (pure local) for persistent memory across sessions:
- No API key or external service — SQLite-backed, runs entirely inside container
- Entity resolution, trust scoring, and HRR-based compositional retrieval
- Data persists in `data/hermes/memory_store.db` (gitignored, survives restarts)
- Activated via `memory.provider: holographic` in `data/hermes/config.yaml`

## Model Routing

Each message is automatically routed to the right model before the LLM is called:

| Trigger | Combo | Primary Model |
|---------|-------|---------------|
| Code keywords (`debug`, `fix`, `api`, `deploy`, …) | `viko-code` | Claude Sonnet |
| Everything else | `viko-chat` | Claude Haiku |
| Manual `/model` override | preserved until `/new` or `/reset` | — |

Each combo has Groq fallback: `sonnet/haiku → groq/llama-3.3 → groq/maverick`.
Implemented in `patches/patch-model-router.py`.

## Project Isolation (Option B)

Each WhatsApp group runs its own Hermes instance with isolated memory:

```
WA (1 number)
    └── hermes (admin) — bridge exposed on Docker network at :3000
            ├── queue[personal_jid / unregistered] → handled by admin
            ├── queue[project_jid_1] → Hermes-Mankop  (RELAY_MODE)
            └── queue[project_jid_2] → Hermes-Siprodev (RELAY_MODE)
```

- **Admin Hermes** (viko-hermes): handles DMs, unregistered groups, onboarding
- **Project Hermes** (viko-hermes-{slug}): spawned by spawn-hermes.py, memory-isolated
- **Routing**: data/bridge/routing.json maps group JIDs to Hermes ports, hot-reloaded
- **Relay mode**: project containers set WHATSAPP_RELAY_MODE=true, proxy to admin bridge

## Projects

Projects are **dynamic and local** — not committed to git (except `projects/viko-agent/`).

- Each user maintains their own `projects/` directory locally
- Viko discovers available projects by running `ls projects/`
- To onboard an existing project: tell Viko "add project <name> to viko"
  Viko will validate the folder exists, scan the codebase, and generate `context.md`

App code lives outside this repo, mounted at the same path inside Docker:
```yaml
volumes:
  - ${HOME}/Projects:${HOME}/Projects:rw
```

Set `VIKO_PROJECTS_ROOT` in `.env` to tell Viko where your projects root is.

## What Lives Where

| Content | Location |
|---------|----------|
| Identity and values | `soul/` |
| Behavior rules | `rules/` |
| Domain skills | `skills/` — exposed as `/skill-name` slash commands |
| Project context and steps | `projects/<slug>/` — gitignored, local only |
| Long-term memory | `data/hermes/memory_store.db` — gitignored |
| Event hooks | `hooks/` — mounted at runtime into `/opt/data/hooks/` |
| Hermes patches | `patches/` — applied at `docker compose build hermes` |
| Setup scripts | `scripts/` — run manually or via docker-compose service |
| App code | `$VIKO_PROJECTS_ROOT/<name>/` — mounted read-write at same path |
| Secrets | `.env` — never committed |

## Docker Operations

```bash
# Build image (required after Dockerfile.hermes or patches/ changes)
docker compose build hermes

# Start all services
docker compose --profile full up -d

# Restart hermes only (picks up config.yaml and hooks changes)
docker compose --profile full up -d --force-recreate hermes

# View logs
docker compose logs -f hermes

# Stop all
docker compose down

# Spawn new project Hermes instance
ssh viko-vps python3 ~/projects/viko-agent/scripts/spawn-hermes.py <slug> <group_jid>

# Initialize admin Hermes config (after fresh setup or data/ wipe)
python3 scripts/init-hermes-config.py --target admin

# View routing table
cat data/bridge/routing.json

# View per-project container
docker logs viko-hermes-<slug> -f
```

## After a Reset

See `config/README.md` for full recovery steps.
Quick reference:

```bash
# 9router combos — auto-restored on next docker compose up
# Hermes config — restore manually:
python3 scripts/init-hermes-config.py
docker compose --profile full up -d --force-recreate hermes

# Re-spawn all project containers (routing.json has the JIDs)
cat data/bridge/routing.json  # see all projects + ports
python3 scripts/spawn-hermes.py <slug> <jid>  # repeat per project
```

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | 9router API key for Hermes |
| `OPENAI_BASE_URL` | 9router URL (default: `http://viko-9router:20128/v1`) |
| `WHATSAPP_HOME_CHANNEL` | JID Viko sends startup notifications to |
| `VIKO_PROJECTS_ROOT` | Root folder for all your app projects (e.g. `~/Projects`) |
| `GITHUB_TOKEN` | Classic PAT (repo scope) for automated GitHub deploy key setup |
