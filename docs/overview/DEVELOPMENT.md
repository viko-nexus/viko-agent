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
# Required: WHATSAPP_OWNER_NUMBER, VIKO_OWNER_NAME, VIKO_PROJECTS_ROOT,
#           NINEROUTER_JWT_SECRET, NINEROUTER_INITIAL_PASSWORD, NINEROUTER_API_KEY_SECRET,
#           ANTHROPIC_API_KEY, GROQ_API_KEY, GITHUB_TOKEN,
#           HERMES_DASHBOARD_BASIC_AUTH_USERNAME + _PASSWORD (or _SECRET / a scrypt hash)
# Optional: VIKO_BIND_ADDR (default 127.0.0.1), VIKO_ISOLATION_GUARD (default enforce)
#
# VIKO_OWNER_NAME — bridge stamps the owner's real name on the inbound CTX line so
#   Viko addresses the owner by name instead of guessing.
# VIKO_PROJECTS_ROOT — absolute host path for project repos, bind-mounted at the
#   same path inside containers. On macOS/local set HERMES_UID/HERMES_GID to your
#   host IDs (often 501:20, not the 1000:1000 Linux default) so bind-mount files
#   are owned correctly.
# Dashboard auth — the Hermes dashboard binds 0.0.0.0:9119 (for the host port-map),
#   so it is reachable by every container on a shared docker network. It now runs
#   with HERMES_DASHBOARD_INSECURE=false; set the basic-auth credentials so a
#   project container can't scrape the session token / API key.

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
| Hermes (agent, WA session, config) | http://localhost:9119 | basic auth — `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` / `_PASSWORD` (`HERMES_DASHBOARD_INSECURE=false`) |
| 9router (providers, combos, API keys, usage) | http://localhost:20128 | password = `NINEROUTER_INITIAL_PASSWORD` |

The Hermes dashboard binds `0.0.0.0` for the host port-map, which also exposes it
to peers on a shared docker network, so the host bind alone is not a boundary.
Set `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` + `_PASSWORD` in `.env` (prod: prefer a
scrypt hash over plaintext) so a project container can't scrape the session token /
API key.

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
but a few stand-alone files (`whatsapp-bridge.js`, `isolation-guard.py`) are copied
verbatim into the image and can be bind-mounted over their in-image location instead.
See [Fast Local Iteration](#fast-local-iteration-no-rebuild) below.

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

> **Project containers get the live bridge too.** `scripts/spawn-hermes.py`
> bind-mounts `patches/whatsapp-bridge.js` over the image's baked copy in every
> `viko-{slug}` container as well, so a bridge edit applies to admin AND project
> containers on a container restart — no image rebuild. But a project container's
> generated `config.yaml` / `SOUL.md` (anti-hallucination + persona prompt, terminal
> cwd, channel prompt) are written by `spawn-hermes.py` only at spawn time — to pick
> up changes to those you must **re-spawn** the container, not just restart it.

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

**JavaScript** (the WhatsApp bridge — ESLint + Prettier + type-check via checkJs):
```bash
npm install        # once, installs the dev tooling (gitignored node_modules)

npm run lint       # ESLint: no-unused-vars, no-undef, prefer-const, …
npm run format     # Prettier: apply formatting   (format:check to verify only)
npm run typecheck  # tsc --noEmit with checkJs — type-checks the JS, no build step
npm run check      # all three at once (what CI runs)
```

The bridge stays plain JavaScript (Node runs `bridge.js` directly — no compile step,
so the fast-reload loop above is unaffected). Type-checking is via `checkJs`/JSDoc in
`tsconfig.json`; external libs (Baileys, express) are declared in `types/externals.d.ts`,
and `patches/allowlist.d.ts` types the Hermes-provided `allowlist.js` import.

> **`node --check` is NOT enough to validate the bridge.** It is an ESM module; a
> syntax check that passes can still crash the ESM loader at import time. Real lesson:
> a regex containing literal U+2028/U+2029 chars passed `node --check` but threw when
> the loader actually parsed the module. Validate via an actual import / `npm run check`,
> not `node --check`.

Run the quality gate before every commit. CI enforces both in the `quality` job:

```bash
npm run check                              # bridge: lint + format:check + typecheck
ruff check scripts/ patches/ mcp-servers/  # Python
```

---

## Testing

No automated test suite yet. Manual testing:

1. **Bridge connectivity**: `curl http://localhost:3000/health`
2. **9router health**: `curl http://localhost:20128/`
3. **Hermes dashboard**: `http://localhost:9119` (bound to `VIKO_BIND_ADDR`; basic auth)
4. **Onboarding dry run**: `python3 scripts/onboard.py --dry-run ...`
5. **Isolation guard**: check a project container's logs for `[isolation-guard] OK`
   (e.g. `docker logs viko-hermes-{slug}`). The guard runs per-project at boot; with
   `VIKO_ISOLATION_GUARD=enforce` (the default) a failed check leaves the container
   inert/unhealthy instead of starting the gateway.

---

## Commit Standards

- All commits in English, under 120 characters
- Prefix: `feat:`, `fix:`, `docs:`, `security:`, `chore:`, `refactor:`
- No hardcoded values (phone numbers, group JIDs, project slugs) in committed files
- Run ruff before committing any Python changes
