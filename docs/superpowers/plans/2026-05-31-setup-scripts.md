# Viko Agent Setup Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an interactive, resumable setup system (`scripts/setup.sh` + 4 sub-scripts) that automates Viko Agent installation on a fresh machine or re-setup after reinstall.

**Architecture:** One orchestrator (`setup.sh`) runs 4 sub-scripts in sequence; each sub-script detects its own state and skips completed steps. Colored terminal output (✓/→/✗/—) via ANSI codes. Sub-scripts are independently runnable.

**Tech Stack:** zsh, claude CLI, brew, bun, curl

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `scripts/setup/01-deps.sh` | Check & install bun, tmux, claude |
| Create | `scripts/setup/02-plugin.sh` | Install WhatsApp Claude plugin |
| Create | `scripts/setup/03-phone.sh` | Configure phone number + pairing guide |
| Create | `scripts/setup/04-links.sh` | Setup symlinks from projects/ → ~/.whatsapp-channel/groups/ |
| Create | `scripts/setup.sh` | Orchestrator — runs 01–04 in order |

---

## Task 1: Create `scripts/setup/01-deps.sh`

**Files:**
- Create: `scripts/setup/01-deps.sh`

- [ ] **Step 1: Create the file**

```bash
mkdir -p /Users/eksa/Projects/viko-agent/scripts/setup
```

Write `/Users/eksa/Projects/viko-agent/scripts/setup/01-deps.sh`:

```zsh
#!/bin/zsh
# 01-deps.sh — Check and install: brew, tmux, bun, claude

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
fail() { echo "${RED}  ✗ $*${NC}"; exit 1 }

echo "\n[01] Dependencies"

# brew — required for tmux; cannot auto-install
if ! command -v brew &>/dev/null; then
  fail "Homebrew tidak ditemukan. Install dulu:\n      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\n      Lalu jalankan setup lagi."
fi
ok "brew $(brew --version 2>/dev/null | head -1 | awk '{print $2}')"

# tmux
if ! command -v tmux &>/dev/null; then
  go "Installing tmux via brew..."
  brew install tmux || fail "brew install tmux gagal"
fi
ok "tmux $(tmux -V 2>/dev/null | awk '{print $2}')"

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
ok "claude $(claude --version 2>/dev/null | head -1)"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x /Users/eksa/Projects/viko-agent/scripts/setup/01-deps.sh
```

- [ ] **Step 3: Verify it runs (all deps should already be present)**

```bash
/Users/eksa/Projects/viko-agent/scripts/setup/01-deps.sh
```

Expected output:
```
[01] Dependencies
  ✓ brew 4.x.x
  ✓ tmux 3.x
  ✓ bun 1.x.x
  ✓ claude 2.x.x
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup/01-deps.sh
git commit -m "feat: add setup/01-deps.sh — check and install bun, tmux, brew, claude"
```

---

## Task 2: Create `scripts/setup/02-plugin.sh`

**Files:**
- Create: `scripts/setup/02-plugin.sh`

- [ ] **Step 1: Write the file**

Write `/Users/eksa/Projects/viko-agent/scripts/setup/02-plugin.sh`:

```zsh
#!/bin/zsh
# 02-plugin.sh — Install whatsapp-claude-channel plugin

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
fail() { echo "${RED}  ✗ $*${NC}"; exit 1 }

echo "\n[02] WhatsApp Plugin"

# Check if already installed
if claude plugin list 2>/dev/null | grep -q "whatsapp-claude-channel"; then
  ok "whatsapp-claude-channel sudah terinstall"
  exit 0
fi

# Add marketplace
go "Adding marketplace: Rich627/whatsapp-claude-plugin..."
claude plugin marketplace add Rich627/whatsapp-claude-plugin || fail "Gagal menambah marketplace"

# Install plugin
go "Installing whatsapp-claude-channel..."
claude plugin install whatsapp-claude-channel@whatsapp-claude-plugin || fail "Gagal install plugin"

ok "Plugin berhasil diinstall."
echo ""
echo "  PENTING: Restart Claude Code sekarang agar plugin aktif."
echo "  Setelah restart, jalankan setup lagi untuk lanjut ke langkah berikutnya."
exit 0
```

- [ ] **Step 2: Make executable**

```bash
chmod +x /Users/eksa/Projects/viko-agent/scripts/setup/02-plugin.sh
```

- [ ] **Step 3: Verify skip logic (plugin already installed)**

```bash
/Users/eksa/Projects/viko-agent/scripts/setup/02-plugin.sh
```

Expected (plugin already installed):
```
[02] WhatsApp Plugin
  ✓ whatsapp-claude-channel sudah terinstall
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup/02-plugin.sh
git commit -m "feat: add setup/02-plugin.sh — install whatsapp-claude-channel plugin"
```

---

## Task 3: Create `scripts/setup/03-phone.sh`

**Files:**
- Create: `scripts/setup/03-phone.sh`

- [ ] **Step 1: Write the file**

Write `/Users/eksa/Projects/viko-agent/scripts/setup/03-phone.sh`:

```zsh
#!/bin/zsh
# 03-phone.sh — Configure WhatsApp phone number and guide device pairing

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; GREY='\033[0;37m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
fail() { echo "${RED}  ✗ $*${NC}"; exit 1 }
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
    echo -n "  Masukkan nomor WA kamu (contoh: 628123456789): "
    read PHONE
    # Validate: digits only, 10-15 chars
    if [[ "$PHONE" =~ ^[0-9]{10,15}$ ]]; then
      break
    else
      echo "${RED}  ✗ Format salah. Hanya angka, 10-15 digit (contoh: 628123456789)${NC}"
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

# Pairing needed — print instructions and exit 0 (not an error)
echo ""
echo "${YELLOW}  Pairing diperlukan. Ikuti langkah berikut:${NC}"
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x /Users/eksa/Projects/viko-agent/scripts/setup/03-phone.sh
```

- [ ] **Step 3: Verify skip logic (phone + pairing already done)**

```bash
/Users/eksa/Projects/viko-agent/scripts/setup/03-phone.sh
```

Expected (both already configured):
```
[03] Phone & Pairing
  ✓ Nomor WA sudah dikonfigurasi: 628xxxxx
  ✓ Device sudah dipaired
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup/03-phone.sh
git commit -m "feat: add setup/03-phone.sh — configure phone number and guide pairing"
```

---

## Task 4: Create `scripts/setup/04-links.sh`

**Files:**
- Create: `scripts/setup/04-links.sh`

- [ ] **Step 1: Write the file**

Write `/Users/eksa/Projects/viko-agent/scripts/setup/04-links.sh`:

```zsh
#!/bin/zsh
# 04-links.sh — Setup symlinks from projects/ to ~/.whatsapp-channel/groups/

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; GREY='\033[0;37m'; NC='\033[0m'
ok()   { echo "${GREEN}  ✓ $*${NC}" }
go()   { echo "${YELLOW}  → $*${NC}" }
err()  { echo "${RED}  ✗ $*${NC}" }
skip() { echo "${GREY}  — $*${NC}" }

SCRIPT_DIR="$(cd "$(dirname $0)/../.." && pwd)"
PROJECTS_DIR="$SCRIPT_DIR/projects"

echo "\n[04] Group Symlinks"

# Iterate over each project directory
for PROJECT_DIR in "$PROJECTS_DIR"/*/; do
  NAME=$(basename "$PROJECT_DIR")
  README="$PROJECT_DIR/README.md"

  if [ ! -f "$README" ]; then
    skip "$NAME: README.md tidak ditemukan"
    continue
  fi

  # Extract JID from line: "- **WhatsApp group JID**: <jid>"
  JID=$(grep -o '\*\*WhatsApp group JID\*\*: [^[:space:]]*' "$README" | awk '{print $NF}')

  # Skip if no JID or placeholder
  if [ -z "$JID" ] || echo "$JID" | grep -q "belum ada"; then
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x /Users/eksa/Projects/viko-agent/scripts/setup/04-links.sh
```

- [ ] **Step 3: Verify — symlinks already exist, should show ✓ for mankop and luxso**

```bash
/Users/eksa/Projects/viko-agent/scripts/setup/04-links.sh
```

Expected:
```
[04] Group Symlinks
  ✓ mankop → 120363409428298054@g.us
  ✓ luxso  → 120363424541097083@g.us
  — forecastinn: belum ada group WhatsApp
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup/04-links.sh
git commit -m "feat: add setup/04-links.sh — auto-symlink all projects to whatsapp groups"
```

---

## Task 5: Create `scripts/setup.sh` (orchestrator)

**Files:**
- Create: `scripts/setup.sh`

- [ ] **Step 1: Write the file**

Write `/Users/eksa/Projects/viko-agent/scripts/setup.sh`:

```zsh
#!/bin/zsh
# setup.sh — Viko Agent setup orchestrator
# Runs phases 01-04 in order. Resumable: each phase skips steps already done.
# Each sub-script can also be run independently: ./scripts/setup/01-deps.sh

set -e

SCRIPT_DIR="$(cd "$(dirname $0)" && pwd)"
SETUP_DIR="$SCRIPT_DIR/setup"

echo "╔══════════════════════════════════╗"
echo "║     Viko Agent Setup             ║"
echo "╚══════════════════════════════════╝"

"$SETUP_DIR/01-deps.sh"   || exit 1
"$SETUP_DIR/02-plugin.sh" || exit 1
"$SETUP_DIR/03-phone.sh"  || exit 1
"$SETUP_DIR/04-links.sh"  || exit 1

echo ""
echo "✅ Viko siap! Jalankan: ./scripts/start.sh"
echo ""
```

- [ ] **Step 2: Make executable**

```bash
chmod +x /Users/eksa/Projects/viko-agent/scripts/setup.sh
```

- [ ] **Step 3: Run full setup end-to-end (all phases should skip — already configured)**

```bash
/Users/eksa/Projects/viko-agent/scripts/setup.sh
```

Expected (everything already set up):
```
╔══════════════════════════════════╗
║     Viko Agent Setup             ║
╚══════════════════════════════════╝

[01] Dependencies
  ✓ brew 4.x.x
  ✓ tmux 3.x
  ✓ bun 1.x.x
  ✓ claude 2.x.x

[02] WhatsApp Plugin
  ✓ whatsapp-claude-channel sudah terinstall

[03] Phone & Pairing
  ✓ Nomor WA sudah dikonfigurasi: 628xxxxx
  ✓ Device sudah dipaired

[04] Group Symlinks
  ✓ mankop → 120363409428298054@g.us
  ✓ luxso  → 120363424541097083@g.us
  — forecastinn: belum ada group WhatsApp

✅ Viko siap! Jalankan: ./scripts/start.sh
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup.sh
git commit -m "feat: add setup.sh orchestrator — resumable multi-phase Viko setup"
```

---

## Self-Review

**Spec coverage:**
- [x] Orchestrator `setup.sh` runs 01–04 → Task 5
- [x] `01-deps.sh`: brew check+exit, tmux auto-install, bun auto-install, claude check+exit → Task 1
- [x] `02-plugin.sh`: skip if installed, marketplace add + install → Task 2
- [x] `03-phone.sh`: Phase A phone config + Phase B pairing guide → Task 3
- [x] `04-links.sh`: reads JID from README.md, checks symlink, runs link-groups.sh → Task 4
- [x] Colored output ✓/→/✗/— via ANSI codes → all tasks
- [x] Interactive phone prompt with validation (digits only, 10-15 chars) → Task 3
- [x] Re-prompt on invalid phone → Task 3
- [x] Exit 0 on pairing-needed (not an error) → Task 3
- [x] link-groups.sh failure is non-fatal → Task 4
- [x] Each sub-script independently runnable → all tasks
- [x] `set -e` in orchestrator to stop on phase failure → Task 5

**Placeholders:** None — all scripts contain complete code.

**Type consistency:** `SCRIPT_DIR` computed consistently in each sub-script using `$(cd "$(dirname $0)/../.." && pwd)` for sub-scripts and `$(cd "$(dirname $0)" && pwd)` for orchestrator. `link-groups.sh` called with `"$SCRIPT_DIR/scripts/link-groups.sh"` from `04-links.sh`. ✓
