#!/bin/zsh
# watchdog.sh — Foreground daemon run by launchd with KeepAlive.
# Starts the viko-agent tmux session and monitors it, restarting with
# a cooldown to prevent rapid restarts that damage the Baileys WA session.

TMUX="/opt/homebrew/bin/tmux"
SESSION="viko-agent"
WORKDIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGFILE="$WORKDIR/logs/watchdog.log"
MIN_RESTART_INTERVAL=90  # seconds — protect Baileys from rapid reconnects
POLL=15                  # seconds between health checks

mkdir -p "$WORKDIR/logs"

# Just echo — launchd redirects stdout to LOGFILE (StandardOutPath). Using
# `tee -a` here too would write every line twice (tee + launchd capture).
log() { echo "[watchdog] $(date '+%Y-%m-%d %H:%M:%S') $*"; }

trap 'log "watchdog received SIGTERM, exiting"; exit 0' SIGTERM SIGINT

last_start=0

start_viko() {
  local now=$(date +%s)
  local since=$(( now - last_start ))

  if [[ $last_start -gt 0 ]] && (( since < MIN_RESTART_INTERVAL )); then
    local wait=$(( MIN_RESTART_INTERVAL - since ))
    log "restart too soon (${since}s ago) — waiting ${wait}s to protect Baileys..."
    sleep $wait
  fi

  last_start=$now
  log "starting viko-agent..."
  if ! "$WORKDIR/scripts/start.sh" >> "$LOGFILE" 2>&1; then
    log "WARNING: start.sh exited with code $?"
  fi
  log "start.sh returned"
}

[[ -x "$TMUX" ]] || { echo "ERROR: tmux not found at $TMUX"; exit 1; }
[[ -d "$WORKDIR" ]] || { echo "ERROR: workdir not found: $WORKDIR"; exit 1; }
[[ -x "$WORKDIR/scripts/start.sh" ]] || { echo "ERROR: start.sh not found"; exit 1; }

log "watchdog started (min_restart=${MIN_RESTART_INTERVAL}s, poll=${POLL}s)"
start_viko

while true; do
  sleep $POLL
  if ! $TMUX has-session -t "$SESSION" 2>/dev/null; then
    log "session '$SESSION' not found — restarting"
    start_viko
  elif ! pgrep -f "$WORKDIR/scripts/watcher.sh" >/dev/null 2>&1; then
    # Session alive but watcher (message poller) died — WhatsApp auto-response
    # silently stops. Relaunch just the watcher window; don't touch the Claude
    # session / Baileys connection in window 0.
    log "watcher not running — relaunching watcher window"
    $TMUX new-window -t "$SESSION" -c "$WORKDIR" "zsh $WORKDIR/scripts/watcher.sh"
  fi
done
