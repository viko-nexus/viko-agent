#!/bin/zsh
# watcher.sh — Poll messages.jsonl for unreplied group messages that
# mention Viko, then trigger the Viko tmux session.

MESSAGES="$HOME/.whatsapp-channel/messages.jsonl"
SESSION="viko-agent"
TMUX="/opt/homebrew/bin/tmux"
POLL=3          # seconds between polls
COOLDOWN=10     # seconds between triggers

log() { echo "[watcher] $(date '+%H:%M:%S') $*"; }

log "started — polling every ${POLL}s"
log "messages: $MESSAGES"

last_trigger=0
# Track message IDs we've already triggered on to avoid re-triggering
seen_ids_file="/tmp/viko-watcher-seen.txt"
touch "$seen_ids_file"

while true; do
  sleep "$POLL"

  [[ ! -f "$MESSAGES" ]] && continue

  # Find unreplied group messages not yet seen
  new_msgs=$(python3 - <<'PYEOF' 2>/dev/null
import json, sys

seen = set(open("/tmp/viko-watcher-seen.txt").read().splitlines())
results = []

for line in open(sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"):
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except:
        continue
    if not d.get("chat_id","").endswith("@g.us"):
        continue
    if d.get("replied", True):
        continue
    msg_id = d.get("id","")
    if msg_id in seen:
        continue
    results.append(json.dumps({
        "id": msg_id,
        "group": d.get("group_name","?"),
        "text": d.get("text","")[:80]
    }))

print("\n".join(results))
PYEOF
  "$MESSAGES")

  [[ -z "$new_msgs" ]] && continue

  # Log each new message found
  echo "$new_msgs" | while read -r msg_json; do
    [[ -z "$msg_json" ]] && continue
    grp=$(echo "$msg_json" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['group'])" 2>/dev/null)
    txt=$(echo "$msg_json" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['text'])" 2>/dev/null)
    msg_id=$(echo "$msg_json" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['id'])" 2>/dev/null)
    log "new msg → [$grp] $txt"
    echo "$msg_id" >> "$seen_ids_file"
  done

  # Cooldown check
  now=$(date +%s)
  (( now - last_trigger < COOLDOWN )) && { log "cooldown, skip trigger"; continue; }
  last_trigger=$now

  # Check if tmux session exists
  if ! $TMUX has-session -t "$SESSION" 2>/dev/null; then
    log "WARNING: session '$SESSION' not found"
    continue
  fi

  # Check if Claude is already busy
  pane=$($TMUX capture-pane -t "$SESSION:0" -p | tail -5)
  if echo "$pane" | grep -qE 'esc to interrupt|Lollygag|Enchanting|Gallivanting|Zesting|Working|Calling|thinking'; then
    log "Viko busy, will retry next poll"
    continue
  fi

  log "triggering Viko..."
  $TMUX send-keys -t "$SESSION:0" "" Enter 2>/dev/null
  sleep 0.3
  $TMUX send-keys -t "$SESSION:0" "Check and reply to unreplied messages from configured WhatsApp groups." Enter 2>/dev/null
  log "triggered"
done
