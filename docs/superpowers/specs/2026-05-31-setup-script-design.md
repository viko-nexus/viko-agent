# Viko Agent — Setup Script Design

**Date**: 2026-05-31
**Status**: Approved

## Overview

A multi-script setup system that automates Viko Agent installation on a fresh machine or re-setup after a Claude Code reinstall. Detects existing state at each phase and skips steps already completed. Interactive for inputs that require user action (phone number, pairing).

## Folder Structure

```
scripts/
├── setup.sh           ← orchestrator: runs all phases in order
└── setup/
    ├── 01-deps.sh     ← check & install bun, tmux, claude CLI
    ├── 02-plugin.sh   ← install WhatsApp Claude plugin
    ├── 03-phone.sh    ← configure phone number + guide device pairing
    └── 04-links.sh    ← setup symlinks from projects/ → ~/.whatsapp-channel/groups/
```

Each sub-script can be run independently: `./scripts/setup/01-deps.sh`

## Orchestrator: `setup.sh`

Runs phases 01–04 in sequence. Exits immediately if a phase fails (non-zero exit code). On re-run, each phase detects its own state and skips if already complete — making setup fully resumable.

```
[01] deps   → skip if bun + tmux + claude all present
[02] plugin → skip if whatsapp-claude-channel already installed
[03] phone  → skip phone config if .env has WHATSAPP_PHONE_NUMBER
              skip pairing guide if creds.json exists and registered:true
[04] links  → for each projects/*/ with a JID in README.md, link if not already symlinked
[--] Done   → print: "Viko ready. Run ./scripts/start.sh to launch."
```

## Phase Details

### `01-deps.sh` — Dependencies

Checks for each dependency in order. Installs missing ones:

| Dependency | Check | Install |
|---|---|---|
| `brew` | `which brew` | Print install URL + exit (cannot auto-install) |
| `tmux` | `which tmux` | `brew install tmux` |
| `bun` | `which bun` | `curl -fsSL https://bun.sh/install \| bash` then source env |
| `claude` | `which claude` | Print: install from claude.ai/download + exit |

If brew or claude are missing, print clear manual instructions and exit with code 1.

### `02-plugin.sh` — Plugin Installation

Skip condition: `claude plugin list` output contains `whatsapp-claude-channel`.

If not installed:
1. `claude plugin marketplace add Rich627/whatsapp-claude-plugin`
2. `claude plugin install whatsapp-claude-channel@whatsapp-claude-plugin`

After install, print reminder: restart Claude Code once before running setup again (plugin activates on next launch).

### `03-phone.sh` — Phone Configuration & Pairing

**Phase A — Phone number config:**
- Skip if `~/.whatsapp-channel/.env` contains `WHATSAPP_PHONE_NUMBER=`
- Otherwise: prompt *"Masukkan nomor WhatsApp kamu (contoh: 628123456789):"*
- Write `WHATSAPP_PHONE_NUMBER=<input>` to `~/.whatsapp-channel/.env` (create dir if needed)

**Phase B — Device pairing:**
- Skip if `~/.whatsapp-channel/.baileys_auth/creds.json` exists AND contains `"registered":true`
- Otherwise: print step-by-step instructions:
  ```
  Pairing diperlukan. Ikuti langkah berikut:
  1. Jalankan: ./scripts/start.sh
  2. Buka tmux session: tmux attach -t viko-agent
  3. Lihat pairing code yang muncul
  4. Di WhatsApp: Settings → Linked Devices → Link a Device
     → "Link with phone number instead" → masukkan kode
  5. Setelah paired, jalankan setup.sh lagi untuk lanjut
  ```
- Exit 0 (not an error — user needs to pair manually then re-run)

### `04-links.sh` — Symlink Setup

For each directory in `projects/*/`:
1. Read `projects/<name>/README.md`
2. Extract JID from line matching `**WhatsApp group JID**: <jid>` (skip if `belum ada`)
3. Check if `~/.whatsapp-channel/groups/<jid>/config.md` is already a symlink to `projects/<name>/config.md`
4. If not: run `./scripts/link-groups.sh <name> <jid>`
5. Report: `✓ mankop linked`, `→ luxso: linking...`, `— forecastinn: no group yet`

## UX: Output Format

All scripts use consistent colored output:

```
✓ [green]  already done / success
→ [yellow] action being taken
✗ [red]    error / failed
— [grey]   skipped (no group yet, not applicable)
```

Example run (fresh machine):
```
[01] Dependencies
  → Installing tmux via brew...
  ✓ bun 1.x.x
  ✓ claude 2.x.x

[02] Plugin
  → Adding marketplace: Rich627/whatsapp-claude-plugin
  → Installing whatsapp-claude-channel
  ✓ Plugin installed. Restart Claude Code, then re-run setup.

[03] Phone & Pairing
  Masukkan nomor WhatsApp kamu (contoh: 628123456789): 628xx
  ✓ Phone number saved.
  Pairing diperlukan. Jalankan ./scripts/start.sh dan ikuti instruksi...

[04] Links
  ✓ mankop → 120363409428298054@g.us
  ✓ luxso  → 120363424541097083@g.us
  — forecastinn: no group yet

Viko ready. Jalankan: ./scripts/start.sh
```

## Error Handling

- Missing `brew`: print `https://brew.sh` install instructions + exit 1
- Missing `claude`: print download URL + exit 1
- Plugin install fails: print error from claude CLI + exit 1
- Invalid phone number format: re-prompt (must be digits only, 10-15 chars)
- `link-groups.sh` fails: print error + continue to next project (non-fatal)

## State Files Referenced

| File | Purpose |
|------|---------|
| `~/.whatsapp-channel/.env` | Phone number config |
| `~/.whatsapp-channel/.baileys_auth/creds.json` | WA auth state |
| `~/.whatsapp-channel/groups/<jid>/config.md` | Group symlinks |
| `projects/*/README.md` | JID source for `04-links.sh` |
