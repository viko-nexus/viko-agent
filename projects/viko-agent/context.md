# Project: viko-agent

## Overview

`viko-agent` is Viko's own home — the repo that defines Viko's identity, rules, skills, and
project context. Viko is expected to read and modify this repo to improve itself, subject to
the authorization tiers below.

## Paths

All paths are identical inside the container and on the host (bind-mounted at the same path).

| Resource | Path |
|----------|------|
| Repo root | `~/Projects/viko-agent` |
| Runtime data | `~/Projects/viko-agent/data/hermes` |
| SOUL.md (active persona) | `~/Projects/viko-agent/data/hermes/SOUL.md` |
| Config | `~/Projects/viko-agent/data/hermes/config.yaml` |
| Identity canon | `~/Projects/viko-agent/soul/identity.md` |
| Rules | `~/Projects/viko-agent/rules/*.md` |
| Skills | `~/Projects/viko-agent/skills/*.md` |
| Project contexts | `~/Projects/viko-agent/projects/<slug>/` |
| Patches | `~/Projects/viko-agent/patches/` |

## Self-Modification Architecture

### Layer 1 — Runtime (`data/hermes/`, writable)
Read directly by Hermes every session. Changes take effect immediately (no restart needed):

| File | Purpose |
|------|---------|
| `SOUL.md` | Active persona — tone, name, communication style |
| `config.yaml` | LLM model, provider, display language |

### Layer 2 — Source of Truth (repo files, writable via bind mount)
Loaded via `AGENTS.md` every session. Changes take effect in the next session:

| Path | Purpose |
|------|---------|
| `soul/identity.md` | Identity canon — roles, core values |
| `rules/*.md` | Behavior rules (authorization, approval, timeouts) |
| `skills/*.md` | Domain knowledge per lifecycle stage |
| `projects/<slug>/context.md` | Per-project context |
| `projects/<slug>/steps.md` | Per-project SOP |

### Layer 3 — Build-time (`patches/`, `Dockerfile.hermes`)
Applied during `docker compose build hermes`. Changes require a **full rebuild + redeploy**:

| File | Purpose |
|------|---------|
| `patches/whatsapp-bridge.js` | Custom WhatsApp bridge |
| `patches/indonesian-locale.py` | Hermes locale overrides |
| `patches/apply-agent-msgs.py` | Agent message handling patch |
| `Dockerfile.hermes` | Image build definition |

## Authorization for Self-Modification

| Change | Tier | Reason |
|--------|------|--------|
| Edit `data/hermes/SOUL.md` (tone, persona) | Tier 2 | Safe, instant effect, reversible |
| Edit `skills/*.md` (domain knowledge) | Tier 2 | Low risk, git-reversible |
| Edit `projects/*/context.md` or `steps.md` | Tier 2 | Factual updates, git-reversible |
| Add new skill file | Tier 2 | Additive only |
| Edit `soul/identity.md` (core identity) | Tier 3 | Changes who Viko is — needs approval |
| Edit `rules/*.md` (authorization, approval) | Tier 3 | Changes how Viko operates |
| Edit `data/hermes/config.yaml` (model/provider) | Tier 3 | Can break LLM routing |
| Edit `patches/` | Tier 3 | Requires rebuild, high risk |
| Git commit to viko-agent | Tier 3 | Permanent in history |
| `docker compose build hermes` | Tier 3 | Rebuild takes time, causes downtime |

## Git Workflow for Self-Modification

```bash
# Stage and commit changes
git -C ~/Projects/viko-agent add skills/new-skill.md
git -C ~/Projects/viko-agent commit -m "feat: add skill X because Y"
```

> Pushing to remote requires credentials — Eksa handles the push to GitHub.

## Session Init

Before working on any self-modification task:
1. Read the file to be changed first
2. Identify whether Tier 2 or Tier 3 applies
3. Tier 3: send approval request to Eksa first
4. Tier 2: execute, then notify

See `projects/viko-agent/steps.md` for step-by-step guides per change type.

## Team

| Name | Role |
|------|------|
| Eksa | Owner — sole approver for Tier 3 actions |
| Viko | Self-maintainer — can edit Layer 1 & 2 within authorization rules |

## Notes

- All `.md` files in this repo must be written in **English** — including any sections you add
- `SOUL.md` is also in English — the communication language (Indonesian) is configured inside the file
- `data/hermes/` files other than `SOUL.md` and `config.yaml` should not be touched without Eksa
- When in doubt about the tier: **ask first**
- After editing Layer 2 files, inform Eksa that changes take effect in the next session
- After editing `SOUL.md` (Layer 1), changes are immediate — no restart needed
