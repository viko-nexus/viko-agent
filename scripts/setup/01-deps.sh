#!/bin/zsh
# 01-deps.sh — Check and install: brew, tmux, bun, claude
set -o pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
fail() { printf "${RED}  ✗ %b${NC}\n" "$*"; exit 1 }

echo "\n[01] Dependencies"

# brew — required for tmux; cannot auto-install
if ! command -v brew &>/dev/null; then
  fail "Homebrew tidak ditemukan. Install dulu:\n      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\n      Lalu jalankan setup lagi."
fi
ok "$(brew --version 2>/dev/null | head -1)"

# tmux
if ! command -v tmux &>/dev/null; then
  go "Installing tmux via brew..."
  brew install tmux 2>&1 || fail "brew install tmux gagal"
fi
ok "$(tmux -V 2>/dev/null)"

# bun
if ! command -v bun &>/dev/null; then
  go "Installing bun..."
  curl -fsSL https://bun.sh/install | bash || fail "bun install gagal"
  # Source bun env so it's available in this session
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
fi
ok "bun $(bun --version 2>/dev/null)"

# claude CLI — cannot auto-install
if ! command -v claude &>/dev/null; then
  fail "Claude CLI tidak ditemukan. Install dari: https://claude.ai/download\n      Lalu jalankan setup lagi."
fi
ok "$(claude --version 2>/dev/null | head -1)"
