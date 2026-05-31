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

# Start new detached tmux session running Viko
$TMUX new-session -d -s $SESSION -c "$WORKDIR" \
  "$CLAUDE --dangerously-skip-permissions --dangerously-load-development-channels plugin:whatsapp-claude-channel@whatsapp-claude-plugin >> $LOGFILE 2>&1"

# Auto-answer "I am using this for local development" prompt (development channels warning)
sleep 8 && $TMUX send-keys -t $SESSION "1" Enter &
