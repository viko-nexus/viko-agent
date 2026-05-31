#!/bin/zsh

# Paths
CLAUDE="/Users/eksa/.local/bin/claude"
TMUX="/opt/homebrew/bin/tmux"
SESSION="viko-agent"
WORKDIR="/Users/eksa/Projects/viko-agent"
LOGFILE="$WORKDIR/logs/viko-agent.log"

mkdir -p "$WORKDIR/logs"

# Kill existing session if any
$TMUX kill-session -t $SESSION 2>/dev/null
pkill -f "watcher.sh" 2>/dev/null

# Start Viko in tmux (window 0)
# No stdout redirect — Claude needs a real TTY for interactive/channel mode.
# To view: tmux attach -t viko-agent
$TMUX new-session -d -s $SESSION -c "$WORKDIR" \
  "$CLAUDE --dangerously-skip-permissions"

# Start message watcher in a second tmux window (no sleep needed — session exists immediately)
$TMUX new-window -t $SESSION -c "$WORKDIR" "zsh $WORKDIR/scripts/watcher.sh"
$TMUX select-window -t $SESSION:0
