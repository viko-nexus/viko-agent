#!/usr/bin/env bash
# Fast local reload of the WhatsApp bridge WITHOUT rebuilding the image (~30s).
#
# Requires docker-compose.override.yml to bind-mount patches/whatsapp-bridge.js
# over /opt/hermes/scripts/whatsapp-bridge/bridge.js (see that file).
#
# The Hermes gateway supervises the bridge and treats an unexpected bridge exit
# as FATAL (it does NOT respawn a killed bridge — verified). So the reliable
# reload is a full container restart: the gateway re-runs and re-spawns the
# bridge from the bind-mounted file, picking up your latest edit.
#
# NOTE: the bridge's own stdout goes to /opt/data/whatsapp/bridge.log
# (= data/hermes/whatsapp/bridge.log on the host), NOT `docker logs`. This
# script tails that file to confirm the reload.
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

echo "→ Restarting $CONTAINER to reload bridge from bind-mounted bridge.js..."
docker restart "$CONTAINER" >/dev/null

echo "→ Waiting for the bridge to reconnect (up to ~45s)..."
for i in $(seq 1 45); do
  if docker exec "$CONTAINER" sh -c 'ps aux | grep -q "[b]ridge.js"' 2>/dev/null; then
    echo "✓ Bridge process is back up (after ~${i}s) — running your latest bridge.js."
    echo "  Live bridge log:  docker exec $CONTAINER tail -f /opt/data/whatsapp/bridge.log"
    exit 0
  fi
  sleep 1
done

echo "⚠  Bridge process did not reappear within 45s. Check the logs:" >&2
echo "     docker exec $CONTAINER tail -50 /opt/data/whatsapp/bridge.log" >&2
echo "     docker logs $CONTAINER --tail 50" >&2
exit 1
