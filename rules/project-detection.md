# Project Detection Rules

Viko maintains an "active project" state across sessions. This determines which project
context is loaded and which codebase Viko works against.

## Detection Priority (highest to lowest)

### 0. Group Binding (deterministic — highest, overrides the rest)
The project is decided by the GROUP the message comes from, not by guessing:
- **Project container**: `VIKO_PROJECT_SLUG` IS the active project (hard-locked; only that project is even readable).
- **Admin context**: map the conversation's group JID (`chat_id`) → project via `data/bridge/routing.json`. Registered JID → that project. Unregistered group → not onboarded; do NOT fall back to another project or list the catalog (see `authorization.md` → Cross-Project Scoping).

Only when there is genuinely no group binding (e.g. the owner's DM with no prior context) fall through to the priorities below.

### 1. Explicit Mention
Eksa names a project in the message.

- Example: "check error in <project-name>" → switch to that project
- Viko confirms the switch once: "Switching to <project-name>."
- Subsequent messages continue in the same project until changed

### 2. Conversation Context
No explicit mention, but prior conversation referenced a project.

- Viko continues with the last active project
- No confirmation message needed

### 3. Auto-Detect
No context available (new session or ambiguous message).

- Viko infers from keywords: project name, tech stack, team member names
- Viko confirms before executing: "Is this for [project]?"
- If inference is too uncertain, Viko asks directly: "Which project do you mean?"

## Session Persistence

- Active project persists across sessions (stored in runtime state / Docker volume)
- At the start of each new session, Viko announces:
  "Continuing from [project]. Switch project? Type another project name."
- If no prior session exists, Viko asks: "Which project do you want to start with?"

## Available Projects

Projects are dynamic — each user maintains their own list under `projects/` in the viko-agent repo.
To discover available projects, list the directory:

```bash
ls projects/
```

⚠️ **Owner-only.** Listing the full catalog is allowed only for the owner in the admin context.
A `[READ-ONLY MEMBER]` or a project-specific group must never enumerate other projects — scope
strictly to the group's own project (see `authorization.md` → Cross-Project Scoping).

Each folder with a `context.md` is an available project. Load `projects/<slug>/context.md`
for full details on stack, paths, server, and team.

## Creating a New Project

When Eksa asks to create a new project, Viko does two things:

### 1. Create the Viko config (in viko-agent repo)

Create these files inside the `viko-agent` repo:

```
projects/<slug>/
  context.md   ← team, stack, server details, session init instructions
  steps.md     ← project-specific steps Viko will maintain over time
```

Template for `context.md`:
```markdown
# Project: <Name>

| Field | Value |
|-------|-------|
| Slug | `<slug>` |
| Stack | <tech stack> |
| App Path | `$VIKO_PROJECTS_ROOT/<slug>/` |
| Server | `<server-alias>` |

## Team
- Eksa (lead)

## Session Init
Load this file. Active project: <slug>.
```

Template for `steps.md`:
```markdown
# Steps: <Name>

## Setup
<!-- Viko fills this in as the project evolves -->
```

Then add the project to the Available Projects table above.

### 2. Scaffold the app code (in projects root)

App code lives **outside** the viko-agent repo, in the user's projects root.
The location comes from the `VIKO_PROJECTS_ROOT` environment variable.

Before creating any files, **confirm with Eksa**:
> "I'll scaffold the app at `$VIKO_PROJECTS_ROOT/<slug>/`. Is that the right location?"

Do not hardcode any absolute path (e.g. `/home/user/...`) in context.md — use `$VIKO_PROJECTS_ROOT/<slug>/`
so the config stays portable across machines and users.

## Onboarding an Existing Project

When the user says something like *"buat context untuk project X"* or *"tambah project X ke viko"*:

### Step 1 — Validate the project folder exists

```bash
ls ~/Projects/<slug>/
```

If the folder **does not exist**:
> ⚠️ "Folder `~/Projects/<slug>/` tidak ditemukan. Apakah path-nya berbeda? Tolong konfirmasi lokasi project-nya."

Stop here. Do not create any files until Eksa confirms the correct path.

### Step 2 — Scan the codebase

Read enough to understand the project:

```bash
# Structure overview
find ~/Projects/<slug>/ -maxdepth 3 -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*'

# Tech stack signals
cat ~/Projects/<slug>/package.json 2>/dev/null
cat ~/Projects/<slug>/requirements.txt 2>/dev/null
cat ~/Projects/<slug>/go.mod 2>/dev/null
cat ~/Projects/<slug>/Dockerfile 2>/dev/null

# Project description
cat ~/Projects/<slug>/README.md 2>/dev/null | head -60
```

### Step 3 — Generate context.md

Based on the scan, create `projects/<slug>/context.md` with:
- Stack and key dependencies (inferred from package.json / requirements.txt / Dockerfile)
- App path (always `~/Projects/<slug>/` — never absolute)
- Folder structure summary (main dirs only)
- Blank sections for Server and Team (ask Eksa to fill if unknown)

Also create `projects/<slug>/steps.md` (empty template).

### Step 4 — Confirm with Eksa

Show a summary of what was found and what was written:
> "✅ Context dibuat untuk `<slug>`. Stack: <X>. Path: `~/Projects/<slug>/`. Cek `projects/<slug>/context.md` dan lengkapi bagian Server/Team jika perlu."

Then add the project to the Available Projects table in this file.

## Path Validation on Every Session Start

When switching to or loading any project, **always verify the app path exists** before doing any file or terminal work:

```bash
ls <app_path>/ 2>/dev/null || echo "NOT_FOUND"
```

If not found:
> ⚠️ "Path `<app_path>` tidak ditemukan di sistem ini. Kemungkinan path berbeda di mesin ini atau project belum di-clone. Konfirmasi path yang benar?"

Do not attempt to read files, run commands, or scaffold anything until the path is confirmed.
