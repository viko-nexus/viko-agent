# Architecture

viko-agent is a self-hosted multi-project AI developer agent built on top of
[Hermes](https://github.com/NousResearch/hermes-agent) and a standalone WhatsApp bridge.

---

## System Overview

```
WhatsApp
   │
   ▼
┌──────────────────────────────────────────────────────────┐
│  viko-hermes (Hermes-Admin container)                     │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  bridge/whatsapp-bridge.js (port 3000)               │ │
│  │                                                       │ │
│  │  routing.json check:                                  │ │
│  │    known JID → Hermes-Project (relay, no LLM)         │ │
│  │    unknown JID + owner sender → Admin LLM             │ │
│  │    unknown JID + non-owner → silent ignore            │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  Hermes gateway (port 9119)                               │
│    ├── reads admin/ (SOUL.md, rules/, skills/)            │
│    └── calls 9router for LLM inference                    │
└──────────────────────────────────────────────────────────┘
         │                           │
         │ relay (per-port queue)    │ OpenAI-compat API
         ▼                           ▼
┌─────────────────┐        ┌──────────────────────────────┐
│  viko-{slug}    │        │  viko-9router (port 20128)    │
│  Hermes-Project │        │                               │
│  per group      │        │  viko-chat  → Claude Haiku    │
│                 │        │  viko-code  → Claude Sonnet   │
│  isolated:      │        │  (fallback: Groq Llama)       │
│  ├── memory DB  │        └──────────────────────────────┘
│  ├── SSH key    │
│  └── config/   │
└─────────────────┘
```

---

## Components

### Hermes-Admin (`viko-hermes`)

The central coordinator. Holds the single WhatsApp session. Handles onboarding
of new projects. Does NOT know about or interact with registered project groups.

- Identity: `admin/SOUL.md`
- Authorization: `admin/rules/authorization.md`
- Onboarding: `admin/skills/onboarding.md`

### WhatsApp Bridge (`bridge/`)

A standalone Node.js process (Baileys library) running inside the admin container.
Two modes controlled by `WHATSAPP_RELAY_MODE` env var:

**Admin mode** (unset): Holds the WA session, reads `routing.json`, dispatches group
messages to per-port queues. Stamps `[CTX project=slug caller=owner|member]` on every
routed message. Validates outbound relay tokens.

**Relay mode** (`WHATSAPP_RELAY_MODE=true`): No WA session. Proxies all requests to
the admin bridge on behalf of a project container.

### 9router (`viko-9router`)

LLM gateway with model combo routing and API key management. Two combos:
- `viko-chat` — general discussion, analysis (Claude Haiku → Sonnet fallback)
- `viko-code` — code-related tasks (Claude Sonnet → Opus fallback)

Auto-selected by `patches/patch-model-router.py` based on message content.

### Hermes-Project (`viko-{slug}`)

One isolated container per WhatsApp project group. Spawned dynamically by
`scripts/spawn-hermes.py`. Uses relay mode bridge to communicate via the admin.

Fully isolated: own memory database, SSH keypair, and config directory. Cannot
access other projects' data or send messages to other projects' groups.

---

## Isolation Model

```
Admin container
  └── routing.json: GROUP_JID → port mapping

Project container (viko-slug)
  ├── /opt/data/      ← /home/deploy/slug/config/ bind-mount
  ├── SSH key         ← /home/deploy/slug/.ssh/id_ed25519
  └── relay token     ← only allows sending to this project's JID
```

The relay token is the cryptographic enforcement layer. Even if a project
container is compromised, it can only send to its own registered WhatsApp group.
The `[CTX]` stamp is injected by the bridge (not by LLM) and cannot be spoofed.

---

## Data Flow

**Incoming message (registered project group):**

1. Message arrives at bridge (Baileys)
2. Bridge checks `routing.json` — JID found → lookup port
3. Bridge stamps `[CTX project=slug caller=owner|member]`
4. Message placed in per-port queue
5. Hermes-Project polls bridge → receives message
6. Hermes processes with project identity (SOUL.md, rules/, skills/)
7. Hermes sends reply via bridge `/send` endpoint with relay token
8. Bridge validates token → sends to WA group

**Incoming message (unregistered group) from owner:**

1. Message arrives at bridge
2. JID not in `routing.json` → falls through to Admin LLM
3. Bridge checks sender == WHATSAPP_OWNER_NUMBER
4. Admin Hermes handles (onboarding or general assistance)

---

## Security Boundaries

| Boundary | Enforcement |
|----------|-------------|
| Only owner can issue commands | `WHATSAPP_OWNER_NUMBER` checked at bridge layer (code, not LLM) |
| Projects cannot see each other | Separate HERMES_HOME bind-mounts, no shared network |
| Projects cannot send to other JIDs | Relay token scoped to one JID per token |
| Project containers cannot impersonate | `[CTX]` stamp is bridge-injected, verified by Admin |
| Boot-time isolation check | `patches/isolation-guard.py` runs before gateway |

---

## VPS Layout

```
/home/deploy/
├── viko-agent/         ← this repo (git clone, updated by CI/CD)
├── bridge/
│   └── routing.json    ← group JID → port mapping (hot-reloaded, gitignored)
└── {slug}/
    ├── .ssh/
    │   ├── id_ed25519  ← per-project private key (generated at onboard)
    │   └── id_ed25519.pub
    ├── config/         ← HERMES_HOME for Hermes-Project
    │   ├── SOUL.md
    │   ├── project.json    ← per-project DB credentials (mode 600)
    │   ├── rules/
    │   └── skills/
    └── repo/           ← git clone of the project's GitHub repo
```
