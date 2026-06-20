# Development Guide

## Prerequisites

- Docker + Docker Compose (v2)
- Python 3.11+ (for scripts)
- Node.js 20+ (for bridge development)
- A WhatsApp account (for testing the bridge)
- Anthropic API key (primary LLM)
- Groq API key (fallback LLM)
- GitHub fine-grained PAT (for onboarding)

---

## Local Setup

```bash
git clone git@github.com:viko-nexus/viko-agent.git
cd viko-agent

# Copy and fill in environment
cp .env.example .env
# Required: WHATSAPP_OWNER_NUMBER, NINEROUTER_JWT_SECRET, NINEROUTER_INITIAL_PASSWORD,
#           NINEROUTER_API_KEY_SECRET, ANTHROPIC_API_KEY, GROQ_API_KEY, GITHUB_TOKEN

# Build Hermes image (takes ~10-20 min on first build, cached after)
docker compose build hermes

# Start everything
docker compose --profile full up -d

# Tail logs
docker logs -f viko-hermes
```

---

## First-Time Initialization

After Hermes has started at least once (config.yaml is created):

```bash
# 1. Apply Hermes config overrides
python3 scripts/init-hermes-config.py

# 2. Initialize 9router model combos
python3 scripts/init-9router.py

# 3. Pair WhatsApp (scan QR in logs)
docker logs -f viko-hermes   # QR appears during startup
```

After pairing, WhatsApp session is saved to `data/hermes/.hermes/whatsapp/session/`
(gitignored). It persists across container restarts.

---

## Working on Each Component

### Editing `admin/` (Hermes-Admin identity)

No rebuild needed. The admin config is bind-mounted.

```bash
# Edit SOUL.md, rules/, or skills/
nano admin/SOUL.md

# Restart to pick up changes
docker compose --profile full up -d --force-recreate hermes
```

### Editing `patches/` (Hermes image patches)

Patches are baked into the image at build time. Any change requires a rebuild.

```bash
nano patches/patch-model-router.py
docker compose build hermes
docker compose --profile full up -d --force-recreate hermes
```

### Editing `bridge/` (WhatsApp bridge)

The bridge is a Node.js process (`bridge/whatsapp-bridge.js`) baked into the image.
Changes require a rebuild.

```bash
nano bridge/whatsapp-bridge.js
cd bridge && npm install   # update dependencies locally if needed
docker compose build hermes
docker compose --profile full up -d --force-recreate hermes
```

### Editing `hooks/` (Event hooks)

Hooks are bind-mounted at `/opt/data/hooks/` — no rebuild needed.

```bash
nano hooks/viko-startup/handler.py
# Restart to pick up
docker compose --profile full up -d --force-recreate hermes
```

### Editing `scripts/` (Onboarding scripts)

Scripts run directly from the VPS repo clone — no rebuild needed.

```bash
# Test locally with dry run
WHATSAPP_OWNER_NUMBER=<your-number> python3 scripts/onboard.py \
  --name "Test" --slug testproject \
  --github https://github.com/example/repo \
  --vps-host localhost --vps-user deploy \
  --dry-run
```

### Editing `mcp-servers/`

MCP servers are bind-mounted into the container. Restart is enough.

```bash
nano mcp-servers/projects-gateway.py
docker compose --profile full up -d --force-recreate hermes
```

---

## Dockerfile.hermes

Multi-stage build:

| Stage | Purpose |
|-------|---------|
| `uv_source` | uv binary (Python package manager) |
| `node_source` | Node 22 LTS |
| `hermes_source` | Clone Hermes source from GitHub |
| `runtime` | Final image: Hermes + patches + bridge + tools |

The Viko-specific patches are applied at the **end** of the Dockerfile so that
changing `patches/` only rebuilds the last few layers (~2-3 min), not the full
npm/uv/apt installation (~15-20 min).

Rebuild triggers (only Dockerfile.hermes and patches/):
- `Dockerfile.hermes` changed
- Any file in `patches/` changed
- `bridge/whatsapp-bridge.js` or `bridge/package.json` changed

The CI build job checks `git diff` for these files before rebuilding.

---

## Linting

**Python** (scripts/, patches/, mcp-servers/):
```bash
ruff check scripts/ patches/ mcp-servers/
ruff format --check scripts/ patches/ mcp-servers/
```

**JavaScript** (bridge/):
```bash
cd bridge && node --check whatsapp-bridge.js allowlist.js
```

Run lint before every commit. CI enforces this in the `quality` job.

---

## Testing

No automated test suite yet. Manual testing:

1. **Bridge connectivity**: `curl http://localhost:3000/health`
2. **9router health**: `curl http://localhost:20128/`
3. **Hermes dashboard**: `http://localhost:9119` (requires VIKO_BIND_ADDR loopback)
4. **Onboarding dry run**: `python3 scripts/onboard.py --dry-run ...`
5. **Isolation guard**: Check `docker logs viko-hermes` for `[isolation-guard] OK`

---

## Commit Standards

- All commits in English, under 120 characters
- Prefix: `feat:`, `fix:`, `docs:`, `security:`, `chore:`, `refactor:`
- No hardcoded values (phone numbers, group JIDs, project slugs) in committed files
- Run ruff before committing any Python changes
