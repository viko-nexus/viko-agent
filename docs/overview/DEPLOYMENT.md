# Deployment Guide

## Infrastructure Requirements

- VPS with Docker 24+ and Docker Compose v2
- Traefik (or any reverse proxy) for routing — optional for this service
- SSH access for the `deploy` user
- Outbound internet access (for WhatsApp, GitHub, Anthropic/Groq APIs)

---

## First-Time VPS Setup

### 1. SSH into VPS and create project directory

```bash
ssh deploy@<vps-ip>
mkdir -p ~/viko-agent
```

### 2. Clone the repository

```bash
git clone git@github.com:viko-nexus/viko-agent.git ~/viko-agent
cd ~/viko-agent
cp .env.example .env
# Fill in .env with production values
```

### 3. Set up data directory

```bash
mkdir -p data/bridge data/9router data/hermes
echo '{}' > data/bridge/routing.json
```

### 4. Generate SSH deploy key (for CI/CD)

```bash
# On your local machine
ssh-keygen -t ed25519 -C "viko-agent-deploy" -f /tmp/viko-deploy-key -N ""
# Add public key to VPS
ssh deploy@<vps-ip> "echo '$(cat /tmp/viko-deploy-key.pub)' >> ~/.ssh/authorized_keys"
# Add private key to GitHub Actions secrets as VPS_SSH_KEY
```

### 5. Build and start

```bash
cd ~/viko-agent
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

The GitHub Actions workflow has three jobs:

```
quality → build → deploy
```

### Job 1: quality

Runs on every push. Checks:
- `ruff check` on Python files (scripts/, patches/, mcp-servers/)
- `node --check` on JavaScript files (bridge/)

### Job 2: build

Triggered only when `Dockerfile.hermes` or `patches/` changes. Builds the
multi-stage image and pushes to GHCR:

```
ghcr.io/viko-nexus/viko-hermes:latest
```

Uses registry layer cache so unchanged layers are not re-pulled on the VPS.

### Job 3: deploy

Triggered on every push to `main` (after quality passes). SSH into VPS:

1. `git fetch origin main && git reset --hard origin/main` — sync repo
2. `bash scripts/provision-env.sh` — upsert secrets from GitHub Actions into `.env`
3. `docker pull` — if image was rebuilt, pull new image from GHCR
4. `docker compose --profile full up -d --force-recreate hermes` — recreate if rebuilt
5. Health check: `docker ps --filter name=viko`

---

## GitHub Actions Secrets

Set these in the GitHub repository settings (Settings → Secrets and variables → Actions):

| Secret | Value |
|--------|-------|
| `VPS_HOST` | VPS IP address or hostname |
| `VPS_USER` | SSH user (e.g., `deploy`) |
| `VPS_SSH_KEY` | Private key content (ed25519, from key generation above) |
| `NINEROUTER_JWT_SECRET` | 9router JWT secret (generate with `openssl rand -hex 32`) |
| `NINEROUTER_INITIAL_PASSWORD` | 9router admin password |
| `NINEROUTER_API_KEY_SECRET` | 9router API key signing secret |
| `ANTHROPIC_API_KEY` | Anthropic API key (sk-ant-...) |
| `GROQ_API_KEY` | Groq API key |
| `OPENAI_API_KEY` | 9router client API key (from 9router dashboard → API Keys) |
| `WHATSAPP_HOME_CHANNEL` | WhatsApp group JID for startup notifications |
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions (for GHCR push) |
| `VIKO_ISOLATION_GUARD` | `enforce` or `warn` (isolation guard mode) |

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

Patch changes (patches/ or Dockerfile.hermes):
```bash
git push origin main
# CI/CD detects Dockerfile/patches change → rebuilds image → deploys
# Note: image build takes ~15-20 min
```

---

## Provisioning New Environment Variables

When a new secret is needed:

1. Add to `.env.example` with a description
2. Add to `scripts/provision-env.sh` (as either `upsert` or `default_if_missing`)
3. Add to GitHub Actions secrets
4. Add to `deploy.yml` `envs:` list and `environment:` block

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
