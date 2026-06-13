# Project Detection Rules

Viko maintains an "active project" state across sessions. This determines which project
context is loaded and which codebase Viko works against.

## Detection Priority (highest to lowest)

### 1. Explicit Mention
Eksa names a project in the message.

- Example: "cek error di forecast-inn" → switch to `forecast-inn`
- Viko confirms the switch once: "Switching ke forecast-inn."
- Subsequent messages continue in the same project until changed

### 2. Conversation Context
No explicit mention, but prior conversation referenced a project.

- Viko continues with the last active project
- No confirmation message needed

### 3. Auto-Detect
No context available (new session or ambiguous message).

- Viko infers from keywords: project name, tech stack, team member names
- Viko confirms before executing: "Ini untuk [project]?"
- If inference is too uncertain, Viko asks directly: "Project mana yang dimaksud?"

## Session Persistence

- Active project persists across sessions (stored in runtime state / Docker volume)
- At the start of each new session, Viko announces:
  "Melanjutkan dari [project]. Ganti project? Ketik nama project lain."
- If no prior session exists, Viko asks: "Mau mulai dari project mana?"

## Available Projects

| Slug | Description |
|------|-------------|
| `viko-agent` | Viko's own configuration repo — identity, rules, skills, project contexts |
| `forecast-inn` | ForecastInn hospitality platform |
| `forecast-crm` | ForecastInn CRM |
| `luxso` | Luxso Executive Dashboard |
| `mankop` | Mankop (Koperasi Multi Pihak) |

See `projects/<slug>/context.md` for full details on each project.
