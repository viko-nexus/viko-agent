#!/bin/zsh
# manage-groups.sh — List & setup Viko in WhatsApp groups

WHATSAPP_DIR="$HOME/.whatsapp-channel"
VIKO_DIR="$(cd "$(dirname $0)/.." && pwd)"

python3 "$VIKO_DIR/tools/manage-groups.py" "$WHATSAPP_DIR"
