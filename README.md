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
