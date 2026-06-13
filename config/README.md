# Config

Infrastructure configuration for the Viko agent stack.
Docker Compose file is at the repo root: `../docker-compose.yml`

## Services

| Service | Role | Status | Port |
|---------|------|--------|------|
| ChromaDB | Vector DB for persistent memory | Docker ✅ | 8000 |
| 9router | LLM gateway with fallback routing | Docker ✅ | 8080 |
| Hermes | AI orchestrator (single brain) | Native (launchctl) | — |

> **Hermes note**: Hermes from NousResearch currently runs as a native macOS service
> (`launchctl`). The Docker block in `docker-compose.yml` is commented out until an
> official Docker image is available. Run `bash ../scripts/hermes.sh` to install/update.

## Data (Bind Mounts)

All persistent data is stored in `../data/` — on the laptop, not inside Docker.
This folder is gitignored but persists across container restarts and re-creates.

```
data/
├── chromadb/    ← ChromaDB vector store (Viko's memory)
├── hermes/      ← Hermes session state (future Docker use)
└── 9router/     ← 9router config and cache
```

## LLM Routing (9router)

9router handles model selection and fallback:

| Priority | Provider | Model |
|----------|----------|-------|
| Primary | Google | Gemini Flash |
| Fallback | Groq | Llama 3.3 70B |

Fallback triggers when: primary quota exhausted, rate limit hit, or timeout.

## Quick Commands

```bash
# Start all Docker services
docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f chromadb
docker compose logs -f 9router

# Restart a single service
docker compose restart chromadb

# Hermes (native — not Docker)
launchctl stop ai.hermes.gateway && sleep 2 && launchctl start ai.hermes.gateway
```

## Setup

1. Copy `.env.example` to `.env` and fill in API keys
2. Run `docker compose up -d`
3. Verify: `curl http://localhost:8000/api/v1/heartbeat` (ChromaDB)
4. Verify: `curl http://localhost:8080/health` (9router)

## Security

- All secrets stay in `.env` — never committed to git
- `.gitignore` excludes `.env`, `*.env`, `data/`
- ChromaDB runs on localhost only (no external exposure)
