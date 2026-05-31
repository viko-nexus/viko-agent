#!/bin/zsh
# 02-plugin.sh — Install whatsapp-claude-channel plugin
set -o pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
fail() { printf "${RED}  ✗ %b${NC}\n" "$*"; exit 1 }

echo "\n[02] WhatsApp Plugin"

# Check if already installed
if claude plugin list 2>/dev/null | grep -q "whatsapp-claude-channel"; then
  ok "whatsapp-claude-channel sudah terinstall"
  exit 0
fi

# Add marketplace
go "Adding marketplace: Rich627/whatsapp-claude-plugin..."
claude plugin marketplace add Rich627/whatsapp-claude-plugin 2>&1 || fail "Gagal menambah marketplace"

# Install plugin
go "Installing whatsapp-claude-channel..."
claude plugin install whatsapp-claude-channel@whatsapp-claude-plugin 2>&1 || fail "Gagal install plugin"

ok "Plugin berhasil diinstall."
echo ""
echo "  PENTING: Restart Claude Code sekarang agar plugin aktif."
echo "  Setelah restart, jalankan setup lagi untuk lanjut ke langkah berikutnya."
exit 0
