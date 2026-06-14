# Project Detection Rules

Viko maintains an "active project" state across sessions. This determines which project
context is loaded and which codebase Viko works against.

## Detection Priority (highest to lowest)

### 1. Explicit Mention
Eksa names a project in the message.

- Example: "check error in forecast-inn" → switch to `forecast-inn`
- Viko confirms the switch once: "Switching to forecast-inn."
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

| Slug | Description |
|------|-------------|
| `viko-agent` | Viko's own configuration repo — identity, rules, skills, project contexts |
| `forecast-inn` | ForecastInn hospitality platform |
| `forecast-crm` | ForecastInn CRM |
| `luxso` | Luxso Executive Dashboard |
| `mankop` | Mankop (Koperasi Multi Pihak) |

See `projects/<slug>/context.md` for full details on each project.
