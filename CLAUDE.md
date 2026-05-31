# Viko Agent

Viko adalah WhatsApp AI assistant dan developer agent yang berjalan di atas Claude Code. Satu Claude instance menangani beberapa WhatsApp group sekaligus, masing-masing dipetakan ke project dengan konteks dan personality sendiri.

## Struktur Project

```
viko-agent/
├── .claude/skills/          ← custom Claude skills (/manage-project, /viko-status)
├── docs/superpowers/        ← design specs dan implementation plans
├── projects/                ← per-project personality configs (gitignored, symlinked)
│   ├── mankop/              ← Koperasi Mankop (group JID: 120363409428298054@g.us)
│   ├── luxso/               ← Luxso Executive Dashboard (group JID: 120363424541097083@g.us)
│   └── forecastinn/         ← Forecastinn villa app (belum ada group)
├── scripts/
│   ├── setup.sh             ← setup otomatis di mesin baru (jalankan pertama kali)
│   ├── setup/               ← sub-scripts: 01-deps, 02-plugin, 03-phone, 04-links
│   ├── deploy.sh            ← copy src/server.ts → plugin cache lalu restart Claude Code
│   ├── link-groups.sh       ← tambah symlink project baru ke WhatsApp group
│   ├── start.sh             ← launch Viko di tmux session
│   └── manage-groups.sh     ← CLI untuk list & manage WhatsApp groups
├── src/
│   └── server.ts            ← MCP WhatsApp server (source of truth)
└── tools/
    └── manage-groups.py     ← group management CLI tool
```

## Projects & Konteks

| Project | Topic | Project Path | Group JID |
|---------|-------|-------------|-----------|
| mankop | Koperasi project Mankop — PM, Dev, QA, CS, Business Analysis | ~/Projects/mankop | 120363409428298054@g.us |
| luxso | Luxso Executive Dashboard — villa management | ~/Projects/forecastinn/clients/Luxso-executive-dashboard | 120363424541097083@g.us |
| forecastinn | Forecastinn villa app | ~/Projects/forecastinn | (belum ada group) |

## Workflow Penting

### Edit MCP Server
```zsh
# 1. Edit src/server.ts
# 2. Deploy ke plugin cache
./scripts/deploy.sh
# 3. Restart Claude Code (Cmd+Shift+P → Reload Window atau restart VS Code)
```

### Tambah Project Baru
Gunakan skill: `/manage-project` — atau manual:
```zsh
mkdir -p projects/<nama>
# buat projects/<nama>/config.md (personality Viko) dan README.md (metadata + JID)
./scripts/link-groups.sh <nama> <jid>@g.us
```

### Setup Mesin Baru
```zsh
./scripts/setup.sh   # interaktif, deteksi state otomatis, resumable
```

### Cek Status Semua Projects
Gunakan skill: `/viko-status`

## Arsitektur

```
WhatsApp (phone)
    ↕ Baileys (linked device protocol)
src/server.ts (MCP server)   ← di-deploy ke ~/.claude/plugins/cache/.../server.ts
    ↕ stdio
Claude Code process          ← dijalankan via scripts/start.sh (tmux session "viko-agent")
    ↕ membaca
~/.whatsapp-channel/groups/<jid>/config.md  ← symlink ke projects/*/config.md
```

Plugin WhatsApp routing pesan ke Claude berdasarkan group JID. Per-group personality dibaca dari `config.md` — diedit di `projects/*/config.md` (langsung aktif, tidak perlu restart).

## State Files (di luar repo)

| Path | Isi |
|------|-----|
| `~/.whatsapp-channel/.env` | Nomor WA (`WHATSAPP_PHONE_NUMBER`) |
| `~/.whatsapp-channel/.baileys_auth/` | WA auth state (session) |
| `~/.whatsapp-channel/groups/<jid>/` | Per-group config (symlink) + memory.md |
| `~/.whatsapp-channel/inbox/` | Media yang diterima |
| `logs/viko-agent.log` | Log output Claude process |
