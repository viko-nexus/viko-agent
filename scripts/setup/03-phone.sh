#!/bin/zsh
# 03-phone.sh — Configure WhatsApp phone number and guide device pairing
set -o pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; GREY='\033[0;37m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
fail() { printf "${RED}  ✗ %b${NC}\n" "$*"; exit 1 }
skip() { echo "${GREY}  — $*${NC}" }

STATE_DIR="$HOME/.whatsapp-channel"
ENV_FILE="$STATE_DIR/.env"
CREDS_FILE="$STATE_DIR/.baileys_auth/creds.json"
SCRIPT_DIR="$(cd "$(dirname $0)/../.." && pwd)"

echo "\n[03] Phone & Pairing"

# Phase A — Phone number config
if grep -q "WHATSAPP_PHONE_NUMBER=" "$ENV_FILE" 2>/dev/null; then
  EXISTING=$(grep "WHATSAPP_PHONE_NUMBER=" "$ENV_FILE" | cut -d= -f2)
  ok "Nomor WA sudah dikonfigurasi: $EXISTING"
else
  go "Konfigurasi nomor WhatsApp..."
  while true; do
    printf "  Masukkan nomor WA kamu (contoh: 628123456789): "
    read PHONE
    if [[ "$PHONE" =~ ^[0-9]{10,15}$ ]]; then
      break
    else
      printf "${RED}  ✗ Format salah. Hanya angka, 10-15 digit (contoh: 628123456789)${NC}\n"
    fi
  done
  mkdir -p "$STATE_DIR"
  echo "WHATSAPP_PHONE_NUMBER=$PHONE" >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  ok "Nomor WA disimpan: $PHONE"
fi

# Phase B — Device pairing check
if [ -f "$CREDS_FILE" ] && grep -q '"registered":true' "$CREDS_FILE" 2>/dev/null; then
  ok "Device sudah dipaired"
  exit 0
fi

# Pairing needed — print instructions and exit 0
echo ""
printf "${YELLOW}  Pairing diperlukan. Ikuti langkah berikut:${NC}\n"
echo ""
echo "  1. Jalankan Viko:          $SCRIPT_DIR/scripts/start.sh"
echo "  2. Buka tmux session:      tmux attach -t viko-agent"
echo "  3. Lihat pairing code yang muncul di terminal"
echo "  4. Di WhatsApp:"
echo "     Settings → Linked Devices → Link a Device"
echo "     → 'Link with phone number instead'"
echo "     → Masukkan kode dari terminal"
echo ""
echo "  5. Setelah paired, jalankan setup lagi: ./scripts/setup.sh"
echo ""
exit 0
