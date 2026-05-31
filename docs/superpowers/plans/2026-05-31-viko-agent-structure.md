# Viko Agent Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `viko-agent/` into a clean, version-controlled project with `src/server.ts` as source of truth, per-project configs symlinked to the WhatsApp plugin, and custom Claude skills.

**Architecture:** One Claude Code process handles all WhatsApp groups via the `whatsapp-claude-channel` plugin. Per-group personality lives in `projects/<name>/config.md` and is symlinked into `~/.whatsapp-channel/groups/<jid>/config.md` so the plugin reads it directly. `src/server.ts` is the only file that needs a deploy step (copy to plugin cache).

**Tech Stack:** zsh scripts, Python 3, TypeScript (server.ts), git

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `src/server.ts` | Copy from plugin cache — MCP server source of truth |
| Create | `scripts/deploy.sh` | Copy src/server.ts → plugin cache |
| Create | `scripts/link-groups.sh` | Setup symlink for a project's config.md |
| Move | `start-viko-agent.sh` → `scripts/start.sh` | Viko launcher |
| Move | `manage-groups.sh` → `scripts/manage-groups.sh` | Group management wrapper |
| Move | `manage-groups.py` → `tools/manage-groups.py` | Group management CLI |
| Create | `projects/mankop/config.md` | Personality (from existing ~/.whatsapp-channel/groups/120363409428298054@g.us/config.md) |
| Create | `projects/mankop/README.md` | Mankop project metadata |
| Create | `projects/luxso/config.md` | Personality (from existing ~/.whatsapp-channel/groups/120363424541097083@g.us/config.md) |
| Create | `projects/luxso/README.md` | Luxso project metadata |
| Create | `projects/forecastinn/config.md` | Personality template (no group yet) |
| Create | `projects/forecastinn/README.md` | Forecastinn project metadata |
| Create | `.claude/skills/manage-project.md` | Skill: add new project |
| Create | `.claude/skills/viko-status.md` | Skill: check all project status |
| Create | `.gitignore` | Ignore logs, .DS_Store, .env |
| Create | `README.md` | Viko Agent overview |
| Init | `.git/` | Local git repo |

---

## Task 1: Create directory structure

**Files:** (directories only)

- [ ] **Step 1: Create all new directories**

```bash
cd /Users/eksa/Projects/viko-agent
mkdir -p src scripts tools projects/mankop projects/luxso projects/forecastinn .claude/skills
```

- [ ] **Step 2: Verify**

```bash
ls -la /Users/eksa/Projects/viko-agent/
```

Expected: `src/`, `scripts/`, `tools/`, `projects/`, `.claude/` all present.

---

## Task 2: Copy server.ts to src/

**Files:**
- Create: `src/server.ts`

- [ ] **Step 1: Copy from plugin cache**

```bash
cp ~/.claude/plugins/cache/whatsapp-claude-plugin/whatsapp-claude-channel/0.8.0/server.ts \
   /Users/eksa/Projects/viko-agent/src/server.ts
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/eksa/Projects/viko-agent/src/server.ts
```

Expected: same line count as plugin cache (should be ~1875+ lines).

---

## Task 3: Move existing scripts to scripts/

**Files:**
- Move: `start-viko-agent.sh` → `scripts/start.sh`
- Move: `manage-groups.sh` → `scripts/manage-groups.sh`
- Move: `manage-groups.py` → `tools/manage-groups.py`

- [ ] **Step 1: Move files**

```bash
cd /Users/eksa/Projects/viko-agent
mv start-viko-agent.sh scripts/start.sh
mv manage-groups.sh scripts/manage-groups.sh
mv manage-groups.py tools/manage-groups.py
```

- [ ] **Step 2: Update path reference in manage-groups.sh** (it references `manage-groups.py` via `$VIKO_DIR`)

```bash
cat scripts/manage-groups.sh
```

Check that `python3 "$VIKO_DIR/manage-groups.py"` — update to `tools/manage-groups.py`:

```bash
cat > scripts/manage-groups.sh << 'EOF'
#!/bin/zsh
# manage-groups.sh — List & setup Viko in WhatsApp groups

WHATSAPP_DIR="$HOME/.whatsapp-channel"
VIKO_DIR="$(cd "$(dirname $0)/.." && pwd)"

python3 "$VIKO_DIR/tools/manage-groups.py" "$WHATSAPP_DIR"
EOF
chmod +x scripts/manage-groups.sh
```

- [ ] **Step 3: Ensure scripts are executable**

```bash
chmod +x scripts/start.sh scripts/manage-groups.sh
```

- [ ] **Step 4: Verify**

```bash
ls -la /Users/eksa/Projects/viko-agent/scripts/ /Users/eksa/Projects/viko-agent/tools/
```

Expected: `start.sh`, `manage-groups.sh` in scripts/; `manage-groups.py` in tools/.

---

## Task 4: Create deploy.sh and link-groups.sh

**Files:**
- Create: `scripts/deploy.sh`
- Create: `scripts/link-groups.sh`

- [ ] **Step 1: Write deploy.sh**

```bash
cat > /Users/eksa/Projects/viko-agent/scripts/deploy.sh << 'EOF'
#!/bin/zsh
set -e
PLUGIN_CACHE="$HOME/.claude/plugins/cache/whatsapp-claude-plugin/whatsapp-claude-channel/0.8.0"
SCRIPT_DIR="$(cd "$(dirname $0)" && pwd)"
SRC="$SCRIPT_DIR/../src/server.ts"

if [ ! -f "$SRC" ]; then
  echo "Error: $SRC not found" >&2
  exit 1
fi

cp "$SRC" "$PLUGIN_CACHE/server.ts"
echo "Deployed src/server.ts → $PLUGIN_CACHE/server.ts"
echo "Restart Claude Code to reload the MCP server."
EOF
chmod +x /Users/eksa/Projects/viko-agent/scripts/deploy.sh
```

- [ ] **Step 2: Write link-groups.sh**

```bash
cat > /Users/eksa/Projects/viko-agent/scripts/link-groups.sh << 'EOF'
#!/bin/zsh
# Usage: ./scripts/link-groups.sh <project-name> <group-jid>
# Example: ./scripts/link-groups.sh mankop 120363409428298054@g.us
set -e
PROJECT=$1
JID=$2

if [ -z "$PROJECT" ] || [ -z "$JID" ]; then
  echo "Usage: $0 <project-name> <group-jid>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname $0)" && pwd)"
VIKO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_SRC="$VIKO_DIR/projects/$PROJECT/config.md"
TARGET_DIR="$HOME/.whatsapp-channel/groups/$JID"
TARGET="$TARGET_DIR/config.md"

if [ ! -f "$CONFIG_SRC" ]; then
  echo "Error: $CONFIG_SRC not found. Create projects/$PROJECT/config.md first." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
ln -sf "$CONFIG_SRC" "$TARGET"
echo "Linked projects/$PROJECT/config.md → $TARGET"
EOF
chmod +x /Users/eksa/Projects/viko-agent/scripts/link-groups.sh
```

- [ ] **Step 3: Verify scripts are executable**

```bash
ls -la /Users/eksa/Projects/viko-agent/scripts/
```

Expected: `deploy.sh`, `link-groups.sh`, `manage-groups.sh`, `start.sh` all with `x` permission.

---

## Task 5: Setup mankop project

**Files:**
- Create: `projects/mankop/config.md` (from existing group config)
- Create: `projects/mankop/README.md`

- [ ] **Step 1: Copy existing config into projects/mankop/**

```bash
cp ~/.whatsapp-channel/groups/120363409428298054@g.us/config.md \
   /Users/eksa/Projects/viko-agent/projects/mankop/config.md
```

- [ ] **Step 2: Create README.md**

```bash
cat > /Users/eksa/Projects/viko-agent/projects/mankop/README.md << 'EOF'
# Mankop

- **Topic**: Koperasi project Mankop — PM, Senior Dev, QA, Customer Support, Business Analysis
- **Project path**: ~/Projects/mankop
- **WhatsApp group JID**: 120363409428298054@g.us
- **Symlink**: ~/.whatsapp-channel/groups/120363409428298054@g.us/config.md → projects/mankop/config.md
EOF
```

- [ ] **Step 3: Create symlink (replaces the file in ~/.whatsapp-channel with a symlink)**

```bash
cd /Users/eksa/Projects/viko-agent
./scripts/link-groups.sh mankop 120363409428298054@g.us
```

- [ ] **Step 4: Verify symlink is correct**

```bash
ls -la ~/.whatsapp-channel/groups/120363409428298054@g.us/config.md
```

Expected: symlink pointing to `.../viko-agent/projects/mankop/config.md`

```bash
diff ~/.whatsapp-channel/groups/120363409428298054@g.us/config.md \
     /Users/eksa/Projects/viko-agent/projects/mankop/config.md
```

Expected: no diff (same content via symlink).

---

## Task 6: Setup luxso project

**Files:**
- Create: `projects/luxso/config.md` (from existing group config)
- Create: `projects/luxso/README.md`

- [ ] **Step 1: Copy existing config into projects/luxso/**

```bash
cp ~/.whatsapp-channel/groups/120363424541097083@g.us/config.md \
   /Users/eksa/Projects/viko-agent/projects/luxso/config.md
```

- [ ] **Step 2: Create README.md**

```bash
cat > /Users/eksa/Projects/viko-agent/projects/luxso/README.md << 'EOF'
# Luxso

- **Topic**: Luxso Executive Dashboard — villa management & Luxso client project
- **Project path**: ~/Projects/forecastinn/clients/Luxso-executive-dashboard
- **WhatsApp group JID**: 120363424541097083@g.us
- **Symlink**: ~/.whatsapp-channel/groups/120363424541097083@g.us/config.md → projects/luxso/config.md
EOF
```

- [ ] **Step 3: Create symlink**

```bash
cd /Users/eksa/Projects/viko-agent
./scripts/link-groups.sh luxso 120363424541097083@g.us
```

- [ ] **Step 4: Verify symlink**

```bash
ls -la ~/.whatsapp-channel/groups/120363424541097083@g.us/config.md
```

Expected: symlink pointing to `.../viko-agent/projects/luxso/config.md`.

---

## Task 7: Setup forecastinn project

**Files:**
- Create: `projects/forecastinn/config.md`
- Create: `projects/forecastinn/README.md`

No WhatsApp group exists yet — create template config only, wire up symlink later when group is created.

- [ ] **Step 1: Create config.md template**

```bash
cat > /Users/eksa/Projects/viko-agent/projects/forecastinn/config.md << 'EOF'
# Soul

## Identity
Kamu adalah **Viko** — AI multi-role untuk project **Forecastinn**.
Nama kamu Viko. Ketika ada yang menyebut "viko", mereka memanggil kamu.

## Focus
Project ini adalah **Forecastinn** — aplikasi manajemen villa.
Project folder: ~/Projects/forecastinn

## Behavior
- Fokus pada topik Forecastinn app
- Bantu dengan coding, debugging, planning, dan review untuk project ini
- Gunakan bahasa yang sama dengan user (Indonesia/English)
EOF
```

- [ ] **Step 2: Create README.md**

```bash
cat > /Users/eksa/Projects/viko-agent/projects/forecastinn/README.md << 'EOF'
# Forecastinn

- **Topic**: Forecastinn app — aplikasi manajemen villa
- **Project path**: ~/Projects/forecastinn
- **WhatsApp group JID**: (belum ada — jalankan link-groups.sh setelah group dibuat)
- **Symlink**: Jalankan: `./scripts/link-groups.sh forecastinn <jid>@g.us`
EOF
```

- [ ] **Step 3: Verify files created**

```bash
ls /Users/eksa/Projects/viko-agent/projects/forecastinn/
```

Expected: `config.md`, `README.md`

---

## Task 8: Create .claude/skills/

**Files:**
- Create: `.claude/skills/manage-project.md`
- Create: `.claude/skills/viko-status.md`

- [ ] **Step 1: Write manage-project skill**

```bash
cat > /Users/eksa/Projects/viko-agent/.claude/skills/manage-project.md << 'EOF'
---
name: manage-project
description: Add or setup a new Viko project — creates project folder, config.md template, README.md, and wires up the symlink to the WhatsApp group.
---

Use when the user wants to add a new project to Viko or link an existing project to a WhatsApp group.

## Steps

1. Ask for: project name (slug, lowercase), WhatsApp group JID, project path, topic description
2. Create `projects/<name>/` directory
3. Create `projects/<name>/config.md` with personality template:
   ```
   # Soul
   ## Identity
   Kamu adalah **Viko** — AI multi-role untuk project **<Project Name>**.
   Nama kamu Viko.
   ## Focus
   Project ini adalah **<Project Name>** — <topic>.
   Project folder: <project-path>
   ## Behavior
   - Fokus pada topik project ini
   - Bantu dengan coding, debugging, planning, dan review
   - Gunakan bahasa yang sama dengan user
   ```
4. Create `projects/<name>/README.md` with metadata
5. Run: `./scripts/link-groups.sh <name> <jid>`
6. Confirm symlink is working with: `ls -la ~/.whatsapp-channel/groups/<jid>/config.md`
EOF
```

- [ ] **Step 2: Write viko-status skill**

```bash
cat > /Users/eksa/Projects/viko-agent/.claude/skills/viko-status.md << 'EOF'
---
name: viko-status
description: Check the status of all Viko projects — lists projects, verifies symlinks, and shows which groups are active.
---

Use when the user wants to see all Viko projects and their status.

## Steps

1. List all projects in `projects/`:
   ```bash
   ls /Users/eksa/Projects/viko-agent/projects/
   ```

2. For each project, check README.md for the JID and verify symlink:
   ```bash
   ls -la ~/.whatsapp-channel/groups/<jid>/config.md
   ```

3. Report for each project:
   - Project name
   - Topic (from README.md)
   - Group JID
   - Symlink status: ✓ linked / ✗ broken / — no group yet

4. Check if viko-agent tmux session is running:
   ```bash
   tmux ls 2>/dev/null | grep viko-agent
   ```

5. Show summary table to user.
EOF
```

- [ ] **Step 3: Verify**

```bash
ls /Users/eksa/Projects/viko-agent/.claude/skills/
```

Expected: `manage-project.md`, `viko-status.md`

---

## Task 9: Add .gitignore and README.md

**Files:**
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Write .gitignore**

```bash
cat > /Users/eksa/Projects/viko-agent/.gitignore << 'EOF'
# Logs
*.log

# macOS
.DS_Store
**/.DS_Store

# Runtime / temp
*.tmp
.env
EOF
```

- [ ] **Step 2: Remove any existing .DS_Store files**

```bash
find /Users/eksa/Projects/viko-agent -name ".DS_Store" -delete
```

- [ ] **Step 3: Write root README.md**

```bash
cat > /Users/eksa/Projects/viko-agent/README.md << 'EOF'
# Viko Agent

WhatsApp AI assistant and developer agent running on Claude Code. One Claude instance handles multiple WhatsApp groups, each mapped to a specific project with custom personality and context.

## Quick Start

```zsh
./scripts/start.sh       # Launch Viko in tmux session
./scripts/deploy.sh      # Deploy src/server.ts → plugin cache (after editing)
```

## Projects

| Project | Topic | Group JID |
|---------|-------|-----------|
| mankop | Koperasi Mankop | 120363409428298054@g.us |
| luxso | Luxso Executive Dashboard | 120363424541097083@g.us |
| forecastinn | Forecastinn villa app | (belum ada group) |

## Adding a New Project

```zsh
# 1. Create project folder + config
mkdir -p projects/<name>
# edit projects/<name>/config.md and projects/<name>/README.md

# 2. Link to WhatsApp group
./scripts/link-groups.sh <name> <jid>@g.us
```

Or use the Claude skill: `/manage-project`

## Structure

```
viko-agent/
├── .claude/skills/      ← custom Claude skills
├── projects/            ← per-project personality configs (symlinked to plugin)
├── src/server.ts        ← MCP WhatsApp server source
├── scripts/             ← deploy, start, manage
└── tools/               ← manage-groups.py CLI
```

## Editing the MCP Server

```zsh
# 1. Edit src/server.ts
# 2. Deploy to plugin cache
./scripts/deploy.sh
# 3. Restart Claude Code
```
EOF
```

---

## Task 10: Init git and commit

- [ ] **Step 1: Init git**

```bash
cd /Users/eksa/Projects/viko-agent
git init
```

Expected: `Initialized empty Git repository in .../viko-agent/.git/`

- [ ] **Step 2: Verify .gitignore is working (symlinks should be tracked, not followed)**

```bash
git status
```

Check that `projects/mankop/config.md` and `projects/luxso/config.md` appear as new files (the symlinks themselves are tracked, not the content they point to — that is the correct behavior).

- [ ] **Step 3: Stage all files**

```bash
cd /Users/eksa/Projects/viko-agent
git add \
  src/server.ts \
  scripts/deploy.sh \
  scripts/link-groups.sh \
  scripts/start.sh \
  scripts/manage-groups.sh \
  tools/manage-groups.py \
  projects/ \
  .claude/ \
  .gitignore \
  README.md \
  docs/
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
init: setup viko-agent project structure

- src/server.ts as source of truth for WhatsApp MCP server
- projects/ with per-group personality configs (symlinked to plugin)
- scripts/ for deploy, start, group linking
- .claude/skills/ for manage-project and viko-status
- root README and .gitignore
EOF
)"
```

- [ ] **Step 5: Verify clean state**

```bash
git status
```

Expected: `nothing to commit, working tree clean`

---

## Self-Review

**Spec coverage:**
- [x] Migrate existing files → Task 3
- [x] Create deploy.sh, link-groups.sh → Task 4
- [x] Copy server.ts → Task 2
- [x] Create project folders (mankop, luxso, forecastinn) → Tasks 5, 6, 7
- [x] Setup symlinks → Tasks 5, 6 (forecastinn has no group yet — documented)
- [x] Create .claude/skills/ → Task 8
- [x] .gitignore + README → Task 9
- [x] Init git + commit → Task 10
- [x] Delete .DS_Store → Task 9 Step 2

**Placeholders:** None — all scripts contain exact content, all paths are absolute.

**Type consistency:** N/A — no code types involved, only shell scripts and markdown.
