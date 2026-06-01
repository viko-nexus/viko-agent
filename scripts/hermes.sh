#!/usr/bin/env bash
# Install and configure Hermes Agent
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

header() { echo -e "\n${BOLD}${CYAN}==> $1${RESET}"; }
ok()     { echo -e "${GREEN}✓ $1${RESET}"; }
warn()   { echo -e "${YELLOW}! $1${RESET}"; }

# ── 1. Check prerequisites ────────────────────────────────────────────────────
header "Checking prerequisites"

if ! command -v git &>/dev/null; then
  echo "Error: git is required. Install via Xcode CLI tools: xcode-select --install"
  exit 1
fi
ok "git $(git --version | awk '{print $3}')"

if ! command -v node &>/dev/null; then
  warn "Node.js not found on PATH — Hermes installer will handle this"
else
  ok "node $(node --version)"
fi

# ── 2. Check if already installed ────────────────────────────────────────────
header "Checking existing installation"

if command -v hermes &>/dev/null; then
  ok "Hermes already installed: $(hermes --version 2>/dev/null | head -1)"
  echo ""
  echo "Pilih aksi:"
  echo "  1) Buka desktop app     → hermes desktop"
  echo "  2) Update Hermes + re-apply patches"
  echo "  3) Konfigurasi ulang    → hermes model"
  echo "  4) Keluar"
  read -r -p "Pilih [1-4]: " choice
  case "$choice" in
    1) hermes desktop ;;
    2)
      hermes update
      SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
      bash "$SCRIPT_DIR/post-update.sh"
      ;;
    3) hermes model ;;
    *) echo "Selesai." ;;
  esac
  exit 0
fi

# ── 3. Install Hermes ─────────────────────────────────────────────────────────
header "Installing Hermes Agent (+ desktop app)"
echo "Mengunduh installer dari NousResearch..."
echo ""

curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh \
  | bash -s -- --include-desktop

# ── 4. Reload shell PATH ──────────────────────────────────────────────────────
header "Reloading shell environment"

HERMES_BIN="$HOME/.hermes/bin"
if [[ ":$PATH:" != *":$HERMES_BIN:"* ]]; then
  export PATH="$HERMES_BIN:$PATH"
fi

# Add common install locations to PATH for this script's remaining steps
for bin_dir in "$HOME/.local/bin" "$HOME/.hermes/bin"; do
  [[ -d "$bin_dir" && ":$PATH:" != *":$bin_dir:"* ]] && export PATH="$bin_dir:$PATH"
done

# ── 5. Verify installation ────────────────────────────────────────────────────
header "Verifying installation"

if command -v hermes &>/dev/null; then
  ok "$(hermes --version 2>/dev/null | head -1)"
else
  warn "Hermes tidak ditemukan di PATH setelah install."
  echo "Jalankan di terminal kamu: source ~/.zshrc"
  echo "Lalu cek: hermes --version"
fi

# ── 6. Next steps ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Installation selesai!${RESET}"
echo ""
echo "Langkah selanjutnya:"
echo -e "  ${CYAN}hermes model${RESET}          — pilih LLM provider (Gemini Flash gratis)"
echo -e "  ${CYAN}hermes gateway setup${RESET}  — setup WhatsApp + Google Chat"
echo -e "  ${CYAN}hermes desktop${RESET}         — buka desktop app"
echo -e "  ${CYAN}hermes doctor${RESET}          — diagnosa jika ada masalah"
echo ""
echo "Untuk setup lengkap, ikuti: docs/setup.md (segera dibuat)"
