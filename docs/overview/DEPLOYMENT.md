# Deployment Guide

## Infrastructure Requirements

- VPS with Docker 24+ and Docker Compose v2
- Traefik (or any reverse proxy) for routing — optional for this service
- SSH access for the `deploy` user
- Outbound internet access (for WhatsApp, GitHub, Anthropic/Groq APIs)

### VPS Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB |
| CPU | 2 vCPU | 4 vCPU |
| Disk | 40 GB | 100 GB |

**Memory budget per container (with MALLOC_ARENA_MAX=2 tuning):**
- `viko-hermes` (admin + bridge): ~770 MB baseline, limit 1.5 GB
- `viko-9router`: ~150 MB baseline, limit 512 MB
- `viko-hermes-{slug}` (per project): ~500–700 MB baseline, limit 1500 MB
- Infra (postgres, redis, minio, traefik): ~280 MB combined

**Practical capacity:** 8 GB RAM comfortably supports ~7–8 simultaneous active project containers.

---

## First-Time VPS Setup

### 1. SSH into VPS as the deploy user

```bash
ssh deploy@<vps-ip>
```

### 2. Clone the repository

Clone to `/home/deploy/viko-agent` — the same path the CI `deploy` job operates
on (its `working-directory`).

```bash
git clone git@github.com:viko-nexus/viko-agent.git /home/deploy/viko-agent
cd /home/deploy/viko-agent
cp .env.example .env
# Fill in .env with production values — include the dashboard-auth + VIKO_OWNER_NAME
# keys (see "Required pre-deploy .env keys NOT provisioned by CI" below)
```

### 3. Set up data directory

```bash
mkdir -p data/bridge data/9router data/hermes
echo '{}' > data/bridge/routing.json
```

### 4. Register the self-hosted GitHub Actions runner

The `deploy` job runs **on the VPS itself** via a self-hosted runner (label
`self-hosted,linux,vps`) — there is no SSH deploy key. Install the runner from
the repo's Settings → Actions → Runners, registered under
`~/actions-runner`, running as the `deploy` user with working tree at
`/home/deploy/viko-agent`.

### 5. Build and start

```bash
cd /home/deploy/viko-agent
docker compose build hermes
docker compose --profile full up -d
```

### 6. Initialize (after first start)

```bash
python3 scripts/init-hermes-config.py
python3 scripts/init-9router.py
```

### 7. Pair WhatsApp

```bash
docker logs -f viko-hermes   # scan QR code
```

---

## CI/CD Workflow

The GitHub Actions workflow (`.github/workflows/deploy.yml`) has four jobs:

```
quality → build → deploy → release
```

### Job 1: quality

Runs on every push (`ubuntu-latest`). Checks:
- `ruff check scripts/ patches/ mcp-servers/` — Python lint
- `npm run check` — lint + format + type-check on the bridge JS (`bridge/`)

### Job 2: build

Rebuilds the multi-stage image **only when THIS push touched
`Dockerfile.hermes`, `patches/`, or `bridge/`** (diffed across the push's
commit range). Unrelated pushes (docs, config, scripts) skip the rebuild and
reuse the existing image, avoiding a large re-pull on the VPS.

When a rebuild is needed it builds and pushes to GHCR:

```
ghcr.io/<owner>/viko-agent:latest
```

Uses a registry layer cache
(`ghcr.io/<owner>/viko-agent:buildcache`, `mode=max`) so unchanged layers are
not re-pulled on the VPS. The build exposes its `rebuilt` (true/false) result
as a job output consumed by `deploy`. The image build takes **~15–20 min**.

### Job 3: deploy

Runs on the **self-hosted runner installed on the VPS itself** (label
`[self-hosted, linux, vps]`) — there is no SSH step; the runner executes docker
commands locally. Working directory: `/home/deploy/viko-agent`.

1. `git fetch origin main && git reset --hard origin/main` — sync repo
2. `bash scripts/provision-env.sh` — provision `.env` from CI secrets
3. **If the image was rebuilt** (`rebuilt == true`): `docker login` to GHCR,
   `docker pull ghcr.io/<owner>/viko-agent:latest`, then
   `docker tag … viko-hermes:latest`
4. Restart Hermes:
   - if rebuilt → `docker rm -f viko-hermes` then
     `docker compose --profile full up -d --force-recreate hermes`
   - else → `docker compose --profile full up -d hermes`
5. Status check: `docker ps --filter name=viko`

> **Only the admin `viko-hermes` container is auto-restarted by deploy.** The
> `viko-9router` service and any per-project `viko-hermes-{slug}` containers are
> not touched here (see [Updating a Deployment](#updating-a-deployment)).

### Job 4: release

Runs after `deploy` (`ubuntu-latest`). Uses semantic-release (conventional
commits → semver) to create the Git tag + GitHub release and bump
`package.json`. When a new version is published it re-tags the already-pushed
`:latest` image as `ghcr.io/<owner>/viko-agent:v<version>` and pushes that tag
(no rebuild).

---

## GitHub Actions Secrets

Set these in the GitHub repository settings (Settings → Secrets and variables → Actions).
The `deploy` job consumes them as environment, then `scripts/provision-env.sh`
writes them into the VPS `.env`. The runner is self-hosted on the VPS, so **no
SSH host/user/key secrets are needed.**

| Secret | Value |
|--------|-------|
| `NINEROUTER_JWT_SECRET` | 9router JWT secret (generate with `openssl rand -hex 32`) |
| `NINEROUTER_INITIAL_PASSWORD` | 9router admin password |
| `NINEROUTER_API_KEY_SECRET` | 9router API key signing secret |
| `ANTHROPIC_API_KEY` | Anthropic API key (sk-ant-...) — set in 9router |
| `GROQ_API_KEY` | Groq API key |
| `OPENAI_API_KEY` | 9router client API key (from 9router dashboard → API Keys) |
| `WHATSAPP_HOME_CHANNEL` | WhatsApp group JID for startup notifications |
| `WHATSAPP_OWNER_NUMBER` | Owner's WhatsApp number (only number allowed to issue commands) |
| `VIKO_SSH_PUB` | Viko's dedicated SSH public key (`id_viko`) |
| `VIKO_ISOLATION_GUARD` | `enforce` or `warn` (isolation guard mode) |
| `VIKO_GITHUB_TOKEN` | Fine-grained PAT for onboarding. Arrives as `VIKO_GITHUB_TOKEN` and is written to `.env` as `GITHUB_TOKEN` — the Actions secret name `GITHUB_TOKEN` is reserved (auto-provided for GHCR push) and cannot be overridden. |
| `VIKO_OWNER_NAME` | Owner display name (e.g. `Eksa`), stamped on the owner's CTX line |
| `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` | Admin dashboard login username |
| `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH` | Admin dashboard scrypt password hash (see [Dashboard auth](#dashboard-auth--owner-name-provisioned-from-ci-secrets)) |
| `HERMES_DASHBOARD_BASIC_AUTH_SECRET` | Dashboard session-cookie signing secret (`openssl rand -hex 32`) |

`GITHUB_TOKEN` (the automatic Actions token) is used by `build`/`release` for
GHCR auth; it is not one you set.

---

## Updating a Deployment

Code changes:
```bash
git push origin main
# CI/CD handles the rest
```

Config changes (admin/, hooks/):
```bash
git push origin main
# CI/CD will restart Hermes and pick up changes
```

Patch changes (`patches/`, `bridge/`, or `Dockerfile.hermes`):
```bash
git push origin main
# CI/CD detects the change → rebuilds image → deploys
# Note: image build takes ~15-20 min
```

> **Per-project containers are NOT updated by deploy.** CI only force-recreates
> the admin `viko-hermes` container. Existing `viko-hermes-{slug}` containers
> keep running their previously-generated `config/` + `SOUL.md` on the old base
> image until they are **re-spawned** with `scripts/spawn-hermes.py`. So
> persona / prompt / `TERMINAL_CWD` / relay-token-rotation changes and a new
> base image (e.g. the isolation-guard) only reach project containers on
> re-spawn. The relay scope-gate fix lives in the admin bridge, so it is live as
> soon as the admin container restarts.

---

## How `provision-env.sh` Builds the VPS `.env`

`scripts/provision-env.sh` runs in the `deploy` job after the repo sync and
before `docker compose up`. Its behavior:

- **Upserts** (GitHub secrets are canonical, overriding any local drift):
  `NINEROUTER_JWT_SECRET`, `NINEROUTER_INITIAL_PASSWORD`,
  `NINEROUTER_API_KEY_SECRET`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`,
  `OPENAI_API_KEY`, `WHATSAPP_HOME_CHANNEL`, `WHATSAPP_OWNER_NUMBER`,
  `VIKO_SSH_PUB`, `VIKO_ISOLATION_GUARD`, and `VIKO_GITHUB_TOKEN` →
  written as `GITHUB_TOKEN`. (Empty values are skipped, so a blank secret leaves
  the existing line untouched.)
- **Defaults only when missing** (machine-specific — never overrides an existing
  host): `VIKO_PROJECTS_ROOT` (`/home/viko/projects`), `HERMES_UID` (`1000`),
  `HERMES_GID` (`1000`), `VIKO_BIND_ADDR` (`127.0.0.1`).
- **Pins `VIKO_ISOLATION_GUARD=enforce` when missing** — fail-closed backstop so
  a fresh deploy is locked down even if the CI secret is unset.

### Dashboard auth + owner name (provisioned from CI secrets)

The admin dashboard runs with `HERMES_DASHBOARD_INSECURE=false`, so it needs
credentials or it is auth-locked. These are now provisioned by
`provision-env.sh` from GitHub Actions secrets — set the following secrets:

| Secret | Used for |
|--------|----------|
| `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` | Dashboard login username |
| `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH` | scrypt password hash (no plaintext at rest) |
| `HERMES_DASHBOARD_BASIC_AUTH_SECRET` | Session-cookie signing secret (`openssl rand -hex 32`) |
| `VIKO_OWNER_NAME` | Owner display name stamped on the CTX line so Viko addresses the owner by name |

The dashboard binds `0.0.0.0:9119` (needed for the host port-map), which also
exposes it to every container on the shared docker network — so basic-auth is
the real boundary, not the host bind. Generate the password hash with:

```bash
python -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('YOUR_PASSWORD'))"
```

`docker-compose.yml` wires both `_PASSWORD` (plaintext, for local dev) and
`_PASSWORD_HASH` (preferred in prod); the auth plugin uses the hash when set.

## Provisioning New Environment Variables

When a new secret is needed:

1. Add to `.env.example` with a description
2. Add to `scripts/provision-env.sh` (as either `upsert` or `default_if_missing`)
3. Add to GitHub Actions secrets
4. Add to `deploy.yml` `env:` block

---

## Container Management

```bash
# Check status
docker ps --filter name=viko --format 'table {{.Names}}\t{{.Status}}'

# View logs
docker logs viko-hermes -f --tail 100

# Restart all
docker compose --profile full up -d --force-recreate

# Stop all
docker compose --profile full down

# Check routing table
cat data/bridge/routing.json
```
