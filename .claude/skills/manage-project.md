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
