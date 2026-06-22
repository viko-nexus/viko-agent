# Security

## Security Model

viko-agent is designed around the principle that **the AI cannot be trusted to enforce
security on its own**. All critical security boundaries are enforced at the code layer
(the bridge and isolation guard), not by LLM behavior or prompting.

---

## Trust Boundaries

### Owner Authentication

The `WHATSAPP_OWNER_NUMBER` environment variable is the root of all trust. Only messages from
this WhatsApp number can trigger commands. This check happens in the bridge code
before the LLM is ever invoked:

```
Message arrives → bridge checks sender == WHATSAPP_OWNER_NUMBER → PASS or SILENT IGNORE
```

`WHATSAPP_OWNER_NUMBER` is never hardcoded in committed code. It is set at deploy time via
environment variable, making the system self-hostable without exposing credentials.

### Relay-Token Scope Gate (the security boundary)

The **relay-token scope gate is THE security boundary** — it is enforced in the bridge
code (`patches/whatsapp-bridge.js`), not by LLM behavior or prompting.

The token is generated with `secrets.token_urlsafe(32)` (URL-safe, ~43 chars) — **not**
a 64-char hex string. It is minted fresh on every (re)spawn (`spawn-hermes.py`,
rotatable by design) and stored in `data/bridge/routing.json` at mode `0600` (its
directory at `0700`). The bridge maps each token → the one group JID that container may
talk to, and **default-DENIES** any networked request with an unknown or missing token.

The gate **normalizes the request path** before checking scope — it collapses duplicate
slashes (`//send` → `/send`), strips trailing slashes (`/send/` → `/send`), and
lowercases (`/SEND` → `/send`) — so Express's non-strict, case-insensitive routing
cannot be used to reach a scoped handler while skipping the scope check. Scoped POST
paths are `/send`, `/send-media`, `/edit`, `/typing`.

Loopback callers (the admin Hermes itself, posting to `127.0.0.1`) carry no token and
keep full access; only networked (per-project) callers are subject to the token gate.

### Scoped Reads (A1)

The bridge scopes read endpoints to the token's own project, not just outbound sends:
- `GET /messages` drains **only** the token's own per-port queue — the port is forced
  from the token's JID, so a relay cannot pass an arbitrary `?port` to read (and
  destructively drain) another project's queue.
- `GET /chat/:id`, `GET /group/:jid/participants`, and `GET /media/:file` are scoped by
  token → JID. `/media/:file` additionally checks the file's recorded owning chat and
  **fails closed** on an unknown-owner file.
- A token-less or cross-project read returns `403`.
- `GET /health` stays open for liveness probes but returns only a minimal payload to
  non-loopback callers (internal queue/routing topology is withheld).
- Loopback (admin Hermes) keeps full access on all of the above.

### Project Isolation

Each per-project Hermes container is isolated at several layers:

- **Per-project Docker network (A3):** each project gets its own `viko-{slug}-net`, so
  projects cannot reach each other directly. The admin bridge (`viko-hermes`) and 9router
  (`viko-9router`) are attached to every project network (hub-spoke).
- **No privileged grants:** project containers do **not** receive `GITHUB_TOKEN`, the
  `/var/run/docker.sock` socket, or `mcp-servers/` (which holds the cross-project
  `ssh_exec` gateway).
- **Allowlisted mounts only:** a container mounts its own code (`$VIKO_PROJECTS_ROOT/{slug}`,
  rw) plus a **read-only allowlist** of viko-agent config — `AGENTS.md`, `rules/`,
  `soul/`, `skills/`, and `projects/{slug}` — never the whole repo (which holds `.env`,
  every container's `data/`, and other projects).
- **Pinned terminal cwd:** the agent terminal cwd is pinned via `TERMINAL_CWD` to the
  project's own slug dir.
- **Per-project SSH (C3):** one alias + one key, mounted read-only; GitHub access uses
  per-repo deploy keys.

### Bridge CTX Stamping

The bridge prepends a control tag — `[CTX project=<slug> caller=owner|member sender=<name>]`
— to every inbound message it routes. This tag:
- Is injected by the bridge at the code layer (the LLM cannot forge it) and is stripped
  on outbound so users never see it.
- **Scrubs forged markers from inbound text first:** before prepending its own tag, the
  bridge strips any `[CTX …`, `[READ-ONLY MEMBER …`, or `[Mentioned …` markers a user
  embedded in their raw message body (anti prompt-injection), and strips brackets plus
  CR/LF and `U+2028`/`U+2029` from sender labels — so the only such markers the gateway
  sees are bridge-generated.
- Identifies the owner via WhatsApp LID→phone resolution. Non-owner group members are
  tagged read-only, and lone approval words (`approve`/`yes`/`ok`/`confirm`/`yolo`) from
  non-owners are dropped so a member cannot self-approve a gated command.

### Isolation Guard

`patches/isolation-guard.py` runs at container startup before the gateway. For a project
container (`VIKO_PROJECT_SLUG` set) it asserts the isolation invariants actually hold at
runtime; the admin container (no slug) is a no-op. Its default mode is **enforce** (no
longer `warn`).

Structural checks: `root-scope`, `projects-scope`, `no-env-secrets`, `no-data-dir`,
`no-mcp-gateway`, `no-github-token`, `ssh-single-alias`, `ssh-no-foreign-keys`,
`relay-token-present`.

It also actively probes the admin bridge: `relay-scope-own-group` (the token resolves to
exactly one JID and the expected port) and `bridge-denies-tokenless-read` — a token-less
cross-project read **must** return `403` (only a successful `200` is treated as a real
leak; an unreachable bridge at boot is not hard-failed).

Modes (`VIKO_ISOLATION_GUARD`):
- `enforce` → on failure: tombstone + best-effort alert + go **inert** (gateway never
  starts, container reports unhealthy). **Default — fail-closed.**
- `warn` → on failure: tombstone + log, but continue startup.
- `off` → skip entirely.

### Admin Dashboard Auth (A2)

The admin dashboard binds `0.0.0.0:9119` for the host port-map, which also exposes it to
every container on the docker network — so the host bind alone is not a sufficient
boundary. `HERMES_DASHBOARD_INSECURE=false` and basic-auth are therefore **required**
(cookie/form login). Credentials come from `.env`:
`HERMES_DASHBOARD_BASIC_AUTH_USERNAME` plus either `…_PASSWORD` or `…_PASSWORD_HASH`
(scrypt, preferred in production — no plaintext at rest) and `…_SECRET`.

### Secrets at Spawn

`OPENAI_API_KEY` / `NINEROUTER_KEY` / `HERMES_RELAY_TOKEN` are passed to `docker run` via
a mode-`0600` `--env-file` (deleted right after the run completes), **not** via `-e`
argv — so they don't leak through `ps` or `/proc/<pid>/cmdline` during spawn. Note:
`docker inspect` still exposes a running container's env (unavoidable); the `--env-file`
only closes the argv/ps window at spawn time.

### Input Validation (fail-closed)

Before any side effect, `spawn-hermes.py` validates its inputs:
- `slug` must match `[a-z0-9][a-z0-9-]{0,38}` (lowercase alphanumeric + hyphens, no `/`,
  `.`, or `..`) — it is interpolated into bind-mount sources, so this prevents path
  traversal into sibling/parent dirs.
- `group_jid` must match `<digits>(-<digits>)?@(g.us|s.whatsapp.net)`.

### GitHub SSH Host Keys (pinned)

Per-project `known_hosts` seeding **pins GitHub's three published host keys** rather than
trusting an unauthenticated `ssh-keyscan` (TOFU), which a MITM at onboarding could poison
under the `accept-new` policy. VPS host-key keyscan failures are surfaced on stderr, not
silently swallowed.

---

## Sensitive Data

| Data | Location | Protection |
|------|----------|------------|
| API keys | `.env` | gitignored, provisioned via CI secrets |
| WA session files | `data/hermes/` | gitignored, bind-mounted |
| Per-project DB credentials | `/home/deploy/{slug}/config/project.json` | mode 600, not in env vars |
| Relay tokens | `data/bridge/routing.json` | mode 0600 (dir 0700), gitignored, unique per project, `token_urlsafe(32)` |
| Per-project SSH keys | `~/.viko/ssh/projects/{slug}/id_viko` | mode 600, mounted read-only into the container |
| Spawn secret env-file | transient file under `data/hermes-{slug}/` | mode 0600, deleted right after `docker run` |
| 9router data | `data/9router/` | gitignored, not exposed externally |

**Never commit:**
- `.env` files
- WhatsApp session directories
- `routing.json`
- API keys or tokens
- Phone numbers (including owner number)
- WhatsApp group JIDs

---

## Known Limitations

- WhatsApp session is tied to one phone number. If that number is banned or the
  session expires, the entire system goes offline.
- 9router and the admin dashboard bind to loopback by default (`VIKO_BIND_ADDR=127.0.0.1`).
  Do not expose them publicly without authentication.
- `docker inspect` still exposes a running container's environment. The `--env-file`
  used at spawn only closes the argv/`ps`/`/proc` window — it does not hide secrets from
  `docker inspect`.
- The admin bridge is a hub attached to every per-project network, so for hub traffic
  the **relay-token scope check — not L3 network isolation — is the real cross-project
  gate**. The per-project networks isolate projects from each other, but not from the hub.
- Deleted projects' Docker networks are not auto-pruned.

---

## Responsible Disclosure

If you discover a security vulnerability, please report it privately:

**Email**: eksant@gmail.com  
**Subject**: `[viko-agent] Security disclosure`

Please include:
- Description of the vulnerability
- Steps to reproduce
- Affected versions or components
- Suggested fix (if known)

We aim to respond within 48 hours and will credit researchers in the changelog.
Do not open public GitHub issues for security vulnerabilities.
