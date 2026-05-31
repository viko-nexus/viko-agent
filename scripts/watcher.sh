#!/bin/zsh
# watcher.sh — Two responsibilities:
# 1. Poll messages.jsonl for unreplied group messages → trigger Viko orchestrator
# 2. Poll ~/.viko/<project>/outbox.jsonl → forward agent messages to WA via Viko

MESSAGES="$HOME/.whatsapp-channel/messages.jsonl"
VIKO_DIR="$HOME/.viko"
SESSION="viko-agent"
TMUX="/opt/homebrew/bin/tmux"
WORKDIR="/Users/eksa/Projects/viko-agent"
POLL=3
COOLDOWN=10

# Group JID → project name mapping
declare -A JID_TO_PROJECT
JID_TO_PROJECT["120363409428298054@g.us"]="mankop"
JID_TO_PROJECT["120363424541097083@g.us"]="luxso"
JID_TO_PROJECT["120363421917950995@g.us"]="forecastinn"

# Group JID for each project (reverse map)
declare -A PROJECT_TO_JID
PROJECT_TO_JID["mankop"]="120363409428298054@g.us"
PROJECT_TO_JID["luxso"]="120363424541097083@g.us"
PROJECT_TO_JID["forecastinn"]="120363421917950995@g.us"

log() { echo "[watcher] $(date '+%H:%M:%S') $*"; }

viko_busy() {
  pane=$($TMUX capture-pane -t "$SESSION:0" -p 2>/dev/null)
  echo "$pane" | grep -qE 'esc to interrupt|Lollygag|Enchanting|Gallivanting|Zesting|Working|Swirling|Brewing|Cogitat|Calling|thinking'
}

send_to_viko() {
  local msg="$1"
  if ! $TMUX has-session -t "$SESSION" 2>/dev/null; then
    log "WARNING: viko-agent session not found"
    return
  fi
  $TMUX send-keys -t "$SESSION:0" "" Enter 2>/dev/null
  sleep 0.3
  $TMUX send-keys -t "$SESSION:0" "$msg" Enter 2>/dev/null
}

log "started — polling every ${POLL}s"
log "watching: $MESSAGES"
log "outbox dirs: $VIKO_DIR/{mankop,luxso,forecastinn}/outbox.jsonl"

seen_msgs_file="/tmp/viko-watcher-seen.txt"
seen_outbox_file="/tmp/viko-outbox-seen.txt"
touch "$seen_msgs_file" "$seen_outbox_file"

last_trigger=0

while true; do
  sleep "$POLL"

  # ── 1. Check for new unreplied group messages ────────────────────────────
  if [[ -f "$MESSAGES" ]]; then
    new_msgs=$(VIKO_MSGS="$MESSAGES" python3 - <<'PYEOF' 2>/dev/null
import json, os

msgs_file = os.environ["VIKO_MSGS"]
seen = set(open("/tmp/viko-watcher-seen.txt").read().splitlines())
results = []

for line in open(msgs_file):
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
        "chat_id": d.get("chat_id",""),
        "group": d.get("group_name","?"),
        "text": d.get("text","")[:120]
    }))

print("\n".join(results))
PYEOF
    )

    if [[ -n "$new_msgs" ]]; then
      echo "$new_msgs" | while read -r msg_json; do
        [[ -z "$msg_json" ]] && continue
        grp=$(echo "$msg_json" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['group'])" 2>/dev/null)
        txt=$(echo "$msg_json" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['text'])" 2>/dev/null)
        chat_id=$(echo "$msg_json" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['chat_id'])" 2>/dev/null)
        msg_id=$(echo "$msg_json" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['id'])" 2>/dev/null)
        log "new msg → [$grp] $txt"
        echo "$msg_id" >> "$seen_msgs_file"

        # Identify project for this group
        project="${JID_TO_PROJECT[$chat_id]}"
        if [[ -n "$project" ]]; then
          log "routing to project: $project"
          # Ensure project session is running
          "$WORKDIR/scripts/session-manager.sh" resume "$project" &
        fi
      done

      # Trigger Viko orchestrator for WA reply
      now=$(date +%s)
      if (( now - last_trigger >= COOLDOWN )) && ! viko_busy; then
        last_trigger=$now
        log "triggering Viko orchestrator..."
        send_to_viko "Check and reply to unreplied messages from configured WhatsApp groups."
        log "triggered"
      elif viko_busy; then
        log "Viko busy, will retry"
      fi
    fi
  fi

  # ── 2. Check outbox files from project agents ────────────────────────────
  for project in mankop luxso forecastinn; do
    outbox="$VIKO_DIR/$project/outbox.jsonl"
    [[ ! -f "$outbox" ]] && continue

    seen=$(cat "$seen_outbox_file")

    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      line_hash=$(echo "$line" | md5)
      if echo "$seen" | grep -qF "$line_hash"; then continue; fi
      echo "$line_hash" >> "$seen_outbox_file"

      msg_type=$(echo "$line" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d.get('type','progress'))" 2>/dev/null)
      msg_text=$(echo "$line" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d.get('message',''))" 2>/dev/null)
      jid="${PROJECT_TO_JID[$project]}"

      log "outbox [$project/$msg_type]: $msg_text"

      if [[ -n "$jid" && -n "$msg_text" ]]; then
        # Tell Viko to send this message to the group
        send_to_viko "Kirim pesan ini ke group WhatsApp $jid: \"$msg_text\" (ini adalah ${msg_type} update dari project agent $project)"
      fi
    done < "$outbox"
  done

done
