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

# Build Hermes image ONCE (takes ~15-30 min; cached after)
docker compose build hermes

# Bootstrap the whole local stack in one run (see below)
./scripts/dev-init.sh
```

### `scripts/dev-init.sh` — one-shot local bootstrap

After the image exists, this single idempotent script does everything needed to
get a working local instance and ends by printing the WhatsApp QR to scan:

1. Sanity checks (`.env`, Docker running, prebuilt image present)
2. Writes `docker-compose.override.yml` (bind-mounts source for rebuild-free iteration)
3. Creates the macOS `data/hermes/SOUL.md` nested-mount placeholder
4. Starts 9router + Hermes from the **existing image** (no rebuild)
5. Seeds 9router combos (`init-9router.py`) and **syncs the local 9router API key
   into `.env`** as `OPENAI_API_KEY` (the key is per-instance — the production key
   does not work against a local 9router and yields `401 API key required`)
6. Smoke-tests the LLM path (expects 9router `200`)
7. Pairs WhatsApp via `hermes whatsapp` if no `creds.json` yet

Re-run it any time; already-done steps are skipped. If the local 9router has no
API key yet, it tells you to generate one in the dashboard and re-run.

### Dashboards (local)

Both bind to `VIKO_BIND_ADDR` (default `127.0.0.1`), so they are reachable only
from this machine:

| Dashboard | URL | Auth |
|-----------|-----|------|
| Hermes (agent, WA session, config) | http://localhost:9119 | none (`HERMES_DASHBOARD_INSECURE=true`) |
| 9router (providers, combos, API keys, usage) | http://localhost:20128 | password = `NINEROUTER_INITIAL_PASSWORD` |

Configure provider keys (Anthropic/Groq) and generate the API key in the 9router
dashboard. `init-9router.py` only creates the combos; it does not add provider keys.

---

## First-Time Initialization

`scripts/dev-init.sh` runs these for you. To do them manually:

```bash
# 1. Apply Hermes config overrides
python3 scripts/init-hermes-config.py

# 2. Initialize 9router model combos
python3 scripts/init-9router.py

# 3. Pair WhatsApp (interactive QR)
docker exec -it viko-hermes hermes whatsapp
```

> The QR for pairing comes from the interactive `hermes whatsapp` command above
> (it needs a TTY), not the gateway logs. The Node bridge writes its own output to
> `data/hermes/whatsapp/bridge.log`, not `docker logs`.

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

Patches are baked into the image at build time. **Most** changes require a rebuild —
but the WhatsApp bridge (`patches/whatsapp-bridge.js`) does not. See
[Fast Local Iteration](#fast-local-iteration-no-rebuild) below; that one file is
copied verbatim into the image and can be bind-mounted instead.

The **Python source patches** (`patch-model-router.py`, `patch-ssh-guard.py`,
`patch-approval-sql-context.py`, `indonesian-locale.py`) edit Hermes' own vendored
files in-place, so they cannot be bind-mounted — they always need a rebuild:

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

## Fast Local Iteration (no rebuild)

A full image rebuild takes 15-30 min. You do **not** need one to iterate on the
WhatsApp bridge — `patches/whatsapp-bridge.js` is copied verbatim into the image
(`Dockerfile.hermes`), not compiled. The same is true for `patches/isolation-guard.py`
and `scripts/init-hermes-config.py`. Bind-mount these over their in-image locations
and reload the process in seconds.

**One-time setup** — create `docker-compose.override.yml` (gitignored, local-only;
`docker compose` loads it automatically with no `-f` flag):

```yaml
services:
  hermes:
    volumes:
      - ./patches/whatsapp-bridge.js:/opt/hermes/scripts/whatsapp-bridge/bridge.js:ro
      - ./patches/isolation-guard.py:/opt/hermes/docker/viko-isolation-guard.py:ro
      - ./scripts/init-hermes-config.py:/opt/viko/scripts/init-hermes-config.py:ro
```

**macOS one-time gotcha:** the base compose bind-mounts `admin/SOUL.md` into the
`data/hermes` bind (a nested mount). On Docker Desktop / VirtioFS the inner target
must pre-exist, or the container fails to start with a "mountpoint is outside of
rootfs" error. Create it once:

```bash
touch data/hermes/SOUL.md
```

Then recreate the container once so the mounts take effect:

```bash
docker compose --profile full up -d --force-recreate hermes
```

**Iteration loop** (repeat freely):

```bash
nano patches/whatsapp-bridge.js          # 1. edit
./scripts/dev-reload-bridge.sh           # 2. reload (~5-30s, no rebuild)
docker exec viko-hermes tail -f /opt/data/whatsapp/bridge.log   # 3. observe
```

`dev-reload-bridge.sh` runs `docker restart viko-hermes`; the gateway re-spawns the
bridge from the bind-mounted file. (Killing the bridge process alone does NOT work —
the gateway treats an unexpected bridge exit as a fatal error and will not respawn it.)

> **Where bridge logs go:** the Node bridge writes its own stdout to
> `/opt/data/whatsapp/bridge.log` (= `data/hermes/whatsapp/bridge.log` on the host),
> NOT to `docker logs viko-hermes` — that stream only shows the Python gateway
> adapter's `[Whatsapp]` lines. Tail the file to see `[bridge]` output.

When the fix is verified, **commit the file** and let CI rebuild the image for prod.
The override is local-only and never deployed, so production always runs the baked image.

> Caveat: this covers the whole-file replacements only. Changes to the Python
> source patches still require `docker compose build hermes` (see above).

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
