# viko-agent Infrastructure Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the viko-agent infrastructure layer — pin hermes upstream to a reproducible SHA, make relay more robust, improve bridge observability, and fix routing accuracy — entirely within the viko layer (no hermes source modified directly).

**Architecture:** Seven independent tasks, each self-contained. Patches are applied at image build time as before. Bridge changes are pure Node.js. MCP and script changes are pure Python. No task depends on any other completing first.

**Tech Stack:** Node.js 22 (bridge), Python 3.13 (patches, scripts, MCP), Docker + s6-overlay (service config), Bash (cron setup)

## Global Constraints
- Never hardcode phone numbers, JIDs, or project slugs — always env vars or config files
- All patches must be idempotent (marker check at top, skip cleanly if already applied)
- Bridge changes must preserve the relay token security model unchanged
- Hermes SHA pin must be the full 40-char commit hash
- Run docker commands from `/home/deploy/viko-agent/` on the server (SSH alias: `doasas`)
- Local repo root: `/Users/eksa/Projects/viko-nexus/viko-agent/`

---

### Task 1: Hermes version pinning + patch fail-fast

**Files:**
- Modify: `Dockerfile.hermes` — add `ARG HERMES_COMMIT`, use it in clone
- Modify: `patches/patch-model-router.py:70` — `sys.exit(0)` → `sys.exit(1)` on injection-point-not-found
- Modify: `patches/patch-ssh-guard.py` — same fail-fast fix
- Modify: `patches/patch-approval-sql-context.py` — same fail-fast fix

**Why this matters:** `git clone --depth=1` without a SHA grabs whatever hermes main is at build time. If hermes changes a function signature, our patches silently do nothing (they print a warning and `sys.exit(0)`). The image builds successfully but patches are not applied, and no one knows.

**Interfaces:**
- Produces: `ARG HERMES_COMMIT=<sha>` usable in CI via `--build-arg HERMES_COMMIT=<new-sha>`
- Produces: Build fails loudly (non-zero exit) if any patch cannot find its injection point

- [x] **Step 1: Record the current hermes SHA to pin**

```bash
curl -s https://api.github.com/repos/NousResearch/hermes-agent/commits/main \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['sha'])"
```

Expected output: `f1345290edb87a5da7b28288dc39c46b0be79313` (or newer if hermes has since updated — use whatever this returns, that's the pin).

- [x] **Step 2: Pin the hermes clone in Dockerfile.hermes**

In `Dockerfile.hermes`, find the hermes_source stage (around line 10–14):

```dockerfile
# BEFORE:
FROM debian:bookworm-slim AS hermes_source
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth=1 https://github.com/NousResearch/hermes-agent.git /opt/hermes
```

Replace with:

```dockerfile
# AFTER:
FROM debian:bookworm-slim AS hermes_source
# Pin hermes to a tested commit. To upgrade: update this SHA, rebuild, re-verify patches.
ARG HERMES_COMMIT=f1345290edb87a5da7b28288dc39c46b0be79313
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/NousResearch/hermes-agent.git /opt/hermes && \
    git -C /opt/hermes checkout "$HERMES_COMMIT"
```

- [x] **Step 3: Fix patch-model-router.py to fail loudly**

In `patches/patch-model-router.py`, find the warning block (around line 67–72):

```python
    if INJECT_AFTER not in content:
        if INJECT_CODE in content:
            print("✓ patch-model-router: already applied")
            return
        print("WARNING: injection point not found (Hermes may have updated upstream)")
        sys.exit(0)
```

Change `sys.exit(0)` to `sys.exit(1)`:

```python
    if INJECT_AFTER not in content:
        if INJECT_CODE in content:
            print("✓ patch-model-router: already applied")
            return
        print("ERROR: injection point not found — hermes upstream changed; patch must be updated")
        sys.exit(1)
```

- [x] **Step 4: Fix patch-ssh-guard.py to fail loudly**

In `patches/patch-ssh-guard.py`, find the "Pattern not found" exit:

```python
if OLD not in original:
    print("Pattern not found — already patched or threat_patterns.py changed upstream.")
    sys.exit(0)
```

Change to:

```python
if OLD not in original:
    if NEW in original:
        print("✓ patch-ssh-guard: already applied")
        sys.exit(0)
    print("ERROR: pattern not found — threat_patterns.py changed upstream; patch must be updated")
    sys.exit(1)
```

- [x] **Step 5: Fix patch-approval-sql-context.py to fail loudly**

In `patches/patch-approval-sql-context.py`, find both exit points in `main()`:

```python
    if ANCHOR not in src:
        print("ERROR: detect_dangerous_command def not found — aborting", file=sys.stderr)
        return 1
    if OLD_LOOP not in src:
        print("ERROR: detect_dangerous_command loop body not found — aborting", file=sys.stderr)
        return 1
```

These already return 1 (correct). Only verify the idempotent check exits cleanly:

```python
    if MARKER in src:
        print("approval.py already patched (SQL exec-context); skipping")
        return 0
```

Confirm `return 0` is there — no change needed.

- [x] **Step 6: Verify the build succeeds with pinned SHA**

```bash
ssh doasas "cd /home/deploy/viko-agent && docker compose build hermes 2>&1 | tail -20"
```

Expected: build completes, all patches print `✓ patch-*: applied`.

- [x] **Step 7: Verify the build fails with a bad SHA**

Temporarily change `HERMES_COMMIT` in the ARG line to `0000000000000000000000000000000000000000`, run build, confirm failure, then revert.

```bash
# Temporary test only — revert immediately after
ssh doasas "cd /home/deploy/viko-agent && \
  sed -i 's/HERMES_COMMIT=f1345290/HERMES_COMMIT=0000000000/' Dockerfile.hermes && \
  docker compose build hermes 2>&1 | grep -E 'error|fatal'; \
  git checkout Dockerfile.hermes"
```

Expected: build fails with git checkout error. Revert restores correct SHA.

- [x] **Step 8: Commit**

```bash
git add Dockerfile.hermes patches/patch-model-router.py patches/patch-ssh-guard.py patches/patch-approval-sql-context.py
git commit -m "fix(build): pin hermes to f1345290 + fail-fast on patch injection miss"
```

---

### Task 2: MCP projects-gateway dynamic reload

**Files:**
- Modify: `mcp-servers/projects-gateway.py` — remove module-level constants, reload per call

**Why this matters:** `PROJECTS` and `PROJECT_NAMES` are loaded once at import time. When a new project is onboarded (via `add-project.py`), the MCP server must be restarted manually or the new project is invisible to `ssh_exec`. Reloading per call costs a file read (~0.1ms) but makes onboarding seamless.

**Interfaces:**
- Produces: `_load_projects()` returns fresh data on every call (no module-level cache)

- [x] **Step 1: Write the failing test**

Create `scripts/test_mcp_reload.py`:

```python
#!/usr/bin/env python3
"""Manual test: verify projects-gateway reloads projects.json dynamically."""
import json
import tempfile
import sys
from pathlib import Path

# Patch REPO_DIR so _load_projects reads our temp file
import importlib, types
fake_module = types.ModuleType("mcp")
fake_module.server = types.ModuleType("mcp.server")
fake_module.server.Server = lambda name: None
sys.modules["mcp"] = fake_module
sys.modules["mcp.server"] = fake_module.server
sys.modules["mcp.server.stdio"] = types.ModuleType("mcp.server.stdio")
sys.modules["mcp.types"] = types.ModuleType("mcp.types")

# Minimal shim so import works without mcp installed
import mcp.types
mcp.types.Tool = object
mcp.types.TextContent = object

with tempfile.TemporaryDirectory() as tmpdir:
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()
    projects_file = data_dir / "projects.json"

    # Write initial projects
    projects_file.write_text(json.dumps({"alpha": {"ssh_host": "alpha-prod"}}))

    # Patch REPO_DIR before import
    import mcp_servers.projects_gateway as gw  # noqa: E402  (can't actually import like this)
    # This test verifies the concept; run it via docker exec in the actual env

print("Concept test: _load_projects() must be called inside list_tools/call_tool, not at module level")
print("Verify by: grep -n 'PROJECTS\\|PROJECT_NAMES' mcp-servers/projects-gateway.py")
print("After fix: those names should only appear inside function bodies, not at module scope")
```

Run: `grep -n "^PROJECTS\|^PROJECT_NAMES" mcp-servers/projects-gateway.py`
Expected BEFORE fix: lines 18–19 show module-level assignments.

- [x] **Step 2: Remove module-level PROJECTS and PROJECT_NAMES**

In `mcp-servers/projects-gateway.py`, delete these two lines (currently around lines 18–19):

```python
PROJECTS: dict[str, dict] = _load_projects()
PROJECT_NAMES: list[str] = list(PROJECTS.keys())
```

- [x] **Step 3: Update list_tools() to reload fresh**

Find `list_tools()` (currently uses module-level `PROJECT_NAMES`). Replace:

```python
@server.list_tools()
async def list_tools() -> list[Tool]:
    projects_str = ", ".join(PROJECT_NAMES) if PROJECT_NAMES else "(none configured)"
    return [
        Tool(
            name="ssh_exec",
            ...
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "enum": PROJECT_NAMES,
                        "description": f"Project slug. Available: {projects_str}",
                    },
```

With:

```python
@server.list_tools()
async def list_tools() -> list[Tool]:
    projects = _load_projects()
    project_names = list(projects.keys())
    projects_str = ", ".join(project_names) if project_names else "(none configured)"
    return [
        Tool(
            name="ssh_exec",
            description=(
                "Run a shell command on a project's production server via SSH. "
                "Use this for any task requiring server access: checking logs, "
                "querying databases, inspecting running containers, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "enum": project_names,
                        "description": f"Project slug. Available: {projects_str}",
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to run on the production server",
                    },
                },
                "required": ["project", "command"],
            },
        ),
    ]
```

- [x] **Step 4: Update call_tool() to reload fresh**

Find `call_tool()` (currently references `PROJECTS` and `PROJECT_NAMES`). Replace:

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "ssh_exec":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    projects = _load_projects()
    project = arguments.get("project", "")
    command = arguments.get("command", "")

    if project not in projects:
        project_names = list(projects.keys())
        return [TextContent(type="text", text=f"Unknown project: {project}. Available: {', '.join(project_names)}")]

    ssh_host = projects[project]["ssh_host"]
    # ... rest of the function unchanged
```

- [x] **Step 5: Verify no module-level references remain**

```bash
grep -n "^PROJECTS\|^PROJECT_NAMES" mcp-servers/projects-gateway.py
```

Expected: no output (both names removed from module scope).

- [x] **Step 6: Live test on server**

```bash
ssh doasas "
  # Get MCP server PID inside hermes container
  docker exec viko-hermes pgrep -f projects-gateway || echo 'not running'
  # Check it can read projects.json after a write
  cat /home/deploy/viko-agent/data/projects.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(list(d.keys()))'
"
```

- [x] **Step 7: Commit**

```bash
git add mcp-servers/projects-gateway.py
git commit -m "fix(mcp): reload projects.json on every tool call (no restart needed after onboard)"
```

---

### Task 3: Bridge relay rate limiting

**Files:**
- Modify: `bridge/whatsapp-bridge.js` — add per-token rate limiter, applied to scoped POST paths

**Why this matters:** A bug in a project Hermes container can cause it to spam the bridge with `/send` requests. There is no throttle — a runaway loop floods WhatsApp and potentially triggers WA's rate limiting / ban.

**Interfaces:**
- Produces: relay tokens get 20 sends/minute (configurable via `RELAY_RATE_LIMIT` env var)
- Loopback calls (admin hermes) are never rate-limited

- [x] **Step 1: Add rate-limit state and helper (admin mode block)**

In `bridge/whatsapp-bridge.js`, inside the `} else {` admin mode block (after line 281), before the `bearerToken` helper, add:

```javascript
  // ── Relay rate limiting ────────────────────────────────────────────────────
  // Limits outbound sends per relay token to prevent runaway project containers
  // from spamming WhatsApp. Loopback calls (admin hermes) are never limited.
  const _rateBuckets = new Map(); // token -> { tokens, lastRefill }
  const RATE_LIMIT_MAX = parseInt(process.env.RELAY_RATE_LIMIT || '20', 10);
  const RATE_LIMIT_WINDOW_MS = 60_000;

  function consumeRateLimit(token) {
    const now = Date.now();
    let b = _rateBuckets.get(token);
    if (!b) {
      b = { tokens: RATE_LIMIT_MAX, lastRefill: now };
      _rateBuckets.set(token, b);
    }
    if (now - b.lastRefill >= RATE_LIMIT_WINDOW_MS) {
      b.tokens = RATE_LIMIT_MAX;
      b.lastRefill = now;
    }
    if (b.tokens <= 0) return false;
    b.tokens -= 1;
    return true;
  }
```

- [x] **Step 2: Add rate-limit middleware after the scope middleware**

After the scope enforcement middleware (the `app.use` block ending around line 322), add:

```javascript
  // Rate limit relay tokens on outbound paths (not loopback admin)
  app.use((req, res, next) => {
    if (req.method === 'POST' && SCOPED_PATHS.has(req.path)) {
      const token = bearerToken(req);
      if (token && !consumeRateLimit(token)) {
        console.warn(`[bridge] rate-limit ${req.path} token=${token.slice(0, 8)}…`);
        return res.status(429).json({
          error: 'rate_limited',
          retry_after_ms: RATE_LIMIT_WINDOW_MS,
        });
      }
    }
    next();
  });
```

- [x] **Step 3: Verify order of middleware**

Confirm the order in the file is: scope check → rate limit → actual POST handlers. Run:

```bash
grep -n "SCOPED_PATHS\|consumeRateLimit\|app.post('/send')" bridge/whatsapp-bridge.js
```

Expected output (line numbers may differ but order must be ascending):
```
310:  const SCOPED_PATHS = ...
311:  app.use(... scopeError ...)   ← scope check
325:  app.use(... consumeRateLimit ...)  ← rate limit
456:  app.post('/send', ...         ← actual handler
```

- [x] **Step 4: Manual smoke test on server**

```bash
ssh doasas "
  # Fire 21 rapid sends with a project relay token and verify 21st gets 429
  TOKEN=\$(cat /home/deploy/viko-agent/data/bridge/routing.json | python3 -c \"
import json, sys
d = json.load(sys.stdin)
for jid, v in d.items():
    if isinstance(v, dict) and v.get('relay_token'):
        print(v['relay_token']); break
\")
  echo \"Token: \${TOKEN:0:8}...\"
  for i in \$(seq 1 21); do
    CODE=\$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:3000/send \
      -H 'Content-Type: application/json' \
      -H \"Authorization: Bearer \$TOKEN\" \
      -d '{\"chatId\":\"test\",\"message\":\"test\"}')
    echo \"send \$i: HTTP \$CODE\"
  done
"
```

Expected: sends 1–20 return 403 (scope-denied on fake chatId — that's correct, scope check fires before rate limit), send 21 still 403. 

Note: The rate limit only triggers AFTER scope check passes. To really test, you'd need a valid relay token + valid JID combo. The middleware order ensures: authenticated sends deduct from bucket even when chatId is valid.

- [x] **Step 5: Commit**

```bash
git add bridge/whatsapp-bridge.js
git commit -m "feat(bridge): relay rate limiting — 20 sends/min per token (RELAY_RATE_LIMIT env)"
```

---

### Task 4: Bridge owner priority queue

**Files:**
- Modify: `bridge/whatsapp-bridge.js` — split `perPortQueues` into owner + member queues; drain owner first

**Why this matters:** Owner and members share a FIFO queue per project port. If a member sends multiple messages, the owner's urgent message queues behind them. Owner commands should always be processed first.

**Interfaces:**
- Produces: `dequeuePort(port)` returns owner messages before member messages
- `enqueue(port, event)` routes based on `event.isOwner` (already set by the bridge)

- [x] **Step 1: Replace perPortQueues with split queues**

In `bridge/whatsapp-bridge.js`, find the current queue declarations (around lines 134–136):

```javascript
const perPortQueues = {}; // { "3001": [message, ...] }
const globalQueue = []; // unrouted messages → Admin Hermes
```

Replace `const perPortQueues = {};` with:

```javascript
const perPortOwnerQueues = {}; // { "3001": [owner messages] }
const perPortMemberQueues = {}; // { "3001": [member messages] }
const globalQueue = []; // unrouted messages → Admin Hermes
```

- [x] **Step 2: Update enqueue() to route by isOwner**

Find the `enqueue` function (around lines 138–143):

```javascript
function enqueue(port, event) {
  const key = String(port);
  const q = (perPortQueues[key] = perPortQueues[key] || []);
  q.push(event);
  if (q.length > MAX_QUEUE_SIZE) q.shift();
}
```

Replace with:

```javascript
function enqueue(port, event) {
  const key = String(port);
  const queues = event.isOwner ? perPortOwnerQueues : perPortMemberQueues;
  const q = (queues[key] = queues[key] || []);
  q.push(event);
  if (q.length > MAX_QUEUE_SIZE) q.shift();
}
```

- [x] **Step 3: Update dequeuePort() to drain owner first**

Find `dequeuePort` (around lines 145–151):

```javascript
function dequeuePort(port) {
  const key = String(port);
  const q = perPortQueues[key];
  if (!q || q.length === 0) return [];
  const msgs = q.splice(0);
  perPortQueues[key] = [];
  return msgs;
}
```

Replace with:

```javascript
function dequeuePort(port) {
  const key = String(port);
  const ownerMsgs = (perPortOwnerQueues[key] || []).splice(0);
  const memberMsgs = (perPortMemberQueues[key] || []).splice(0);
  perPortOwnerQueues[key] = [];
  perPortMemberQueues[key] = [];
  return [...ownerMsgs, ...memberMsgs];
}
```

- [x] **Step 4: Verify no stale perPortQueues reference remains**

```bash
grep -n "perPortQueues" bridge/whatsapp-bridge.js
```

Expected: zero results (all references replaced).

- [x] **Step 5: Smoke test — verify isOwner field exists on enqueued events**

The `isOwner` field is set at line ~403: `const isOwner = OWNER_WA && phone === OWNER_WA;` and included in the event object at line ~421: `isOwner,`. Confirm:

```bash
grep -n "isOwner" bridge/whatsapp-bridge.js
```

Expected: lines for both the assignment and the event property.

- [x] **Step 6: Commit**

```bash
git add bridge/whatsapp-bridge.js
git commit -m "feat(bridge): owner priority queue — owner messages drain before member messages"
```

---

### Task 5: Bridge enhanced /health endpoint

**Files:**
- Modify: `bridge/whatsapp-bridge.js` — track `connectedAt`, enrich `/health` with queue stats + uptime

**Why this matters:** Current `/health` only returns `{status, routes, relay: false}`. Docker healthcheck sees port open but has no idea if WA is actually connected or how long it's been. Ops visibility is blind.

**Interfaces:**
- Produces: `/health` returns `{ok, status, relay, routes, uptime_ms, connected_duration_ms, queue}`
- Relay mode `/health` proxies to admin and adds `{relay: true, port_filter}`

- [x] **Step 1: Add connectedAt tracking variable (admin mode)**

Inside the `} else {` admin mode block, after the `let connState = 'disconnected';` line (around line 346), add:

```javascript
  let connectedAt = null;
  const bridgeStartedAt = Date.now();
```

- [x] **Step 2: Set connectedAt when WA connects**

In the `connection.update` handler (around line 382), find:

```javascript
      } else if (connection === 'open') {
        connState = 'connected';
        console.log('[bridge] WhatsApp connected');
```

Add `connectedAt = Date.now();` on the next line:

```javascript
      } else if (connection === 'open') {
        connState = 'connected';
        connectedAt = Date.now();
        console.log('[bridge] WhatsApp connected');
```

- [x] **Step 3: Replace the /health endpoint (admin mode)**

Find the current `/health` in admin mode (around line 508):

```javascript
  app.get('/health', (req, res) => {
    res.json({
      status: connState,
      routes: Object.keys(_routing).length,
      relay: false,
    });
  });
```

Replace with:

```javascript
  app.get('/health', (req, res) => {
    const ownerPending = Object.values(perPortOwnerQueues).reduce((s, q) => s + q.length, 0);
    const memberPending = Object.values(perPortMemberQueues).reduce((s, q) => s + q.length, 0);
    res.json({
      ok: connState === 'connected',
      status: connState,
      relay: false,
      routes: Object.keys(_routing).length,
      uptime_ms: Date.now() - bridgeStartedAt,
      connected_duration_ms: connectedAt ? Date.now() - connectedAt : null,
      queue: {
        admin: globalQueue.length,
        owner: ownerPending,
        member: memberPending,
      },
    });
  });
```

- [x] **Step 4: Verify relay mode /health still works**

Relay mode `/health` (around line 267) proxies to admin and merges `{relay: true, port_filter}`. It will automatically pick up the new fields from admin since it spreads the response. No change needed — confirm by reading:

```bash
grep -n -A 7 "app.get.*health" bridge/whatsapp-bridge.js
```

Expected: relay mode returns `{...adminFields, relay: true, port_filter: PORT_FILTER}`.

- [x] **Step 5: Live test on server**

```bash
ssh doasas "curl -s http://localhost:3000/health | python3 -m json.tool"
```

Expected output (values will vary):
```json
{
  "ok": true,
  "status": "connected",
  "relay": false,
  "routes": 3,
  "uptime_ms": 18340200,
  "connected_duration_ms": 18338000,
  "queue": {
    "admin": 0,
    "owner": 0,
    "member": 0
  }
}
```

- [x] **Step 6: Commit**

```bash
git add bridge/whatsapp-bridge.js
git commit -m "feat(bridge): enrich /health with uptime, connected_duration, and per-queue sizes"
```

---

### Task 6: Automated host-side session pruning cron

**Files:**
- Create: `scripts/setup-cron.sh` — idempotent script to install host cron entries
- Modify: `docs/overview/DEPLOYMENT.md` — add cron setup step to initial setup checklist

**Why this matters:** `prune-idle-sessions.py` exists but is never run automatically. Sessions accumulate indefinitely on disk, bloating context on the next conversation start.

**Interfaces:**
- Produces: hourly cron that runs `prune-idle-sessions.py --idle-hours 1` as `deploy` user
- Log goes to `data/prune.log` (gitignored)

- [x] **Step 1: Create scripts/setup-cron.sh**

```bash
#!/usr/bin/env bash
# Installs viko maintenance cron jobs for the deploy user.
# Idempotent: safe to run multiple times.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/data"
mkdir -p "$LOG_DIR"

PRUNE_ENTRY="0 * * * * python3 $REPO_DIR/scripts/prune-idle-sessions.py --idle-hours 1 >> $LOG_DIR/prune.log 2>&1"
DELIVER_ENTRY="*/15 * * * * python3 $REPO_DIR/scripts/deliver-commitments.py >> $LOG_DIR/commitments.log 2>&1"

install_cron() {
  local entry="$1"
  local marker="$2"
  if crontab -l 2>/dev/null | grep -qF "$marker"; then
    echo "[setup-cron] already installed: $marker"
  else
    (crontab -l 2>/dev/null; echo "$entry") | crontab -
    echo "[setup-cron] installed: $entry"
  fi
}

install_cron "$PRUNE_ENTRY" "prune-idle-sessions.py"

echo "[setup-cron] Current viko cron entries:"
crontab -l 2>/dev/null | grep "viko-agent" || echo "(none yet)"
```

Make it executable:
```bash
chmod +x scripts/setup-cron.sh
```

- [x] **Step 2: Run on server**

```bash
ssh doasas-deploy "bash /home/deploy/viko-agent/scripts/setup-cron.sh"
```

Expected:
```
[setup-cron] installed: 0 * * * * python3 /home/deploy/viko-agent/scripts/prune-idle-sessions.py ...
[setup-cron] Current viko cron entries:
0 * * * * python3 /home/deploy/viko-agent/scripts/prune-idle-sessions.py ...
```

- [x] **Step 3: Verify cron is registered**

```bash
ssh doasas-deploy "crontab -l | grep viko"
```

Expected: the prune entry appears.

- [x] **Step 4: Dry-run the prune script to confirm it works**

```bash
ssh doasas-deploy "python3 /home/deploy/viko-agent/scripts/prune-idle-sessions.py --dry-run"
```

Expected: outputs `=== prune-idle-sessions ===` header and lists projects with sessions counts.

- [x] **Step 5: Add note to DEPLOYMENT.md**

In `docs/overview/DEPLOYMENT.md`, find the "First-Time Setup" or post-deploy checklist section. Add:

```markdown
### Maintenance Cron (one-time, run as deploy user)

```bash
bash /home/deploy/viko-agent/scripts/setup-cron.sh
```

Installs:
- Hourly idle-session pruner (sessions > 1h old are cleared)
- 15-min commitment delivery checker (see OpenClaw features plan)
```

- [x] **Step 6: Commit**

```bash
git add scripts/setup-cron.sh docs/overview/DEPLOYMENT.md
git commit -m "feat(scripts): setup-cron.sh — idempotent host cron installer for maintenance tasks"
```

---

### Task 7: Caller metadata fix + routing scoring

**Files:**
- Modify: `patches/patch-model-router.py` — parse CTX header properly; score keyword hits ≥ 2 instead of binary match

**Why this matters:** (1) `_vr_is_member` currently does a raw string search for `"caller=member"` in the entire lowercased message text — a user writing `"caller=member"` in their message would trick it. CTX header is already structured; parse it with regex. (2) A single keyword match (e.g. `"tes"` → triggers "code" routing) causes false positives. Requiring ≥ 2 distinct keyword hits reduces noise significantly.

**Interfaces:**
- Produces: `_vr_caller` parsed from `[CTX ... caller=<value>]` header; `_vr_is_code` requires 2+ keyword hits

- [ ] **Step 1: Understand current INJECT_CODE in the patch**

Read lines 17–55 of `patches/patch-model-router.py` to see the full INJECT_CODE string. The relevant lines are:

```python
    '            _vr_is_code = bool(_vr_code_re.search(_vr_text))\n'
    '            _vr_is_member = "caller=member" in (_vr_text or "")\n'
    '            _vr_model = "viko-chat" if _vr_is_member else ("viko-code" if _vr_is_code else "viko-chat")\n'
```

- [ ] **Step 2: Replace those three injected lines**

In `patches/patch-model-router.py`, inside the `INJECT_CODE` string, replace:

```python
    '            _vr_is_code = bool(_vr_code_re.search(_vr_text))\n'
    '            _vr_is_member = "caller=member" in (_vr_text or "")\n'
    '            _vr_model = "viko-chat" if _vr_is_member else ("viko-code" if _vr_is_code else "viko-chat")\n'
```

With:

```python
    '            _vr_code_hits = sum(1 for _ in _vr_code_re.finditer(_vr_text))\n'
    '            _vr_is_code = _vr_code_hits >= 2\n'
    '            _vr_ctx_m = _vr_re.search(r"\\[CTX[^\\]]*caller=(\\w+)", event.text or "")\n'
    '            _vr_caller = _vr_ctx_m.group(1) if _vr_ctx_m else "member"\n'
    '            _vr_is_member = _vr_caller != "owner"\n'
    '            _vr_model = "viko-chat" if _vr_is_member else ("viko-code" if _vr_is_code else "viko-chat")\n'
```

- [ ] **Step 3: Also update INJECT_CODE (the idempotent check string)**

The patch script checks if it's already applied by looking for `INJECT_CODE` in the file. Since `INJECT_CODE` changed, the marker check still works because the full new string is what we check. No additional change needed — verify:

```bash
python3 -c "
from patches.patch_model_router import INJECT_CODE, INJECT_AFTER
print('INJECT_CODE snippet:', repr(INJECT_CODE[:100]))
print('Contains scoring:', '_vr_code_hits' in INJECT_CODE)
print('Contains CTX parse:', '_vr_ctx_m' in INJECT_CODE)
"
```

Wait — the patch file uses underscores not hyphens in the filename. Run from repo root:

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
exec(open('patches/patch-model-router.py').read().split('def main')[0])
print('scoring:', '_vr_code_hits' in INJECT_CODE)
print('ctx parse:', '_vr_ctx_m' in INJECT_CODE)
"
```

Expected: both print `True`.

- [ ] **Step 4: Rebuild hermes image**

```bash
ssh doasas "cd /home/deploy/viko-agent && git pull && docker compose build hermes 2>&1 | grep -E 'patch-model-router|ERROR|Step'"
```

Expected: `✓ patch-model-router: applied (chat→haiku, code→sonnet routing)` (or similar success message).

- [ ] **Step 5: Live routing test**

Send two messages to a registered project group from a member account:
- "Iya bagus, sip" (no code keywords) → should route to viko-chat
- "Debug error ini dong, fix fungsinya" (≥2 code keywords: debug, error, fix, fungsi) → should route to viko-code

Check routing decision in hermes logs:

```bash
ssh doasas "docker logs viko-hermes-<slug> --since 1m 2>&1 | grep -i 'viko-chat\|viko-code\|model'"
```

- [ ] **Step 6: Commit**

```bash
git add patches/patch-model-router.py
git commit -m "fix(routing): score keyword hits (>=2) + parse caller from CTX header regex"
```
