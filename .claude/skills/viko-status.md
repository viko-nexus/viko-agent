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
