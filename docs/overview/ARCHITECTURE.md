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
│  │  patches/whatsapp-bridge.js (port 3000)              │ │
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
         │ relay (token-scoped,      │ OpenAI-compat API
         ▼                           ▼
┌─────────────────┐        ┌──────────────────────────────┐
│  viko-{slug}    │        │  viko-9router (port 20128)    │
│  Hermes-Project │        │                               │
│  per group,     │        │  viko-chat  → Claude Haiku    │
│  on its own     │        │  viko-code  → Claude Sonnet   │
│  viko-{slug}-net│        │  (fallback: Groq Llama)       │
│  isolated:      │        └──────────────────────────────┘
│  ├── memory DB  │
│  ├── SSH key    │
│  └── data dir   │
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

### WhatsApp Bridge (`patches/whatsapp-bridge.js`)

A standalone Node.js process (Baileys library) running inside the admin container.
Two modes controlled by `WHATSAPP_RELAY_MODE` env var:

**Admin mode** (unset): Holds the WA session, reads `routing.json`, dispatches group
messages to per-port queues. Scrubs forged control markers from inbound bodies, then
stamps `[CTX project=slug caller=owner|member sender=…]` on every routed message.
Validates relay tokens for both outbound sends and queue reads (scope gate). Binds on
`0.0.0.0` so per-project relay clients can reach it over the Docker network.

**Relay mode** (`WHATSAPP_RELAY_MODE=true`): No WA session. Proxies all requests to
the admin bridge on behalf of a project container.

### 9router (`viko-9router`)

LLM gateway with model combo routing and API key management. Two combos:
- `viko-chat` — general discussion, analysis (Claude Haiku → Sonnet fallback)
- `viko-code` — code-related tasks (Claude Sonnet → Opus fallback)

Auto-selected by `patches/patch-model-router.py` based on message content.

### Hermes-Project (`viko-{slug}`)

One isolated container per WhatsApp project group (`viko-hermes-{slug}`). Spawned
dynamically by `scripts/spawn-hermes.py`. Uses relay mode bridge to communicate via
the admin.

Isolated by capability, not just by rule: its own Docker network (`viko-{slug}-net`),
own memory database, own per-project SSH key, and its own `data/hermes-{slug}/` data
dir. It mounts only its own project code plus a read-only allowlist of viko-agent
config — never the whole repo, `GITHUB_TOKEN`, `docker.sock`, or `mcp-servers/`. It
cannot read or send to other projects' groups; the relay token scopes it to its one
JID. `patches/isolation-guard.py` verifies these invariants at boot (fail-closed).

---

## Isolation Model

Each project runs on a **dedicated Docker network** `viko-{slug}-net`. The admin
bridge (`viko-hermes`) and `viko-9router` are attached to every project network
(hub-and-spoke), so a project can reach those shared services for relay + LLM but
**cannot** reach a sibling project's container or dashboard at L3. There is no shared
flat network between projects.

```
viko-{slug}-net (one per project, hub-spoke)
  ├── viko-hermes      (admin bridge, attached to every project net)
  ├── viko-9router     (LLM gateway, attached to every project net)
  └── viko-hermes-{slug} (the project — only on its own net)

Project container (viko-hermes-{slug})
  ├── /opt/data        ← data/hermes-{slug}/ bind-mount (config.yaml, SOUL.md, state)
  ├── code mount       ← VIKO_PROJECTS_ROOT/{slug} only (no full-root mount)
  ├── viko-agent config← read-only allowlist: AGENTS.md, rules/, soul/, skills/,
  │                       projects/{slug}/  (NOT .env, data/, or other projects/)
  ├── SSH (read-only)  ← only this project's key + 1-alias config + known_hosts
  ├── TERMINAL_CWD     ← pinned to VIKO_PROJECTS_ROOT/{slug}
  └── relay token      ← scopes this container to its one JID (send AND read)
```

**The relay token is the cryptographic enforcement layer.** Minted fresh on every
(re)spawn (`secrets.token_urlsafe(32)`), stored in `data/bridge/routing.json` (mode
0600), it is scoped to exactly **one JID** for both directions:

- **Sending** — `POST /send`, `/send-media`, `/edit`, `/typing` validate the
  token → its JID; a mismatched `chatId` (or token-less request) is `403`
  (default-deny), so a compromised container can only message its own group.
- **Reading** — `GET /messages` drains only the per-port queue bound to the token's
  JID; passing another project's `?port` is `403` (`cross_project_read_blocked`),
  and a token-less networked read is `403`.

What a project container does **not** get: `GITHUB_TOKEN`, `docker.sock`, or
`mcp-servers/` (which exposes cross-project `ssh_exec`).

### Resource Limits

Each container has explicit Docker memory limits to prevent a single runaway agent session from starving the host:

| Container | `mem_limit` |
|-----------|-------------|
| `viko-hermes` (admin) | 1536 MB |
| `viko-9router` | 512 MB |
| `viko-hermes-{slug}` (project) | 1500 MB |

Python's glibc malloc arena count is capped via `MALLOC_ARENA_MAX=2` in all Hermes containers, reducing baseline RAM usage by 20–40% vs the default (8 arenas per CPU core).

The `[CTX project=… caller=owner|member sender=…]` stamp is injected by the bridge
(not the LLM) and cannot be spoofed; the bridge also scrubs any
`[CTX]`/`[READ-ONLY MEMBER]`/`[Mentioned]` markers a user embeds in raw inbound text
before prepending its own, so the gateway only ever sees bridge-generated markers.

---

## Data Flow

**Incoming message (registered project group):**

1. Message arrives at admin bridge (Baileys), which owns the WA session.
2. Bridge checks `routing.json` — JID found → lookup port + slug.
3. Bridge scrubs any forged control markers from the raw body, then stamps
   `[CTX project=slug caller=owner|member sender=…]` (and `[READ-ONLY MEMBER]` for
   non-owners). These markers are bridge-injected and unspoofable.
4. Message placed in the per-port queue for that project.
5. Hermes-Project's relay polls `GET /messages` with its relay token. The bridge
   serves **only** that token's per-port queue (scope gate; cross-project / token-less
   reads are `403`).
6. **At-least-once delivery (E1):** the bridge tags the served batch with an
   `X-Viko-Batch-Id` header and holds it in-flight. The relay consumes the batch
   locally, then `POST /messages/ack`s the batch id. An unacked batch is re-served on
   the next poll; past a TTL / max-tries the bridge gives up, requeues those messages
   at the head (the gateway dedupes), and resumes draining so a dead relay can't wedge
   the port.
7. Hermes processes with project identity (SOUL.md, rules/, skills/).
8. Hermes sends reply via `POST /send` with its relay token. The bridge runs the scope
   gate (token → JID, path-normalized, default-deny) and only then sends to the WA
   group. A reply to any other `chatId` is `403`.

**Incoming message (unregistered group) from owner:**

1. Message arrives at admin bridge.
2. JID not in `routing.json` → falls through to the Admin LLM.
3. Bridge identifies the owner via LID→phone resolution (WhatsApp now uses LID format;
   the bridge resolves it against session mapping files rather than a literal number).
4. Admin Hermes handles (onboarding or general assistance). Non-owners in unregistered
   groups are ignored.

---

## Security Boundaries

| Boundary | Enforcement |
|----------|-------------|
| Only owner can issue commands | Owner resolved at the bridge (code, not LLM) via LID→phone; non-owner approval tokens dropped |
| Projects cannot see each other | Per-project Docker network `viko-{slug}-net` (hub-spoke) + scoped code/config mounts — no full-root mount, no shared flat network |
| Projects cannot send to other JIDs | Relay token scoped to one JID per token; path-normalized scope gate, default-deny → cross-project `/send` is `403` |
| Projects cannot read other queues | `GET /messages` is token-scoped to the project's per-port queue; cross-project `?port` or token-less networked read is `403` |
| Project containers cannot impersonate | `[CTX]` stamp is bridge-injected (unspoofable); bridge scrubs forged `[CTX]`/`[READ-ONLY]`/`[Mentioned]` markers from inbound bodies |
| Dashboard not scrapable (A2) | Dashboard binds `0.0.0.0` (host port-map), so basic-auth is **required** — gates the session token / API key from other containers on the net |
| No latent project capabilities | Project containers get no `GITHUB_TOKEN`, no `docker.sock`, no `mcp-servers/` mount |
| Spawn cannot escape isolation | Fail-closed slug/JID validation (rejects `/`, `.`, `..`); secrets passed via `--env-file` (mode 0600), not docker-run argv |
| Trusted GitHub host keys | GitHub SSH host keys pinned (not `ssh-keyscan` TOFU) in the per-project `known_hosts` |
| Boot-time isolation check | `patches/isolation-guard.py` runs before the gateway; default `enforce` (fail-closed → container goes inert), includes an active token-less cross-project read probe (a `200` = leak = FAIL) |

---

## VPS Layout

The repo lives in the deploy user's home (`/home/deploy/viko-agent`, per
`deploy.yml`'s `working-directory`). Per-project data, SSH material, and code each
live in their own tree:

```
/home/deploy/
├── viko-agent/                       ← this repo (git clone, updated by CI/CD)
│   └── data/
│       ├── hermes-{slug}/            ← Hermes-Project data dir (mounted at /opt/data)
│       │   ├── config.yaml           ← isolated per-project config (JSON-as-YAML)
│       │   ├── SOUL.md               ← project-scoped Viko identity
│       │   ├── .env                  ← relay mode + WHATSAPP_PORT_FILTER (non-secret)
│       │   ├── home/                 ← in-container HOME (.gitconfig, caches)
│       │   └── platforms/, state, …  ← memory DB + gateway state
│       └── bridge/
│           └── routing.json          ← JID → {port, slug, relay_token} (mode 0600,
│                                        dir 0700, hot-reloaded by the bridge)
├── .viko/ssh/
│   ├── {slug}-deploy[.pub]           ← per-project keypair (source of truth)
│   └── projects/{slug}/              ← mounted read-only at /opt/data/.ssh
│       ├── id_viko[.pub]             ← copy of the project key
│       ├── config                    ← single {slug}-vps/{slug}-prod alias only
│       └── known_hosts               ← pinned GitHub + seeded VPS host keys
└── …
```

Project **code** lives separately under `VIKO_PROJECTS_ROOT/{slug}` (bind-mounted at
the identical path into the container). A single-repo project is the slug dir itself;
a multi-repo project holds one `.git` subdir per repo.
