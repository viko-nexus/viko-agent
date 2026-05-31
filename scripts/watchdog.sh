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
