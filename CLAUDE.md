# viko-agent

Configuration and infrastructure for **Viko** — AI developer assistant powered by
Hermes (brain) and 9router (LLM gateway). All services run in Docker locally.

## Repository Purpose

This repo is Viko's "home" — it defines who Viko is, what Viko can do, and what Viko
knows about each project. Read by the orchestrator (Hermes). Not app code.

Exception: `patches/` and `hooks/` are operational — applied to Hermes at container
build time or loaded as event hooks.

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
│   └── monitoring.md
│
├── projects/              ← Per-project context (dossier, not app code)
│   └── <slug>/
│       ├── context.md     ← team, paths, stack, session init
│       ├── steps.md       ← project-specific steps (Viko updates over time)
│       └── plans/         ← approved implementation plans
│
├── memory/                ← Memory architecture docs (data lives in ./data/)
│   └── README.md
│
├── config/                ← Infrastructure docs
│   └── README.md
│
├── patches/               ← Applied to Hermes at container build time
│   ├── whatsapp-bridge.js
│   ├── apply-run-py.py
│   └── apply-agent-msgs.py
│
├── hooks/                 ← Hermes event hooks
│   └── viko-startup/      ← Send WA notification when Viko comes online
│
├── docker-compose.yml     ← Hermes + 9router + ChromaDB
├── .env.example           ← Secrets template (copy to .env, never commit)
└── data/                  ← Bind-mount targets — gitignored, persists on laptop
    ├── chromadb/
    ├── hermes/
    └── 9router/
```

## Viko Startup Sequence

Hermes reads in this order on each session:
1. `soul/identity.md`
2. `rules/` — all files
3. `skills/` — relevant to the current task
4. `projects/<active>/context.md`
5. Relevant memory from ChromaDB (`./data/chromadb`)

## What Lives Where

| Content | Location |
|---------|----------|
| Identity and values | `soul/` |
| Behavior rules | `rules/` |
| Domain skills | `skills/` |
| Project context and steps | `projects/<slug>/` |
| Approved plans | `projects/<slug>/plans/` |
| Memory data | `./data/chromadb` — gitignored |
| Hermes patches | `patches/` — applied at Docker build |
| App code | `~/Projects/<name>/` — outside this repo |
| Secrets | `.env` — never committed |

## Docker Operations

```bash
# Start all services
docker compose up -d

# Restart a service
docker compose restart hermes

# View logs
docker compose logs -f hermes

# Stop all
docker compose down
```

## Projects

| Slug | Description | App Path |
|------|-------------|----------|
| `forecast-inn` | ForecastInn platform | `~/Projects/forecastinn/forecast-inn` |
| `forecast-crm` | ForecastInn CRM | `~/Projects/forecastinn/forecast-crm` |
| `luxso` | Luxso Executive Dashboard | `~/Projects/forecastinn/clients/Luxso-executive-dashboard` |
| `mankop` | Mankop (Koperasi Multi Pihak) | `~/Projects/mankop/mankop-apps` |
