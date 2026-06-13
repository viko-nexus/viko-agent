# viko-agent

Configuration and infrastructure for **Viko** — a local AI developer assistant that handles
the full development lifecycle: answering questions on WhatsApp, planning, coding, testing,
deploying, and monitoring.

---

## How It Works

```
WhatsApp / Google Chat
        │
        ▼
    Hermes (brain)          ← reads soul/, rules/, skills/, projects/
        │
        ├── 9router ──────► Gemini Flash (primary)
        │                   Groq Llama (fallback)
        │
        ├── ChromaDB ──────► persistent memory (decisions, errors, summaries)
        │
        └── tools ─────────► git, code editor, browser (Playwright), CI/CD
```

**Lifecycle:** Message → Plan → Code → Test → Deploy → Monitor → Alert → Plan

---

## Stack

| Component | Role | Image |
|-----------|------|-------|
| Hermes | AI orchestrator — single brain | `HERMES_IMAGE` (set in `.env`) |
| 9router | LLM gateway with fallback | `NINEROUTER_IMAGE` (set in `.env`) |
| ChromaDB | Vector DB for persistent memory | `chromadb/chroma:latest` |

All services run in Docker locally. Data is stored in `./data/` on your laptop —
never inside the container.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd viko-agent

# 2. Set up environment
cp .env.example .env
# Edit .env — add API keys and Docker image names

# 3. Start services
docker compose up -d

# 4. Verify
curl http://localhost:8000/api/v1/heartbeat   # ChromaDB
curl http://localhost:8080/health              # 9router
```

---

## Repo Structure

```
viko-agent/
│
├── soul/                  ← Who Viko is (identity, values, communication style)
├── rules/                 ← How Viko behaves (authorization, approvals, timeouts)
├── skills/                ← Domain knowledge (planning, debugging, deploy, test, monitor)
├── projects/              ← Per-project context — NOT the app code itself
│   └── <project>/
│       ├── context.md     ← team, stack, paths, session init
│       ├── steps.md       ← project-specific dev steps (Viko updates over time)
│       └── plans/         ← approved implementation plans
├── memory/                ← Memory architecture docs (data lives in ./data/chromadb)
├── config/                ← Infrastructure docs and service-specific configs
├── patches/               ← Custom patches applied to Hermes at container build time
├── hooks/                 ← Hermes event hooks (e.g. startup notification)
├── docker-compose.yml
├── .env.example
└── LICENSE
```

> **Key distinction:** `projects/<name>/` contains Viko's *knowledge about* a project
> (context, steps, plans). The actual app code lives elsewhere on your machine.

---

## Adding a New Project

1. Create the project folder and files:
   ```bash
   mkdir -p projects/<slug>/plans
   touch projects/<slug>/context.md
   touch projects/<slug>/steps.md
   touch projects/<slug>/plans/.gitkeep
   ```

2. Fill in `context.md` — minimum required:
   - Project overview and goal
   - App root path on your machine
   - Team members and roles
   - Session init instructions (what Viko reads first)

3. Add the project slug to `rules/project-detection.md`.

4. Create `AGENTS.md` (or `CLAUDE.md`) inside the actual app folder for the executor.

---

## Authorization Model

Viko operates on three tiers — see `rules/authorization.md` for full details.

| Tier | Examples | Action |
|------|----------|--------|
| Free | Read logs, draft plans, send info | Execute, no notification |
| Report | Create branch, install packages, write files | Execute, then notify |
| Ask | Deploy, push, delete data | Send WA approval, wait |

All approvals go to Eksa via WhatsApp in the format:
```
[Action] what Viko wants to do
[Risk]   consequence if something goes wrong
[Choice] Ya / Tidak / Tunda
```

---

## Data Persistence

All Docker volume data is stored as bind mounts in `./data/` — on your laptop:

```
data/
├── chromadb/    ← Viko's memory (decisions, errors, project summaries)
├── hermes/      ← Hermes session state
└── 9router/     ← Gateway cache and config
```

This folder is gitignored. It survives container restarts and `docker compose down`.
Only `docker compose down -v` or manual deletion removes it.

---

## License

Non-commercial use only. See [LICENSE](LICENSE).
