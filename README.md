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

**Per-project isolation.** Each Hermes-Project container mounts only its own `/home/deploy/{slug}/`
folder. Separate memory DB, SSH keypair, and config.

**Owner WA number is always from env.** `OWNER_WA` is set via environment variable — never
hardcoded in code or templates. This makes the system self-hostable.

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
