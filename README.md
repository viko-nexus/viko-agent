# viko-agent

Configuration, templates, and infrastructure for **Viko** — a self-hosted multi-project AI developer
agent powered by [Hermes](https://github.com/NousResearch/hermes-agent) (agent runtime) and
9router (LLM gateway with fallback routing).

---

## How It Works

```
WhatsApp group message
        │
        ▼
  Hermes-Admin (one WA session)
        │
        ├── registered group → Hermes-Project-{slug} (isolated container per project)
        └── unregistered group → onboarding flow
                │
                ├── 9router ──── Claude Haiku / Sonnet (via Anthropic API)
                │               Groq Llama (fallback)
                │
                └── tools ──── git, code editor, browser, SSH deploy
```

Each project gets its own isolated Hermes container with separate memory, SSH keypair,
and config. The admin holds the single WhatsApp session and routes group messages.

---

## Stack

| Component | Role |
|-----------|------|
| Hermes | AI orchestrator — one container per project |
| WhatsApp bridge | Standalone Node.js/Baileys process (admin + relay modes) |
| 9router | LLM gateway — handles model selection and API key management |

All services run in Docker. Runtime data lives in `./data/` (gitignored).

---

## Quick Start

> **VPS RAM:** 8 GB recommended. Each active project agent container uses ~500–700 MB. See [DEPLOYMENT.md](docs/overview/DEPLOYMENT.md) for full resource breakdown.

```bash
git clone git@github.com:viko-nexus/viko-agent.git
cd viko-agent

# Set up environment
cp .env.example .env
# Edit .env — add API keys, WhatsApp owner number, GitHub token

# Build and start
docker compose build hermes
docker compose --profile full up -d

# Verify
docker ps --filter name=viko --format 'table {{.Names}}\t{{.Status}}'

# Initialize 9router model combos (run once after first start)
python3 scripts/init-9router.py

# Initialize Hermes config (run once after Hermes has started once)
python3 scripts/init-hermes-config.py
```

### Local development (one command)

After the image is built once (`docker compose build hermes`), bootstrap the whole
local stack — bind-mounts for rebuild-free iteration, 9router combos + API key sync,
LLM smoke test, and WhatsApp QR pairing — in a single run:

```bash
./scripts/dev-init.sh
```

It is idempotent (safe to re-run) and ends by printing the QR to scan. Dashboards:
**Hermes** → http://localhost:9119 · **9router** → http://localhost:20128
(password = `NINEROUTER_INITIAL_PASSWORD`).

Iterate on the WhatsApp bridge **without rebuilding** (a rebuild takes 15-30 min):

```bash
# edit patches/whatsapp-bridge.js, then:
./scripts/dev-reload-bridge.sh        # ~5-30s
docker exec viko-hermes tail -f /opt/data/whatsapp/bridge.log
```

See [docs/overview/DEVELOPMENT.md](docs/overview/DEVELOPMENT.md#fast-local-iteration-no-rebuild)
for the full workflow and caveats.

---

## Repository Structure

```
viko-agent/
├── admin/          ← Hermes-Admin identity + onboarding skill
├── bridge/         ← WhatsApp bridge (Node.js/Baileys, standalone)
├── patches/        ← Python scripts applied to Hermes image at build time
├── hooks/          ← Event hooks mounted at /opt/data/hooks/
├── scripts/        ← Onboarding, spawning, and init automation
├── mcp-servers/    ← MCP server implementations (registered in config.yaml)
├── skills/         ← Skill files exposed to Hermes-Admin
├── docs/
│   └── overview/   ← Architecture, development, deployment, security docs
├── Dockerfile.hermes      ← Multi-stage build (Hermes + patches + bridge)
├── docker-compose.yml     ← 9router + Hermes services with profiles
├── .env.example           ← Environment variable reference
└── AGENTS.md              ← Hermes-Admin entry point (read by AI agents)
```

---

## Key Design Decisions

**One WA number, many projects.** Hermes-Admin holds the single WhatsApp session and routes
messages to the correct Hermes-Project via `data/bridge/routing.json` (Group JID → port).

**After onboarding, Admin is permanently blind to that group.** The routing check happens first —
if the JID is registered, Admin forwards and stays silent. No exception.

**Per-project isolation.** Each Hermes-Project container mounts only its own project
folder (and a narrow allowlist of the viko-agent repo — never the whole repo, `.env`,
or `data/`). Separate memory DB, per-project SSH keypair, and config. Each container
runs on its own docker network (`viko-{slug}-net`) attached to only the admin bridge
and 9router, so a compromised project can't reach a sibling at L3. Project containers
get **no** `GITHUB_TOKEN` and **no** docker socket — cloning and orchestration are the
admin's job alone.

**Scoped relay tokens.** Each project gets a fresh relay token at every (re)spawn,
passed via an `--env-file` (never the docker-run argv). The admin bridge enforces it
as the real security gate: a token authorizes that one container to **send to** and
**read from** only its single bound group JID — any other chat is `403`. Relay delivery
is at-least-once.

**Boot isolation guard (fail-closed).** Every project container runs
`patches/isolation-guard.py` before the gateway. With `VIKO_ISOLATION_GUARD=enforce`
(the default) a failed isolation invariant leaves the container inert/unhealthy rather
than starting; `warn` and `off` are available for debugging.

**Dashboard auth.** The Hermes dashboard binds `0.0.0.0` for the host port-map, so it
is reachable by peers on a shared docker network. It runs with
`HERMES_DASHBOARD_INSECURE=false` and basic auth
(`HERMES_DASHBOARD_BASIC_AUTH_USERNAME` / `_PASSWORD`, or a scrypt hash) so a project
container can't scrape the session token / API key.

**Owner WA number is always from env.** `WHATSAPP_OWNER_NUMBER` is set via environment variable — never
hardcoded in code or templates. `VIKO_OWNER_NAME` lets the bridge stamp the owner's
real name on each inbound message so Viko addresses the owner by name. This makes the
system self-hostable.

---

## Docs

- [docs/overview/ARCHITECTURE.md](docs/overview/ARCHITECTURE.md) — system design, component breakdown
- [docs/overview/DEVELOPMENT.md](docs/overview/DEVELOPMENT.md) — local dev setup, building, patching
- [docs/overview/DEPLOYMENT.md](docs/overview/DEPLOYMENT.md) — VPS setup, CI/CD, first deploy
- [docs/overview/CONTRIBUTING.md](docs/overview/CONTRIBUTING.md) — contribution guidelines
- [docs/overview/SECURITY.md](docs/overview/SECURITY.md) — security model, responsible disclosure

---

## License

[PolyForm Noncommercial License 1.0.0](LICENSE) — free for personal, educational, and non-commercial use.
© 2026 Viko Nexus
