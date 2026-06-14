# viko-agent — Self-Modification Playbook

Step-by-step guide for each type of change. Always read `context.md` first.

---

## 1. Change Persona / Communication Style (Tier 2)

Target: `data/hermes/SOUL.md` — takes effect immediately

```
1. Read ~/Projects/viko-agent/data/hermes/SOUL.md
2. Identify the section to change
3. Edit the file directly
4. Notify Eksa: "Done — updated SOUL.md: [what changed]"
5. Change is effective on the next message (no restart needed)
```

---

## 2. Update / Add a Skill (Tier 2)

Target: `skills/<name>.md` — takes effect next session

```
1. Read relevant skills in ~/Projects/viko-agent/skills/
2. Edit existing file or create a new one
3. If new file: add entry to AGENTS.md under ## Skills
4. Git commit (Tier 3 — inform or get approval from Eksa)
5. Notify: "Done — updated skills/debugging.md: [what changed]"
```

---

## 3. Update Project Context (Tier 2)

Target: `projects/<slug>/context.md` or `steps.md`

```
1. Read the context file to update
2. Edit directly — paths, team, notes, SOP
3. Notify: "Done — updated projects/forecast-inn/context.md: [what changed]"
4. Note: "Change takes effect next session"
```

---

## 4. Change Rules / Authorization (Tier 3)

Target: `rules/*.md` — **requires Eksa's approval**

```
1. Draft the desired change
2. Send WA approval request to Eksa (see rules/approval-format.md):
   "[Action] Update rules/authorization.md — [description of change]
    [Risk]   Changes how Viko decides what needs approval
    [Choice] Yes / No / Postpone"
3. Wait for approval
4. After approval: edit file, git commit, notify
```

---

## 5. Change Core Identity (Tier 3)

Target: `soul/identity.md` — **requires Eksa's approval**

```
1. Draft the identity change
2. Send approval request to Eksa
3. After approval: edit soul/identity.md
4. Always sync data/hermes/SOUL.md immediately after:
   - soul/identity.md is the canonical source (English, git-tracked)
   - SOUL.md is the runtime file Hermes reads every message (also English)
   - Changes in soul/identity.md are NOT active until SOUL.md is updated
   - Keep SOUL.md in English; the language instruction inside the file tells Viko to respond in Indonesian
5. Git commit + notify
```

---

## 6. Change Config (Model, Provider) (Tier 3)

Target: `data/hermes/config.yaml`

```
1. Read current config: ~/Projects/viko-agent/data/hermes/config.yaml
2. Send approval request to Eksa
3. After approval: edit config.yaml
4. Restart gateway: /command/s6-svc -t /run/service/gateway-default
5. Verify: check logs that LLM provider is active
6. Notify: "Done — config.yaml updated, gateway restarted"
```

---

## 7. Change a Patch or Dockerfile (Tier 3 + Rebuild)

Target: `patches/*.py`, `patches/*.js`, `Dockerfile.hermes`

```
1. Identify which patch needs changing
2. Send approval request to Eksa — include:
   - File to change
   - What changes and why
   - Estimated downtime (typically 5-10 min rebuild)
3. After approval: edit file in ~/Projects/viko-agent/patches/
4. Ask Eksa to rebuild:
   "Please run: docker compose build hermes && docker compose --profile full up -d"
5. After coming back online: verify the change works
```

---

## 8. Add a New Project (Tier 2)

```
1. Create directory: projects/<slug>/
2. Create context.md using standard format (see projects/forecast-inn/context.md)
3. Create an empty steps.md (fill in as patterns are learned)
4. Add entry to AGENTS.md (## Active Projects table)
5. Add entry to rules/project-detection.md (## Available Projects table)
6. Notify Eksa: "Done — added project context for [slug]"
```

---

## Rollback

If a Layer 2 change (repo file) was wrong:

```bash
# View recent changes
git -C ~/Projects/viko-agent log --oneline -5

# Revert a specific file
git -C ~/Projects/viko-agent checkout HEAD -- rules/authorization.md

# Revert last commit (careful)
git -C ~/Projects/viko-agent revert HEAD
```

For SOUL.md (Layer 1): read the file and manually edit, or copy from `soul/identity.md`.
