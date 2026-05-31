#!/bin/zsh
# setup.sh — Viko Agent setup orchestrator
# Runs phases 01-04 in order. Resumable: each phase skips steps already done.
# Each sub-script can also be run independently: ./scripts/setup/01-deps.sh
set -e

SCRIPT_DIR="$(cd "$(dirname $0)" && pwd)"
SETUP_DIR="$SCRIPT_DIR/setup"

echo "╔══════════════════════════════════╗"
echo "║     Viko Agent Setup             ║"
echo "╚══════════════════════════════════╝"

"$SETUP_DIR/01-deps.sh"   || exit 1
"$SETUP_DIR/02-plugin.sh" || exit 1
"$SETUP_DIR/03-phone.sh"  || exit 1
"$SETUP_DIR/04-links.sh"  || exit 1

echo ""
echo "✅ Viko siap! Jalankan: ./scripts/start.sh"
echo ""
