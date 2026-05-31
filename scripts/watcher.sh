#!/bin/zsh
# watcher.sh — Monitor messages.jsonl for new unreplied group messages,
# trigger Viko tmux session to process them.

MESSAGES="$HOME/.whatsapp-channel/messages.jsonl"
SESSION="viko-agent"
TMUX="/opt/homebrew/bin/tmux"
COOLDOWN=5

log() { echo "[watcher] $(date '+%H:%M:%S') $*"; }

log "started — watching $MESSAGES"
log "tmux session: $SESSION"

last_trigger=0

tail -n 0 -F "$MESSAGES" 2>/dev/null | while read -r line; do
  [[ -z "$line" ]] && continue

  # Fast filter: skip non-group messages before spawning python3
  [[ "$line" != *"@g.us"* ]] && continue
  [[ "$line" != *'"replied": false'* ]] && continue

  chat_id=$(echo "$line" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d.get('chat_id',''))" 2>/dev/null)
  text=$(echo "$line" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d.get('text','')[:60])" 2>/dev/null)
  group=$(echo "$line" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d.get('group_name','?'))" 2>/dev/null)

  [[ "$chat_id" != *"@g.us" ]] && continue

  log "new group message — $group: $text"

  # Cooldown
  now=$(date +%s)
  if (( now - last_trigger < COOLDOWN )); then
    log "cooldown active, skipping trigger"
    continue
  fi
  last_trigger=$now

  # Check tmux session
  if ! $TMUX has-session -t "$SESSION" 2>/dev/null; then
    log "WARNING: tmux session '$SESSION' not found, skipping"
    continue
  fi

  # Check if Claude is already processing
  current=$($TMUX capture-pane -t "$SESSION:0" -p | tail -5)
  if echo "$current" | grep -qE 'esc to interrupt|Lollygag|Enchanting|Gallivanting|Zesting|Calling|thinking'; then
    log "Viko already processing, skipping trigger"
    continue
  fi

  log "triggering Viko..."
  $TMUX send-keys -t "$SESSION:0" "" Enter 2>/dev/null
  sleep 0.5
  $TMUX send-keys -t "$SESSION:0" "Check and reply to unreplied messages from configured WhatsApp groups." Enter 2>/dev/null
  log "triggered"
done
