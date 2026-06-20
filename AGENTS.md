# viko-agent — Agent Development Guide

This file is loaded by AI coding agents (Claude Code, etc.) when working in this repo.
It provides context about the system architecture and how to make changes safely.

## What This Repo Is

Configuration, templates, and infrastructure for **Viko** — a self-hosted multi-project AI developer
agent. One isolated Hermes container per WhatsApp group per project.

## Key Architecture Points

- **Hermes-Admin**: holds the single WA session, routes messages, handles onboarding
- **Hermes-Project**: one container per project, fully isolated (volume, memory, SSH key)
- **9router**: shared LLM gateway with two combos (viko-chat / viko-code)
- **routing.json**: Group JID → project container port mapping (hot-reloaded, gitignored)

Full architecture: [docs/overview/ARCHITECTURE.md](docs/overview/ARCHITECTURE.md)

## What Lives Where

| Folder | Purpose | Requires rebuild? |
|--------|---------|-------------------|
| `admin/` | Hermes-Admin identity + onboard skill | Restart viko-hermes container |
| `bridge/` | WhatsApp bridge (Node.js, Baileys) — standalone process | Yes — docker build |
| `patches/` | Python scripts run at container startup (isolation-guard, model-router) | Yes — docker build |
| `hooks/` | Event hooks, mounted at `/opt/data/hooks/` | Restart container |
| `scripts/` | Called by Admin or run manually on VPS | No — run directly |
| `mcp-servers/` | MCP server implementations | Yes — docker build |
| `Dockerfile.hermes` | Multi-stage Hermes build | Yes on any change |
| `docker-compose.yml` | 9router + Hermes service definitions | Recreate if changed |

## Bridge Architecture

The WhatsApp bridge (`bridge/whatsapp-bridge.js`) is a standalone Node.js process.

```
Admin container:
  bridge/whatsapp-bridge.js (WHATSAPP_RELAY_MODE unset)
    ├── Holds the single WA session (Baileys)
    ├── Reads routing.json — routes registered group messages to per-port queues
    ├── Stamps [CTX project=slug caller=owner|member] on every routed message
    └── Validates outbound relay tokens (each project can only send to its own JID)

Project container:
  bridge/whatsapp-bridge.js (WHATSAPP_RELAY_MODE=true)
    ├── No WA session — proxies all requests to admin bridge
    └── Filters polling by port (WHATSAPP_PORT_FILTER)
```

routing.json format (lives at `data/bridge/routing.json` — gitignored):
```json
{
  "GROUP_JID@g.us": {
    "port": 3001,
    "slug": "project-slug",
    "relay_token": "64-char-hex"
  }
}
```

## Template Variable System

Templates use `{{VARIABLE_NAME}}` — replaced by `scripts/onboard.py` at onboard time.

Available variables:
- `{{PROJECT_NAME}}` — display name (e.g. "My Project")
- `{{PROJECT_SLUG}}` — identifier (e.g. "my-project")
- `{{PROJECT_GITHUB}}` — GitHub repo HTTPS URL
- `{{DEPLOY_HOST}}` — deploy VPS hostname or IP
- `{{DEPLOY_USER}}` — SSH user on deploy VPS
- `{{DEPLOY_PORT}}` — SSH port on deploy VPS (default: 22)
- `{{DEPLOY_FOLDER}}` — working folder for deploy commands (default: `/home/deploy/{slug}`)
- `{{APP_CONTAINER}}` — Docker container name on deploy VPS. Default: `{slug}-api`
- `{{WHATSAPP_OWNER_NUMBER}}` — filled from WHATSAPP_OWNER_NUMBER env var at onboard time (never hardcoded)
- `{{MEMBER_WA_LIST}}` — comma-separated member WA numbers
- `{{BLOCKED_WA_LIST}}` — comma-separated blocked numbers

**Never hardcode project-specific values, phone numbers, or group JIDs in committed files.**

## Security Rules (do not break these)

1. `WHATSAPP_OWNER_NUMBER` must always come from env var — never appear as a literal phone number in code
2. `bridge/whatsapp-bridge.js` relay token scope check is the real security gate — never bypass
3. `patches/isolation-guard.py` must verify HERMES_HOME is scoped to the correct slug
4. `project.json` stores DB credentials — must have mode 600, never read from env vars
5. Relay tokens in routing.json are unique per project — never share tokens between projects
6. `channel_prompts` in Hermes config must not be committed — they contain deployment-specific JIDs

## Container Naming

```
{VIKO_NAME}-hermes     ← Hermes-Admin
{VIKO_NAME}-9router    ← LLM gateway
{VIKO_NAME}-{slug}     ← Hermes-Project per project
```

`VIKO_NAME` defaults to `viko`. Configurable in `.env` for multi-instance hosts.

## Dry-Run Testing

Test onboarding without a real WA group:
```bash
WHATSAPP_OWNER_NUMBER=<your-number> python3 scripts/onboard.py \
  --name "Test" --slug testproject \
  --github https://github.com/example/repo \
  --vps-host localhost --vps-user deploy \
  --member <your-number> \
  --group-jid "fake@g.us" \
  --dry-run
```

## Common Operations

```bash
# Build Hermes image
docker compose build hermes

# Start 9router + Hermes
docker compose --profile full up -d

# Restart Hermes only (after admin/ or config changes)
docker compose --profile full up -d --force-recreate hermes

# Pair WhatsApp (scan QR in logs — run once on first deploy)
docker logs -f viko-hermes

# Spawn a project container manually
VIKO_NAME=viko python3 scripts/spawn-hermes.py <slug> <group_jid>

# View routing table
cat data/bridge/routing.json

# View project container logs
docker logs viko-<slug> -f

# Configure 9router model combos (run after 9router is up)
python3 scripts/init-9router.py
```

## Do Not

- Do not hardcode `WHATSAPP_OWNER_NUMBER`, phone numbers, or group JIDs in committed files
- Do not run `apt install`, `pip install`, `npm install -g` inside containers at runtime
- Do not bypass the relay token scope check in `bridge/whatsapp-bridge.js`
- Do not add `channel_prompts` to `scripts/init-hermes-config.py` — configure per-deployment
