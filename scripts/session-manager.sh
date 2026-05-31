#!/bin/zsh
# session-manager.sh — Manage per-project Claude Code agent sessions
#
# Usage:
#   session-manager.sh spawn  <project>          # start fresh session
#   session-manager.sh resume <project>          # resume last session (or spawn)
#   session-manager.sh inject <project> <task>   # inject task into running session
#   session-manager.sh status <project>          # check if session is alive
#   session-manager.sh hibernate <project>       # kill session, save session ID

CLAUDE="/Users/eksa/.local/bin/claude"
TMUX="/opt/homebrew/bin/tmux"
VIKO_DIR="$HOME/.viko"

# Project → directory mapping
project_dir() {
  case "$1" in
    mankop)      echo "/Users/eksa/Projects/mankop/mankop-apps" ;;
    luxso)       echo "/Users/eksa/Projects/forecastinn/clients/Luxso-executive-dashboard" ;;
    forecastinn) echo "/Users/eksa/Projects/forecastinn/forecast-inn" ;;
    *)           echo "" ;;
  esac
}

session_name() { echo "viko-$1"; }

session_id_file() { echo "$VIKO_DIR/$1/session.txt"; }

session_log() { echo "$VIKO_DIR/$1/session-log.md"; }

log() { echo "[session-manager] $(date '+%H:%M:%S') $*"; }

cmd="$1"
project="$2"
task="$3"

if [[ -z "$project" ]]; then
  echo "Usage: session-manager.sh <spawn|resume|inject|status|hibernate> <project> [task]"
  exit 1
fi

proj_dir=$(project_dir "$project")
if [[ -z "$proj_dir" ]]; then
  echo "ERROR: unknown project '$project'" >&2
  exit 1
fi

sess=$(session_name "$project")

case "$cmd" in
  status)
    if $TMUX has-session -t "$sess" 2>/dev/null; then
      echo "running"
    else
      echo "stopped"
    fi
    ;;

  spawn)
    log "spawning fresh session for $project in $proj_dir"
    $TMUX kill-session -t "$sess" 2>/dev/null
    mkdir -p "$VIKO_DIR/$project"

    # Build startup prompt with session-log context
    log_file=$(session_log "$project")
    context_prompt=""
    if [[ -f "$log_file" && -s "$log_file" ]]; then
      context_prompt="Read $log_file for recent session context before starting. "
    fi

    $TMUX new-session -d -s "$sess" -c "$proj_dir" \
      "$CLAUDE --dangerously-skip-permissions"

    log "session '$sess' started"
    ;;

  resume)
    if $TMUX has-session -t "$sess" 2>/dev/null; then
      log "session '$sess' already running"
      echo "running"
      exit 0
    fi

    id_file=$(session_id_file "$project")
    log_file=$(session_log "$project")
    mkdir -p "$VIKO_DIR/$project"

    if [[ -f "$id_file" ]]; then
      session_id=$(cat "$id_file")
      log "resuming session $session_id for $project"
      $TMUX new-session -d -s "$sess" -c "$proj_dir" \
        "$CLAUDE --dangerously-skip-permissions --resume $session_id"
    else
      log "no previous session, spawning fresh"
      $TMUX new-session -d -s "$sess" -c "$proj_dir" \
        "$CLAUDE --dangerously-skip-permissions"
    fi

    # Wait for Claude to be ready
    sleep 5
    log "session '$sess' ready"
    ;;

  inject)
    if ! $TMUX has-session -t "$sess" 2>/dev/null; then
      log "session not running, resuming first..."
      "$0" resume "$project"
      sleep 3
    fi

    if [[ -z "$task" ]]; then
      echo "ERROR: inject requires a task" >&2
      exit 1
    fi

    # Check if already busy
    pane=$($TMUX capture-pane -t "$sess:0" -p)
    if echo "$pane" | grep -qE 'esc to interrupt|Lollygag|Enchanting|Gallivanting|Zesting|Working|Swirling|Brewing|Calling|thinking'; then
      log "session busy, queuing task..."
      echo "$task" >> "$VIKO_DIR/$project/task-queue.txt"
      exit 0
    fi

    log "injecting task into $sess"
    # Clear input then type task and submit with C-m (Enter is unreliable in
    # the Claude TUI — the text lands but doesn't always submit).
    $TMUX send-keys -t "$sess:0" C-c 2>/dev/null
    sleep 0.3
    $TMUX send-keys -t "$sess:0" "$task" 2>/dev/null
    sleep 0.5
    $TMUX send-keys -t "$sess:0" C-m 2>/dev/null
    ;;

  hibernate)
    id_file=$(session_id_file "$project")

    if $TMUX has-session -t "$sess" 2>/dev/null; then
      # Capture last session ID before killing
      last_id=$($TMUX capture-pane -t "$sess:0" -p | grep -oE 'session.*[0-9a-f-]{36}' | head -1)
      $TMUX kill-session -t "$sess" 2>/dev/null
      log "hibernated session '$sess'"
    fi
    ;;

  *)
    echo "Unknown command: $cmd"
    exit 1
    ;;
esac
