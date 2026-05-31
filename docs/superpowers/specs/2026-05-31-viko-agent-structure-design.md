# Viko Agent — Project Structure Design

**Date**: 2026-05-31
**Status**: Approved

## Overview

Viko is a WhatsApp AI assistant and developer agent with per-project context. It runs as a single Claude Code process with the `whatsapp-claude-channel` plugin, handling multiple WhatsApp groups simultaneously — each group mapped to a specific project with its own topic and codebase.

This spec covers reorganizing the `viko-agent/` folder to be the source of truth for all Viko configuration and code.

## Architecture

```
WhatsApp (phone)
    ↕ Baileys
MCP Server (server.ts)          ← source: viko-agent/src/server.ts
    ↕ stdio
Claude Code (claude process)    ← launched by scripts/start.sh
    ↕ reads
~/.whatsapp-channel/groups/<jid>/config.md  ← symlinked from viko-agent/projects/*/config.md
```

One Claude instance handles all groups. Per-group context is configured via `config.md` per group JID — the plugin reads it directly. No multi-instance setup needed.

## Folder Structure

```
viko-agent/
├── .claude/
│   ├── settings.json              ← project-level Claude Code settings
│   └── skills/
│       ├── manage-project.md      ← skill: setup/add a new project
│       └── viko-status.md         ← skill: check status of all active projects
├── projects/
│   ├── mankop/
│   │   ├── config.md              ← Viko personality for Mankop WA group (symlinked)
│   │   └── README.md              ← project metadata (topic, path, group JID)
│   ├── luxso/
│   │   ├── config.md
│   │   └── README.md
│   └── forecastinn/
│       ├── config.md
│       └── README.md
├── src/
│   └── server.ts                  ← source of truth for MCP WhatsApp server
├── scripts/
│   ├── deploy.sh                  ← copy src/server.ts → plugin cache
│   ├── link-groups.sh             ← setup symlink for a project's config.md
│   ├── start.sh                   ← launch Viko (tmux session)
│   └── manage-groups.sh           ← list & manage WhatsApp groups
├── tools/
│   └── manage-groups.py           ← group management CLI tool
├── docs/
│   └── superpowers/specs/         ← design docs
├── .gitignore
└── README.md                      ← overview of viko-agent
```

## Components

### `src/server.ts`
The MCP server that bridges WhatsApp (via Baileys) and Claude Code. This is the **only file** that needs to be deployed to the plugin cache — all other plugin files (`package.json`, `node_modules`, etc.) stay in the cache and are managed by the plugin system.

Deploy workflow: edit `src/server.ts` → run `scripts/deploy.sh` → restart Claude Code.

### `projects/<name>/config.md`
Per-group personality file read directly by the plugin. Stored in `viko-agent/projects/` and **symlinked** into `~/.whatsapp-channel/groups/<jid>/config.md` so the plugin reads it without a deploy step. Editing the file takes effect on the next message without any restart.

### `projects/<name>/README.md`
Human-readable metadata for each project:
```markdown
# <Project Name>
- **Topic**: <what Viko focuses on in this group>
- **Project path**: ~/Projects/<name>
- **WhatsApp group JID**: <jid>@g.us
- **Symlink**: ~/.whatsapp-channel/groups/<jid>/config.md → projects/<name>/config.md
```

### `scripts/deploy.sh`
```bash
#!/bin/zsh
PLUGIN_CACHE="$HOME/.claude/plugins/cache/whatsapp-claude-plugin/whatsapp-claude-channel/0.8.0"
cp "$(dirname $0)/../src/server.ts" "$PLUGIN_CACHE/server.ts"
echo "Deployed src/server.ts → plugin cache. Restart Claude Code to reload."
```

### `scripts/link-groups.sh`
```bash
#!/bin/zsh
# Usage: ./scripts/link-groups.sh <project-name> <group-jid>
# Example: ./scripts/link-groups.sh mankop 1234567890-123456@g.us
PROJECT=$1
JID=$2
TARGET="$HOME/.whatsapp-channel/groups/$JID"
mkdir -p "$TARGET"
ln -sf "$(pwd)/projects/$PROJECT/config.md" "$TARGET/config.md"
echo "Linked projects/$PROJECT/config.md → ~/.whatsapp-channel/groups/$JID/config.md"
```

### `scripts/start.sh`
Launches Viko in a detached tmux session (moved from `start-viko-agent.sh`, content unchanged).

### `.claude/skills/manage-project.md`
Custom skill for adding a new project to Viko: creates `projects/<name>/` folder, generates `config.md` and `README.md` templates, runs `link-groups.sh` to wire up the symlink.

### `.claude/skills/viko-status.md`
Custom skill for checking the status of all active projects: lists groups, verifies symlinks are intact, checks which projects are active in WhatsApp.

## `.gitignore`
```
# Logs
*.log
viko-agent.log

# macOS
.DS_Store
**/.DS_Store

# Runtime / temp
*.tmp
.env
```

## Git Setup
- Init git in `viko-agent/` (local only, no remote required for now)
- Commit all source files including `src/server.ts`, `scripts/`, `tools/`, `.claude/`, `projects/`
- `~/.whatsapp-channel/` is **not** tracked — it contains auth state, inbox, and runtime data

## Migration Steps (one-time)
1. Copy `server.ts` from plugin cache → `src/server.ts`
2. Move `start-viko-agent.sh` → `scripts/start.sh`
3. Move `manage-groups.sh` → `scripts/manage-groups.sh`
4. Move `manage-groups.py` → `tools/manage-groups.py`
5. Create `projects/mankop/`, `projects/luxso/`, `projects/forecastinn/` with `config.md` + `README.md`
6. Run `link-groups.sh` for each project to setup symlinks
7. Add `scripts/deploy.sh` and `scripts/link-groups.sh`
8. Init git and commit
9. Delete `.DS_Store` files if any exist
