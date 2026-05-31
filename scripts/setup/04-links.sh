#!/bin/zsh
# 04-links.sh — Setup symlinks from projects/ to ~/.whatsapp-channel/groups/
set -o pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; GREY='\033[0;37m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
err()  { echo "${RED}  ✗ $*${NC}" }
skip() { echo "${GREY}  — $*${NC}" }

SCRIPT_DIR="$(cd "$(dirname $0)/../.." && pwd)"
PROJECTS_DIR="$SCRIPT_DIR/projects"

echo "\n[04] Group Symlinks"

for PROJECT_DIR in "$PROJECTS_DIR"/*/; do
  NAME=$(basename "$PROJECT_DIR")
  README="$PROJECT_DIR/README.md"

  if [ ! -f "$README" ]; then
    skip "$NAME: README.md tidak ditemukan"
    continue
  fi

  # Extract JID from line: "- **WhatsApp group JID**: <jid>"
  JID=$(grep -o '\*\*WhatsApp group JID\*\*: [^[:space:]]*' "$README" | awk '{print $NF}')

  # Skip if no JID or is a placeholder
  if [ -z "$JID" ] || echo "$JID" | grep -q "belum"; then
    skip "$NAME: belum ada group WhatsApp"
    continue
  fi

  TARGET="$HOME/.whatsapp-channel/groups/$JID/config.md"
  EXPECTED="$PROJECT_DIR/config.md"

  # Check if symlink already points to the right place
  if [ -L "$TARGET" ] && [ "$(readlink "$TARGET")" = "$EXPECTED" ]; then
    ok "$NAME → $JID"
    continue
  fi

  # Link it
  go "Linking $NAME → $JID..."
  if "$SCRIPT_DIR/scripts/link-groups.sh" "$NAME" "$JID" 2>&1; then
    ok "$NAME → $JID"
  else
    err "$NAME: link gagal (lanjut ke project berikutnya)"
  fi
done
