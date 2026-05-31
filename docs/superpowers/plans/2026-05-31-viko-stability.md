# Viko Stability & Auto-Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Viko reliably auto-start on laptop restart, self-heal if crashed, and eliminate all known stability bugs found during May 31 debugging session.

**Architecture:** Add a foreground `watchdog.sh` daemon that launchd monitors with `KeepAlive: true`. Watchdog runs `start.sh` and monitors the tmux session, restarting with cooldown to protect Baileys. Server.ts gets a periodic health-check that alerts owner if connection goes zombie. Watcher.sh gets dynamic JID mapping and efficient outbox polling.

**Tech Stack:** zsh, tmux, Python 3, launchd (macOS), Baileys (WhatsApp), Claude Code CLI

---

## Files

| File | Action | Purpose |
|------|--------|---------|
| `scripts/watchdog.sh` | CREATE | Foreground daemon — monitors tmux session, restarts with cooldown |
| `~/Library/LaunchAgents/com.viko.agent.plist` | MODIFY | Point to watchdog.sh, add KeepAlive + ThrottleInterval |
| `scripts/start.sh` | MODIFY | Remove redundant cleanup (watchdog handles it) |
| `scripts/watcher.sh` | MODIFY | Dynamic JID mapping from access.json + efficient outbox polling |
| `scripts/session-manager.sh` | MODIFY | Fix inject: use C-m not Enter |
| `src/server.ts` | MODIFY | Baileys health check — alert owner if no events for 5+ min |
| `~/.tmux.conf` | CREATE | focus-events on (eliminates warning) |

---

## Task 1: watchdog.sh — Foreground Launchd Daemon

**Files:**
- Create: `scripts/watchdog.sh`

- [ ] **Step 1: Create watchdog.sh**

```zsh
#!/bin/zsh
# watchdog.sh — Foreground daemon run by launchd with KeepAlive.
# Starts the viko-agent tmux session and monitors it, restarting with
# a cooldown to prevent rapid restarts that damage the Baileys WA session.

TMUX="/opt/homebrew/bin/tmux"
SESSION="viko-agent"
WORKDIR="/Users/eksa/Projects/viko-agent"
LOGFILE="$WORKDIR/logs/watchdog.log"
MIN_RESTART_INTERVAL=90  # seconds — protect Baileys from rapid reconnects
POLL=15                  # seconds between health checks

mkdir -p "$WORKDIR/logs"

log() { echo "[watchdog] $(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOGFILE"; }

last_start=0

start_viko() {
  local now=$(date +%s)
  local since=$(( now - last_start ))

  if [[ $last_start -gt 0 ]] && (( since < MIN_RESTART_INTERVAL )); then
    local wait=$(( MIN_RESTART_INTERVAL - since ))
    log "restart too soon (${since}s ago) — waiting ${wait}s to protect Baileys..."
    sleep $wait
  fi

  last_start=$(date +%s)
  log "starting viko-agent..."
  "$WORKDIR/scripts/start.sh" >> "$LOGFILE" 2>&1
  log "start.sh returned"
}

log "watchdog started (min_restart=${MIN_RESTART_INTERVAL}s, poll=${POLL}s)"
start_viko

while true; do
  sleep $POLL
  if ! $TMUX has-session -t "$SESSION" 2>/dev/null; then
    log "session '$SESSION' not found — restarting"
    start_viko
  fi
done
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/watchdog.sh
```

- [ ] **Step 3: Test manually — run watchdog and kill tmux to verify restart**

```bash
# Run in one terminal
./scripts/watchdog.sh &
WATCHDOG_PID=$!
sleep 5

# Kill the session to trigger restart
tmux kill-session -t viko-agent 2>/dev/null
sleep 20  # watchdog polls every 15s

# Verify session was restarted
tmux ls | grep viko-agent
# Expected: viko-agent: 2 windows (created ...)

kill $WATCHDOG_PID
```

- [ ] **Step 4: Commit**

```bash
git add scripts/watchdog.sh
git commit -m "feat: add watchdog.sh — foreground daemon for launchd KeepAlive"
```

---

## Task 2: Update launchd Plist to Use Watchdog

**Files:**
- Modify: `~/Library/LaunchAgents/com.viko.agent.plist`

- [ ] **Step 1: Unload current plist**

```bash
launchctl unload ~/Library/LaunchAgents/com.viko.agent.plist
```

- [ ] **Step 2: Replace plist content**

Write `/Users/eksa/Library/LaunchAgents/com.viko.agent.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.viko.agent</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/Users/eksa/Projects/viko-agent/scripts/watchdog.sh</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/eksa/.local/bin:/Users/eksa/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/eksa</string>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/eksa/Projects/viko-agent/logs/watchdog.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/eksa/Projects/viko-agent/logs/watchdog.log</string>
</dict>
</plist>
```

- [ ] **Step 3: Load and verify**

```bash
launchctl load ~/Library/LaunchAgents/com.viko.agent.plist
sleep 3
launchctl list | grep viko
# Expected: positive PID (not -) for com.viko.agent — means it's running
tmux ls | grep viko-agent
# Expected: viko-agent session exists
```

- [ ] **Step 4: Commit**

```bash
git add -f ~/Library/LaunchAgents/com.viko.agent.plist 2>/dev/null || true
git commit -m "feat: launchd — use watchdog.sh with KeepAlive + ThrottleInterval 30s"
```

---

## Task 3: Baileys Health Check in server.ts

**Files:**
- Modify: `src/server.ts` (add after the composingTimers block, around line 800)

The health check tracks the timestamp of the last received message event. If no event arrives for 5 minutes AND we're supposed to be connected, it pings WhatsApp by fetching profile metadata. If that fails, it alerts the owner via DM and triggers a reconnect.

- [ ] **Step 1: Add lastEventAt tracker and health check function**

Find the block after `const composingTimers = new Map<string, ReturnType<typeof setInterval>>()` and add:

```typescript
// ─── Baileys health check ──────────────────────────────────────────────

let lastEventAt = Date.now()

function recordEvent(): void {
  lastEventAt = Date.now()
}

async function runHealthCheck(): Promise<void> {
  if (!sock || !ownJid) return // not connected yet
  const silentMs = Date.now() - lastEventAt
  const ALERT_AFTER_MS = 5 * 60 * 1000 // 5 minutes

  if (silentMs < ALERT_AFTER_MS) return

  process.stderr.write(`${LOG_PREFIX}: health check — no events for ${Math.round(silentMs / 1000)}s, pinging...\n`)

  try {
    await sock.fetchStatus(ownJid)
    // Ping succeeded — connection is alive but quiet
    lastEventAt = Date.now()
    process.stderr.write(`${LOG_PREFIX}: health check — ping OK\n`)
  } catch {
    process.stderr.write(`${LOG_PREFIX}: health check — ping FAILED, alerting owner and reconnecting\n`)

    // Alert owner via DM
    const access = loadAccess()
    const owner = access.allowFrom[0]
    if (sock && owner) {
      void sock.sendMessage(owner, {
        text: '⚠️ Viko WhatsApp connection appears lost. Auto-reconnecting...',
      }).catch(() => {})
    }

    // Trigger reconnect
    try { sock.end(undefined as any) } catch {}
  }
}

// Run health check every 2 minutes
setInterval(runHealthCheck, 2 * 60 * 1000).unref()
```

- [ ] **Step 2: Call recordEvent() in messages.upsert handler**

Find the `sock.ev.on('messages.upsert', ...)` handler (around line 1840) and add `recordEvent()` at the top:

```typescript
sock.ev.on('messages.upsert', async (ev: { messages: WAMessage[]; type: string }) => {
  if (ev.type !== 'notify') return
  recordEvent() // ← ADD THIS LINE
  for (const msg of ev.messages) {
```

- [ ] **Step 3: Deploy and restart**

```bash
./scripts/deploy.sh && ./scripts/start.sh
sleep 5
tmux ls | grep viko-agent
# Expected: viko-agent session running
```

- [ ] **Step 4: Commit**

```bash
git add src/server.ts
git commit -m "feat: server.ts — Baileys health check, ping every 2min, alert+reconnect after 5min silent"
```

---

## Task 4: Dynamic JID Mapping in watcher.sh

**Files:**
- Modify: `scripts/watcher.sh` (replace hardcoded JID arrays)

The current hardcoded maps must be manually updated when groups change. Fix: read from `~/.whatsapp-channel/access.json` and resolve symlinks in `~/.whatsapp-channel/groups/` to discover project names.

- [ ] **Step 1: Replace hardcoded JID maps with dynamic loader**

Remove the `declare -A JID_TO_PROJECT` and `declare -A PROJECT_TO_JID` blocks at the top of watcher.sh. Replace with a python3-based dynamic loader that reads access.json and resolves symlinks:

```zsh
# Dynamic JID ↔ project mapping — reads access.json + resolves config.md symlinks
load_jid_maps() {
  local json
  json=$(python3 - <<'PYEOF' 2>/dev/null
import json, os, pathlib

access_file = pathlib.Path.home() / '.whatsapp-channel/access.json'
groups_dir = pathlib.Path.home() / '.whatsapp-channel/groups'

try:
    access = json.loads(access_file.read_text())
except:
    print("{}")
    exit(0)

result = {}
for jid in access.get('groups', {}):
    config = groups_dir / jid / 'config.md'
    try:
        real = os.path.realpath(str(config))
        parts = pathlib.Path(real).parts
        if 'projects' in parts:
            idx = list(parts).index('projects')
            project = parts[idx + 1]
            result[jid] = project
    except:
        pass

print(json.dumps(result))
PYEOF
  )
  # Build shell associative arrays from JSON
  declare -gA JID_TO_PROJECT
  declare -gA PROJECT_TO_JID
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local jid project
    jid=$(echo "$line" | python3 -c "import sys; print(sys.stdin.read().split('|')[0])" 2>/dev/null)
    project=$(echo "$line" | python3 -c "import sys; print(sys.stdin.read().split('|')[1])" 2>/dev/null)
    JID_TO_PROJECT["$jid"]="$project"
    PROJECT_TO_JID["$project"]="$jid"
  done < <(echo "$json" | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
for jid, proj in d.items():
    print(f'{jid}|{proj}')
" 2>/dev/null)
  log "loaded ${#JID_TO_PROJECT} JID→project mappings: ${(k)JID_TO_PROJECT}"
}

load_jid_maps
```

- [ ] **Step 2: Reload maps on each poll cycle (detect new groups)**

Add to the top of the `while true; do` loop body (before `sleep`):

```zsh
while true; do
  # Reload JID maps every 10 polls (~30s) to pick up new groups
  (( poll_count++ ))
  if (( poll_count % 10 == 0 )); then
    load_jid_maps
  fi
  sleep "$POLL"
  ...
```

Initialize `poll_count=0` before the while loop.

- [ ] **Step 3: Test — verify maps load correctly**

```bash
# Run watcher briefly and check output
timeout 5 zsh scripts/watcher.sh 2>&1 | grep "loaded"
# Expected: [watcher] HH:MM:SS loaded 3 JID→project mappings: 120363...
```

- [ ] **Step 4: Commit**

```bash
git add scripts/watcher.sh
git commit -m "fix: watcher — dynamic JID→project mapping from access.json symlinks"
```

---

## Task 5: Efficient Outbox Polling

**Files:**
- Modify: `scripts/watcher.sh` (section 2 — outbox polling)

Current: reads full outbox file + md5 per line every 3 seconds. Fix: track line count per project, only process new lines with `tail -n +N`.

- [ ] **Step 1: Replace outbox polling section**

Replace the `# ── 2. Check outbox files` section with:

```zsh
  # ── 2. Check outbox files from project agents ────────────────────────────
  for project in "${(k)PROJECT_TO_JID[@]}"; do
    outbox="$VIKO_DIR/$project/outbox.jsonl"
    [[ ! -f "$outbox" ]] && continue

    local key="outbox_$project"
    local known_lines="${outbox_line_counts[$key]:-0}"
    local total_lines
    total_lines=$(wc -l < "$outbox" 2>/dev/null || echo 0)
    total_lines=${total_lines// /}  # trim whitespace

    (( total_lines <= known_lines )) && continue

    # Process only new lines
    local start_line=$(( known_lines + 1 ))
    outbox_line_counts[$key]=$total_lines

    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      msg_type=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(d.get('type','progress'))" "$line" 2>/dev/null)
      msg_text=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(d.get('message',''))" "$line" 2>/dev/null)
      jid="${PROJECT_TO_JID[$project]}"
      log "outbox [$project/$msg_type]: $msg_text"
      if [[ -n "$jid" && -n "$msg_text" ]]; then
        send_to_viko "Kirim pesan ini ke group WhatsApp $jid: \"$msg_text\" (${msg_type} dari $project agent)"
      fi
    done < <(tail -n +"$start_line" "$outbox")
  done
```

Add before the main while loop: `declare -A outbox_line_counts`

Remove: `seen_outbox_file` variable, `touch "$seen_outbox_file"`, and all references.

- [ ] **Step 2: Test outbox detection**

```bash
# Create test outbox entry
mkdir -p ~/.viko/mankop
echo '{"type":"progress","project":"mankop","message":"Test message","ts":"2026-01-01T00:00:00Z"}' >> ~/.viko/mankop/outbox.jsonl

# Run watcher briefly
timeout 8 zsh scripts/watcher.sh 2>&1 | grep outbox
# Expected: [watcher] HH:MM:SS outbox [mankop/progress]: Test message
```

- [ ] **Step 3: Commit**

```bash
git add scripts/watcher.sh
git commit -m "fix: watcher — efficient outbox polling with line-count diff, no md5"
```

---

## Task 6: Fix session-manager.sh inject (C-m not Enter)

**Files:**
- Modify: `scripts/session-manager.sh:124-127`

- [ ] **Step 1: Fix inject send-keys**

```zsh
    log "injecting task into $sess"
    $TMUX send-keys -t "$sess:0" C-c 2>/dev/null
    sleep 0.3
    $TMUX send-keys -t "$sess:0" "$task" 2>/dev/null
    sleep 0.5
    $TMUX send-keys -t "$sess:0" C-m 2>/dev/null
```

- [ ] **Step 2: Test inject**

```bash
# Start a project session
./scripts/session-manager.sh resume mankop
sleep 8

# Inject a simple task
./scripts/session-manager.sh inject mankop "echo 'inject test'"
sleep 3

# Check session received the task
tmux capture-pane -t viko-mankop:0 -p | grep -i 'inject test'
# Expected: line with "inject test" visible in pane
```

- [ ] **Step 3: Commit**

```bash
git add scripts/session-manager.sh
git commit -m "fix: session-manager inject — use C-m for reliable Claude TUI submit"
```

---

## Task 7: tmux.conf — focus-events on

**Files:**
- Create: `~/.tmux.conf`

- [ ] **Step 1: Create ~/.tmux.conf**

```bash
cat >> ~/.tmux.conf << 'EOF'
# Viko agent requirements
set -g focus-events on
set -g escape-time 10
EOF
```

- [ ] **Step 2: Reload tmux config in running server**

```bash
tmux source-file ~/.tmux.conf 2>/dev/null && echo "reloaded"
# Expected: reloaded
```

- [ ] **Step 3: Verify warning is gone after restart**

```bash
./scripts/start.sh && sleep 5
tmux capture-pane -t viko-agent:0 -p | grep -i 'focus-events'
# Expected: no output (warning gone)
```

- [ ] **Step 4: Commit**

```bash
git commit -m "fix: tmux.conf — focus-events on, escape-time 10"
```

---

## Task 8: End-to-End Validation

- [ ] **Step 1: Full restart test**

```bash
# Kill everything
tmux kill-server 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.viko.agent.plist
sleep 3

# Reload launchd — simulates login
launchctl load ~/Library/LaunchAgents/com.viko.agent.plist
sleep 15

# Verify watchdog + viko-agent running
launchctl list | grep viko       # should show PID (not -)
tmux ls                           # should show viko-agent: 2 windows
ps aux | grep watchdog | grep -v grep  # watchdog process alive
cat logs/watchdog.log | tail -5  # shows startup log
```

- [ ] **Step 2: Crash recovery test**

```bash
# Kill tmux session (simulate crash)
tmux kill-session -t viko-agent
sleep 20  # watchdog polls every 15s

# Verify auto-restart
tmux ls | grep viko-agent   # session should be back
cat logs/watchdog.log | tail -5  # shows "session not found — restarting"
```

- [ ] **Step 3: Rapid restart protection test**

```bash
# Kill session twice quickly
tmux kill-session -t viko-agent 2>/dev/null
sleep 5
tmux kill-session -t viko-agent 2>/dev/null
sleep 3

# Watchdog should log "restart too soon — waiting Xs"
cat logs/watchdog.log | grep "restart too soon"
# Expected: line with "restart too soon"
```

- [ ] **Step 4: WhatsApp message end-to-end test**

Send "viko halo" to any configured group. Within 10 seconds:
- ⚡ reaction appears on message
- Within 30 seconds: text reply from Viko

- [ ] **Step 5: Final commit and summary**

```bash
git log --oneline -10
# Review all commits from this plan
```

---

## Summary of Changes

| Issue | Fix | File |
|-------|-----|------|
| launchd no KeepAlive | watchdog.sh foreground daemon | `scripts/watchdog.sh` + plist |
| Rapid restart damages Baileys | 90s cooldown in watchdog | `scripts/watchdog.sh` |
| Baileys zombie connection | Health check every 2min, alert after 5min | `src/server.ts` |
| JID mapping hardcoded | Dynamic from access.json symlinks | `scripts/watcher.sh` |
| Outbox polling inefficient | Line-count diff, process only new lines | `scripts/watcher.sh` |
| session-manager inject unreliable | C-c then C-m | `scripts/session-manager.sh` |
| tmux focus-events warning | ~/.tmux.conf | `~/.tmux.conf` |
