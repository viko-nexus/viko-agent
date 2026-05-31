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

# ─── Colored, readable logging ─────────────────────────────────────────
C_DIM=$'\e[2m'; C_CYAN=$'\e[36m'; C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'
C_BLUE=$'\e[34m'; C_RED=$'\e[31m'; C_BOLD=$'\e[1m'; C_RST=$'\e[0m'

# _logline <color> <icon> <message...>
_logline() {
  local color="$1" icon="$2"; shift 2
  print -r -- "${C_DIM}${C_CYAN}$(date '+%H:%M:%S')${C_DIM}${C_RST} ${color}${icon}${C_RST}  $*"
}
log()       { _logline "$C_DIM"    "·" "$*"; }   # general info (dim)
log_msg()   { _logline "$C_GREEN"  "✉" "$*"; }   # inbound WhatsApp message
log_route() { _logline "$C_YELLOW" "↳" "$*"; }   # routing to project
log_act()   { _logline "$C_BLUE"   "▸" "$*"; }   # trigger / send action
log_warn()  { _logline "$C_RED"    "⚠" "$*"; }   # busy / warning

# Dynamic JID ↔ project mapping — reads access.json + resolves config.md symlinks
load_jid_maps() {
  typeset -gA JID_TO_PROJECT
  typeset -gA PROJECT_TO_JID
  # Clear existing entries
  JID_TO_PROJECT=()
  PROJECT_TO_JID=()

  while IFS='|' read -r jid project; do
    [[ -z "$jid" || -z "$project" ]] && continue
    JID_TO_PROJECT[$jid]="$project"
    PROJECT_TO_JID[$project]="$jid"
  done < <(python3 - <<'PYEOF' 2>/dev/null
import json, os, pathlib

access_file = pathlib.Path.home() / '.whatsapp-channel/access.json'
groups_dir = pathlib.Path.home() / '.whatsapp-channel/groups'

try:
    access = json.loads(access_file.read_text())
except Exception:
    raise SystemExit(0)

for jid in access.get('groups', {}):
    config = groups_dir / jid / 'config.md'
    try:
        real = os.path.realpath(str(config))
        parts = pathlib.Path(real).parts
        if 'projects' in parts:
            idx = list(parts).index('projects')
            project = parts[idx + 1]
            print(f"{jid}|{project}")
    except Exception:
        pass
PYEOF
)
  # Only log when the mapping count changes (quiet on periodic no-op reloads)
  if (( ${#JID_TO_PROJECT} != _prev_map_count )); then
    log "loaded ${#JID_TO_PROJECT} JID→project mapping(s): ${(v)JID_TO_PROJECT}"
    _prev_map_count=${#JID_TO_PROJECT}
  fi
}
typeset -gi _prev_map_count=-1

load_jid_maps

viko_busy() {
  pane=$($TMUX capture-pane -t "$SESSION:0" -p 2>/dev/null)
  echo "$pane" | grep -qE 'esc to interrupt|Lollygag|Enchanting|Gallivanting|Zesting|Working|Swirling|Brewing|Cogitat|Calling|thinking'
}

send_to_viko() {
  local msg="$1"
  # Clear any existing input, then type message and submit with C-m
  $TMUX send-keys -t "$SESSION:0" C-c 2>/dev/null
  sleep 0.3
  $TMUX send-keys -t "$SESSION:0" "$msg" 2>/dev/null
  sleep 0.5
  $TMUX send-keys -t "$SESSION:0" C-m 2>/dev/null
  log_act "sent to Viko"
}

log "watcher started — polling every ${POLL}s"
log "projects: ${(k)PROJECT_TO_JID}"

seen_msgs_file="/tmp/viko-watcher-seen.txt"
touch "$seen_msgs_file"

last_trigger=0
poll_count=0

declare -A outbox_line_counts
# Initialize counts to current file sizes so we only process NEW entries
for _p in "${(@k)PROJECT_TO_JID}"; do
  _ob="$VIKO_DIR/$_p/outbox.jsonl"
  if [[ -f "$_ob" ]]; then
    outbox_line_counts[outbox_$_p]=$(wc -l < "$_ob" 2>/dev/null | tr -d ' ')
  fi
done

while true; do
  sleep "$POLL"

  (( poll_count++ ))
  if (( poll_count % 10 == 0 )); then
    load_jid_maps
  fi

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
    # Collapse newlines/tabs/runs of spaces into single spaces so the full
    # message shows on one readable log line, untruncated.
    text = " ".join(d.get("text","").split())
    results.append(json.dumps({
        "id": msg_id,
        "chat_id": d.get("chat_id",""),
        "group": d.get("group_name","?"),
        "text": text
    }))

print("\n".join(results))
PYEOF
    )

    if [[ -n "$new_msgs" ]]; then
      # Collect pending message info — do NOT mark seen yet (wait until triggered)
      pending_ids=()
      while IFS= read -r msg_json; do
        [[ -z "$msg_json" ]] && continue
        grp=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(d['group'])" "$msg_json" 2>/dev/null)
        txt=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(d['text'])" "$msg_json" 2>/dev/null)
        chat_id=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(d['chat_id'])" "$msg_json" 2>/dev/null)
        msg_id=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(d['id'])" "$msg_json" 2>/dev/null)
        log_msg "${C_BOLD}${grp}${C_RST}${C_GREEN}: ${txt}${C_RST}"
        pending_ids+=("$msg_id")

        # Resume project session for this group
        project="${JID_TO_PROJECT[$chat_id]}"
        if [[ -n "$project" ]]; then
          log_route "project ${C_BOLD}${project}${C_RST}"
          "$WORKDIR/scripts/session-manager.sh" resume "$project" >/dev/null 2>&1 &
        fi
      done <<< "$new_msgs"

      # Only mark seen + trigger if Viko is idle — otherwise retry next poll
      now=$(date +%s)
      if (( now - last_trigger >= COOLDOWN )) && ! viko_busy; then
        # Mark all pending messages as seen now that we're triggering
        for mid in "${pending_ids[@]}"; do
          echo "$mid" >> "$seen_msgs_file"
        done
        last_trigger=$now
        log_act "triggering Viko"
        send_to_viko "Check and reply to unreplied messages from configured WhatsApp groups."
      elif viko_busy; then
        log_warn "Viko busy — ${#pending_ids[@]} msg(s) pending, retry next poll"
      fi
    fi
  fi

  # ── 2. Check outbox files from project agents ────────────────────────────
  for project in "${(@k)PROJECT_TO_JID}"; do
    outbox="$VIKO_DIR/$project/outbox.jsonl"
    [[ ! -f "$outbox" ]] && continue

    okey="outbox_$project"
    known=${outbox_line_counts[$okey]:-0}
    total=$(wc -l < "$outbox" 2>/dev/null | tr -d ' ')
    [[ -z "$total" ]] && total=0

    (( total <= known )) && continue

    start_line=$(( known + 1 ))
    outbox_line_counts[$okey]=$total

    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      msg_type=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(d.get('type','progress'))" "$line" 2>/dev/null)
      # Full message text, whitespace collapsed to single line for readability
      msg_text=$(python3 -c "import sys,json;d=json.loads(sys.argv[1]);print(' '.join(d.get('message','').split()))" "$line" 2>/dev/null)
      jid="${PROJECT_TO_JID[$project]}"
      log_msg "${C_BOLD}${project}${C_RST}${C_GREEN} [${msg_type}]: ${msg_text}${C_RST}"
      if [[ -n "$jid" && -n "$msg_text" ]]; then
        log_act "forwarding ${project} ${msg_type} → WhatsApp"
        send_to_viko "Kirim pesan ini ke group WhatsApp $jid: \"$msg_text\" (${msg_type} dari $project agent)"
      fi
    done < <(tail -n +"$start_line" "$outbox")
  done

done
