#!/usr/bin/env bash
# Installs viko maintenance cron jobs for the deploy user.
# Idempotent: safe to run multiple times.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/data"
mkdir -p "$LOG_DIR"

PRUNE_ENTRY="0 * * * * python3 $REPO_DIR/scripts/prune-idle-sessions.py --idle-hours 1 >> $LOG_DIR/prune.log 2>&1"
DELIVER_ENTRY="*/15 * * * * python3 $REPO_DIR/scripts/deliver_commitments.py >> $LOG_DIR/commitments.log 2>&1"

install_cron() {
  local entry="$1"
  local marker="$2"
  if crontab -l 2>/dev/null | grep -qF "$marker"; then
    echo "[setup-cron] already installed: $marker"
  else
    (crontab -l 2>/dev/null; echo "$entry") | crontab -
    echo "[setup-cron] installed: $entry"
  fi
}

install_cron "$PRUNE_ENTRY" "prune-idle-sessions.py"
install_cron "$DELIVER_ENTRY" "deliver_commitments.py"

echo "[setup-cron] Current viko cron entries:"
crontab -l 2>/dev/null | grep "viko-agent" || echo "(none yet)"
