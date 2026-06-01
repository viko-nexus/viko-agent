#!/usr/bin/env bash
# Run after `hermes update` to re-apply custom patches.
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PATCHES_DIR="$PROJECT_DIR/patches"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/hermes-agent}"

echo -e "${BOLD}Applying viko-agent patches to Hermes...${RESET}"

# ── whatsapp-bridge patch ─────────────────────────────────────────────────────
BRIDGE_SRC="$PATCHES_DIR/whatsapp-bridge.js"
BRIDGE_DST="$HERMES_HOME/scripts/whatsapp-bridge/bridge.js"

if [[ ! -f "$BRIDGE_SRC" ]]; then
  echo -e "${YELLOW}! Patch not found: $BRIDGE_SRC${RESET}"
  exit 1
fi

cp "$BRIDGE_SRC" "$BRIDGE_DST"
echo -e "${GREEN}✓ whatsapp-bridge.js patched${RESET}"

# ── gateway/run.py patch (Indonesian notifications) ───────────────────────────
RUN_PY_PATCH="$PATCHES_DIR/apply-run-py.py"

if [[ ! -f "$RUN_PY_PATCH" ]]; then
  echo -e "${YELLOW}! Patch not found: $RUN_PY_PATCH${RESET}"
else
  python3 "$RUN_PY_PATCH"
  rm -f "$HERMES_HOME/gateway/__pycache__/run"*.pyc 2>/dev/null || true
  echo -e "${GREEN}✓ gateway/run.py patched + pyc cleared${RESET}"
fi

# ── Restart gateway ───────────────────────────────────────────────────────────
if launchctl list | grep -q "ai.hermes.gateway"; then
  launchctl stop ai.hermes.gateway 2>/dev/null || true
  sleep 2
  launchctl start ai.hermes.gateway 2>/dev/null || true
  echo -e "${GREEN}✓ Gateway restarted${RESET}"
fi

echo -e "\n${BOLD}Done.${RESET} Patches applied."
