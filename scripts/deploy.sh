#!/bin/zsh
set -e
PLUGIN_CACHE="$HOME/.claude/plugins/cache/whatsapp-claude-plugin/whatsapp-claude-channel/0.8.0"
SCRIPT_DIR="$(cd "$(dirname $0)" && pwd)"
SRC="$SCRIPT_DIR/../src/server.ts"

if [ ! -f "$SRC" ]; then
  echo "Error: $SRC not found" >&2
  exit 1
fi

cp "$SRC" "$PLUGIN_CACHE/server.ts"
echo "Deployed src/server.ts → $PLUGIN_CACHE/server.ts"
echo "Restart Claude Code to reload the MCP server."
