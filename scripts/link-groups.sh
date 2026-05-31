#!/bin/zsh
# Usage: ./scripts/link-groups.sh <project-name> <group-jid>
# Example: ./scripts/link-groups.sh mankop 120363409428298054@g.us
set -e
PROJECT=$1
JID=$2

if [ -z "$PROJECT" ] || [ -z "$JID" ]; then
  echo "Usage: $0 <project-name> <group-jid>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname $0)" && pwd)"
VIKO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_SRC="$VIKO_DIR/projects/$PROJECT/config.md"
TARGET_DIR="$HOME/.whatsapp-channel/groups/$JID"
TARGET="$TARGET_DIR/config.md"

if [ ! -f "$CONFIG_SRC" ]; then
  echo "Error: $CONFIG_SRC not found. Create projects/$PROJECT/config.md first." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
ln -sf "$CONFIG_SRC" "$TARGET"
echo "Linked projects/$PROJECT/config.md → $TARGET"
