#!/usr/bin/env bash
# Fast local reload of the WhatsApp bridge WITHOUT rebuilding the image.
#
# Requires docker-compose.override.yml to bind-mount patches/whatsapp-bridge.js
# over /opt/hermes/scripts/whatsapp-bridge/bridge.js (see that file).
#
# Kills the running `node bridge.js`; the Hermes gateway respawns it from the
# bind-mounted file, so your latest edit is live in a few seconds.
#
# Usage: ./scripts/dev-reload-bridge.sh [container]   (default: viko-hermes)
set -euo pipefail

CONTAINER="${1:-viko-hermes}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "✗ Container '$CONTAINER' is not running. Start it first:" >&2
  echo "    docker compose --profile full up -d" >&2
  exit 1
fi

# Confirm the bind-mount is actually in effect (catches a forgotten override file).
if ! docker exec "$CONTAINER" sh -c 'mount | grep -q "/opt/hermes/scripts/whatsapp-bridge/bridge.js"' 2>/dev/null; then
  echo "⚠  bridge.js is NOT bind-mounted in $CONTAINER." >&2
  echo "   Ensure docker-compose.override.yml exists, then recreate the container:" >&2
  echo "     docker compose --profile full up -d --force-recreate $CONTAINER" >&2
  exit 1
fi

echo "→ Reloading bridge in $CONTAINER..."
# pkill returns non-zero if no process matched; tolerate it, gateway will spawn fresh.
docker exec "$CONTAINER" pkill -f 'bridge.js' 2>/dev/null || true

echo "✓ Bridge process killed; gateway will respawn it with your latest bridge.js."
echo "  Tail logs to confirm:  docker logs $CONTAINER -f | grep -i bridge"
