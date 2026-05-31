#!/bin/zsh
# watcher.sh — Forward project agent outbox messages to WhatsApp via Viko.
# Incoming messages are handled natively by the WhatsApp plugin channel
# (notifications/claude/channel push) — no polling needed for that path.

VIKO_DIR="$HOME/.viko"
SESSION="viko-agent"
TMUX="/opt/homebrew/bin/tmux"
WORKDIR="/Users/eksa/Projects/viko-agent"
POLL=3

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

# ─── Singleton lock ────────────────────────────────────────────────────
# Prevent two watchers running simultaneously (double outbox processing).
# Refuse to start if another watcher is already alive. Path-agnostic
# (catches orphans launched via any path), uses kill -0 + command check to
# tolerate reused PIDs after reboot.
WATCHER_LOCK="/tmp/viko-watcher.lock"
if [[ -f "$WATCHER_LOCK" ]]; then
  old_pid=$(cat "$WATCHER_LOCK" 2>/dev/null)
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null \
     && ps -p "$old_pid" -o command= 2>/dev/null | grep -q "watcher.sh"; then
    log_warn "another watcher (pid $old_pid) already running — exiting"
    exit 0
  fi
fi
echo $$ > "$WATCHER_LOCK"
# Release lock on exit. On a signal we must ALSO exit — a bare signal trap that
# doesn't exit cancels the default termination, making the watcher unkillable
# via SIGTERM (tmux kill-session / pkill). tmux kill-session sends HUP.
_watcher_cleanup() { rm -f "$WATCHER_LOCK" 2>/dev/null; }
trap _watcher_cleanup EXIT
trap '_watcher_cleanup; exit 0' INT TERM HUP

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

log "watcher started — outbox polling every ${POLL}s"
log "projects: ${(k)PROJECT_TO_JID}"

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
  if (( poll_count % 20 == 0 )); then
    load_jid_maps
  fi

  # ── Forward outbox messages from project agents to WhatsApp ─────────────
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
