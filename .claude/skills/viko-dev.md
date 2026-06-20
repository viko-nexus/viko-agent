---
name: viko-dev
description: >
  Guide for working on the viko-agent repository. Read this before making changes
  to admin/, patches/, scripts/, bridge/, or Dockerfile.hermes. Covers the template
  variable system, how onboarding works end-to-end, container naming conventions,
  routing.json format, and how to safely test changes without breaking live containers.
  Use when editing any infrastructure, patches, or scripts in this repo.
---

# viko-agent Developer Guide

## What Lives Where

| Folder | Purpose | Rebuild required? |
|--------|---------|-------------------|
| `admin/` | Hermes-Admin identity + onboard skill | Restart viko-hermes container |
| `patches/` | Python scripts applied to Hermes image at build time | Yes — `docker build` |
| `bridge/` | Standalone WhatsApp bridge (Node.js/Baileys) | Yes — `docker build` |
| `hooks/` | Event hooks, hot-mounted at `/opt/data/hooks/` | Restart container |
| `scripts/` | Called by Hermes-Admin or run manually on VPS | No — scripts run directly |
| `mcp-servers/` | MCP server implementations mounted into container | Restart container |
| `skills/` | Skill files exposed to Hermes-Admin | Restart container |
| `Dockerfile.hermes` | Multi-stage Hermes build | Yes — on every Dockerfile change |
| `docker-compose.yml` | 9router + Hermes service definitions | Recreate if config changes |

## Template Variable System

Templates in `admin/` (and any future `templates/`) use `{{VARIABLE_NAME}}` placeholders.
They are replaced by `scripts/onboard.py` at onboard time.

Available variables:
- `{{PROJECT_NAME}}` — display name (e.g., "My Project")
- `{{PROJECT_SLUG}}` — identifier (e.g., "my-project")
- `{{PROJECT_GITHUB}}` — GitHub repo URL
- `{{DEPLOY_HOST}}` — deploy VPS hostname or IP
- `{{DEPLOY_USER}}` — SSH user on deploy VPS
- `{{WHATSAPP_OWNER_NUMBER}}` — filled from WHATSAPP_OWNER_NUMBER env var at onboard time (never hardcoded)
- `{{MEMBER_WA_LIST}}` — comma-separated member WA numbers
- `{{BLOCKED_WA_LIST}}` — comma-separated blocked numbers (empty initially)

Never hardcode project-specific values or WA numbers — templates must be self-hostable.

## Container Naming Convention

```
viko-hermes     ← Hermes-Admin (always)
viko-9router    ← 9router LLM gateway (always)
viko-{slug}     ← Hermes-Project per project (e.g., viko-my-project)
```

`VIKO_NAME` env var is the prefix (default: `viko`). Can be overridden for multi-instance hosts.

## routing.json Format

Lives at `data/bridge/routing.json` (gitignored, deployment-specific).

```json
{
  "GROUP_JID@g.us": {
    "slug": "project-slug",
    "port": 3001,
    "relay_token": "64-char-hex-token"
  }
}
```

Hot-reloaded by the bridge — no restart needed after editing.
Port range for project containers: 3001–3999 (3000 is reserved for Admin bridge).

## VPS Project Workspace Layout

```
/home/deploy/
├── viko-agent/             ← this repo (git clone)
├── bridge/
│   └── routing.json        ← group JID → port mapping (hot-reloaded)
└── {slug}/
    ├── .ssh/
    │   ├── id_ed25519      ← private key (generated at onboard time)
    │   └── id_ed25519.pub
    ├── config/             ← HERMES_HOME for Hermes-Project
    │   ├── SOUL.md
    │   ├── project.json
    │   ├── rules/
    │   └── skills/
    └── repo/               ← git clone of project's GitHub repo
```

## Making Changes Safely

### Editing patches/ or bridge/
Requires image rebuild and container recreate:
```bash
docker compose build hermes
docker compose --profile full up -d --force-recreate hermes
```

### Editing admin/ or hooks/ or mcp-servers/
Only needs a container restart (files are bind-mounted or baked into config):
```bash
docker compose --profile full up -d --force-recreate hermes
```

### Editing scripts/
No rebuild. Scripts run directly from the repo clone on the VPS.
Test locally first with a dummy slug before deploying.

## Testing Onboarding Locally (Dry Run)

```bash
WHATSAPP_OWNER_NUMBER=<your-number> python3 scripts/onboard.py --dry-run \
  --name "TestProject" --slug "testproject" \
  --github "https://github.com/example/repo" \
  --vps-host "localhost" --vps-user "deploy" \
  --member "<wa-number>" \
  --group-jid "fake@g.us"
```

## Common Operations

```bash
# Build Hermes image
docker compose build hermes

# Start everything
docker compose --profile full up -d

# Restart Hermes only (after admin/ or config changes)
docker compose --profile full up -d --force-recreate hermes

# Pair WhatsApp (scan QR in logs — run once on first deploy)
docker logs -f viko-hermes

# View all active project containers
docker ps --filter name=viko --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Check routing table
cat data/bridge/routing.json

# Tail project container logs
docker logs viko-{slug} -f

# Reinitialize Hermes config after data/hermes/ wipe
python3 scripts/init-hermes-config.py

# Reinitialize 9router model combos
python3 scripts/init-9router.py
```
