#!/usr/bin/env bash
# Provision .env on the VPS from CI-provided environment (sourced from GitHub
# Actions secrets). Run by deploy.yml after `git reset`, before `docker compose up`.
#
# Portable keys are UPSERTED — GitHub secrets are the source of truth for them.
# Machine-specific keys (VIKO_PROJECTS_ROOT, HERMES_UID, HERMES_GID) are only
# defaulted when missing, so an existing host keeps its own values and a fresh
# VPS still gets working defaults.
set -eu

ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
touch "$ENV_FILE"

upsert() {
  local key="$1" val="$2"
  [ -z "$val" ] && return 0
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    grep -v "^${key}=" "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
  fi
  printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
}

default_if_missing() {
  local key="$1" val="$2"
  grep -q "^${key}=" "$ENV_FILE" 2>/dev/null || printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
}

# Portable — GitHub secrets are canonical (upsert, overriding any local drift)
for k in NINEROUTER_JWT_SECRET NINEROUTER_INITIAL_PASSWORD NINEROUTER_API_KEY_SECRET \
         ANTHROPIC_API_KEY GROQ_API_KEY OPENAI_API_KEY \
         WHATSAPP_HOME_CHANNEL WHATSAPP_OWNER_NUMBER VIKO_SSH_PUB VIKO_ISOLATION_GUARD; do
  upsert "$k" "${!k:-}"
done

# The Actions secret name GITHUB_TOKEN is reserved, so the PAT arrives as
# VIKO_GITHUB_TOKEN and is written back as GITHUB_TOKEN in .env.
upsert GITHUB_TOKEN "${VIKO_GITHUB_TOKEN:-}"

# Machine-specific — default only on a fresh VPS, never override an existing host
default_if_missing VIKO_PROJECTS_ROOT /home/viko/projects
default_if_missing HERMES_UID 1000
default_if_missing HERMES_GID 1000
# Port bind address — loopback by default; a host can set its Tailscale IP to
# expose the dashboards over Tailscale only. Host-specific, so never overridden.
default_if_missing VIKO_BIND_ADDR 127.0.0.1

echo "provision-env: .env now has $(grep -cE '^[A-Z_]+=' "$ENV_FILE") keys"
