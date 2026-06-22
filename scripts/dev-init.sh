#!/usr/bin/env bash
# ─── One-shot LOCAL development bootstrap ─────────────────────────────────────
# Brings up the full local stack WITHOUT a 15-30 min image rebuild and ends by
# showing the WhatsApp QR for pairing. Safe to re-run (idempotent).
#
# What it does:
#   1. Sanity checks (.env, Docker, prebuilt hermes image)
#   2. Writes docker-compose.override.yml (bind-mounts source for fast iteration)
#   3. Creates the macOS SOUL.md nested-mount placeholder
#   4. Starts 9router + Hermes (uses the existing image — no build)
#   5. Seeds 9router combos and syncs the local API key into .env
#   6. Smoke-tests the LLM path
#   7. Pairs WhatsApp (prints the QR) if not already paired
#
# Usage:  ./scripts/dev-init.sh
#
# First time only (the image must exist before this script can mount onto it):
#   docker compose build hermes      # ~15-30 min, once
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

CONTAINER="viko-hermes"
ROUTER="viko-9router"
ROUTER_DB="data/9router/db/data.sqlite"
WA_CREDS="data/hermes/whatsapp/session/creds.json"

say()  { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ── 1. Preconditions ──────────────────────────────────────────────────────────
[ -f .env ] || die ".env not found. Run: cp .env.example .env  (then fill it in)"

if ! docker info >/dev/null 2>&1; then
  if [ "$(uname)" = "Darwin" ]; then
    say "Docker not running — launching Docker Desktop..."
    open -a Docker
    for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  fi
  docker info >/dev/null 2>&1 || die "Docker daemon is not reachable. Start Docker and re-run."
fi
ok "Docker is running"

if ! docker image inspect "${CONTAINER}:latest" >/dev/null 2>&1 \
   && ! docker compose --profile full config 2>/dev/null | grep -q "image: ${CONTAINER}"; then
  # compose builds the image as <project>-hermes / viko-hermes; check both
  if ! docker images --format '{{.Repository}}' | grep -qx "$CONTAINER"; then
    die "No local '${CONTAINER}' image. Build it once first:  docker compose build hermes"
  fi
fi
ok "Prebuilt hermes image found (no rebuild needed)"

# ── 2. Fast-iteration override (bind-mount source over the image) ─────────────
if [ ! -f docker-compose.override.yml ]; then
  say "Writing docker-compose.override.yml (local-only, gitignored)"
  cat > docker-compose.override.yml <<'YAML'
# LOCAL DEV ONLY — bind-mounts source over the image so bridge fixes need no
# rebuild. Gitignored. Reload after editing: ./scripts/dev-reload-bridge.sh
services:
  hermes:
    volumes:
      - ./patches/whatsapp-bridge.js:/opt/hermes/scripts/whatsapp-bridge/bridge.js:ro
      - ./patches/isolation-guard.py:/opt/hermes/docker/viko-isolation-guard.py:ro
      - ./scripts/init-hermes-config.py:/opt/viko/scripts/init-hermes-config.py:ro
YAML
  ok "override created"
else
  ok "override already present"
fi

# ── 3. macOS nested-bind-mount placeholder for SOUL.md ───────────────────────
# The base compose mounts admin/SOUL.md into the data/hermes bind; on VirtioFS
# the inner target must pre-exist or the container fails to start.
mkdir -p data/hermes
[ -f data/hermes/SOUL.md ] || { touch data/hermes/SOUL.md; ok "created data/hermes/SOUL.md placeholder"; }

# ── 4. Start the stack (no build) ────────────────────────────────────────────
say "Starting 9router + Hermes..."
docker compose --profile full up -d
# Force-recreate hermes so a freshly-built image is actually picked up — a plain
# `up -d` leaves the already-running container on the stale image.
docker compose --profile full up -d --force-recreate hermes
say "Waiting for 9router to be healthy..."
for _ in $(seq 1 60); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$ROUTER" 2>/dev/null)" = "healthy" ] && break
  sleep 2
done
ok "9router up"

# ── 5. Seed combos + sync the local 9router API key into .env ────────────────
if [ -f "$ROUTER_DB" ]; then
  say "Seeding 9router combos (idempotent)"
  python3 scripts/init-9router.py "$ROUTER_DB" || warn "init-9router.py reported an issue (continuing)"

  say "Syncing OPENAI_API_KEY from local 9router DB"
  KEY_CHANGED="$(python3 - "$ROUTER_DB" <<'PY'
import sqlite3, sys, re, pathlib
db = sys.argv[1]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
row = con.execute("SELECT key FROM apiKeys WHERE isActive=1 ORDER BY createdAt LIMIT 1").fetchone()
con.close()
if not row:
    print("NO_KEY"); raise SystemExit
key = row[0]
env = pathlib.Path(".env"); txt = env.read_text()
m = re.search(r'^OPENAI_API_KEY=(.*)$', txt, re.M)
if m and m.group(1).strip() == key:
    print("SAME")
else:
    pathlib.Path(".env.bak-localllm").write_text(txt)
    new = re.sub(r'^OPENAI_API_KEY=.*$', f'OPENAI_API_KEY={key}', txt, count=1, flags=re.M) \
          if m else txt.rstrip()+f"\nOPENAI_API_KEY={key}\n"
    env.write_text(new)
    print("CHANGED")
PY
)"
  case "$KEY_CHANGED" in
    CHANGED) ok "OPENAI_API_KEY synced to local key (backup: .env.bak-localllm); recreating hermes"
             docker compose --profile full up -d --force-recreate hermes >/dev/null ;;
    SAME)    ok "OPENAI_API_KEY already correct" ;;
    NO_KEY)  warn "No API key in local 9router yet. Open http://localhost:20128 (password in
         NINEROUTER_INITIAL_PASSWORD), add provider keys (Anthropic/Groq), generate an
         API key, paste it into .env as OPENAI_API_KEY, then re-run this script." ;;
  esac
else
  warn "No local 9router DB at $ROUTER_DB yet — configure providers + API key via the dashboard."
fi

# ── 6. Wait for Hermes + smoke-test the LLM path ─────────────────────────────
say "Waiting for Hermes gateway..."
for _ in $(seq 1 45); do
  docker exec "$CONTAINER" sh -c 'ps aux | grep -q "[h]ermes gateway"' 2>/dev/null && break
  sleep 2
done
LLM_CODE="$(docker exec "$CONTAINER" sh -c \
  'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $OPENAI_API_KEY" http://viko-9router:20128/v1/models' 2>/dev/null || echo "000")"
[ "$LLM_CODE" = "200" ] && ok "LLM path OK (9router 200)" || warn "9router auth returned HTTP $LLM_CODE — check OPENAI_API_KEY / provider config"

# ── 7. WhatsApp pairing (QR) ─────────────────────────────────────────────────
echo
if [ -f "$WA_CREDS" ]; then
  ok "WhatsApp already paired (creds.json present). Skipping QR."
  echo "  To re-pair: rm -rf data/hermes/whatsapp/session && ./scripts/dev-init.sh"
else
  warn "WhatsApp NOT paired. Pairing the SAME number as production will make this a new"
  warn "linked device — stop the VPS bridge first to avoid double-processing."
  echo
  if [ -t 0 ]; then
    say "Launching pairing — scan the QR with the Viko WhatsApp (Linked Devices → Link a Device):"
    docker exec -it "$CONTAINER" hermes whatsapp || warn "Pairing exited non-zero — re-run: docker exec -it $CONTAINER hermes whatsapp"
    docker compose --profile full up -d --force-recreate hermes >/dev/null
  else
    warn "Not a TTY — pair manually:  docker exec -it $CONTAINER hermes whatsapp"
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo
ok "Local stack ready."
cat <<EOF

  Dashboard : http://localhost:9119
  9router   : http://localhost:20128
  Bridge log: docker exec $CONTAINER tail -f /opt/data/whatsapp/bridge.log

  Iterate on the bridge WITHOUT rebuilding:
    1. edit patches/whatsapp-bridge.js
    2. ./scripts/dev-reload-bridge.sh
    3. watch the bridge log above

  Rebuild is ONLY needed for Dockerfile.hermes or the Python source patches.
EOF
