# Hermes Setup

AI orchestrator (brain) running at port 9119. Built from `Dockerfile.hermes`.

## Critical config.yaml Settings

`data/hermes/config.yaml` is gitignored. After a data wipe, Hermes creates
a fresh default. Run the init script to re-apply critical settings:

```bash
# 1. Start Hermes once so it creates default config.yaml
docker compose --profile full up -d hermes

# 2. Apply critical settings
python3 scripts/init-hermes-config.py

# 3. Restart to apply
docker compose --profile full up -d --force-recreate hermes
```

### Settings Applied by init-hermes-config.py

| Section | Key | Value | Why |
|---------|-----|-------|-----|
| `model.default` | — | `viko-combo` | Routes through 9router combo |
| `model.provider` | — | `openai` | 9router is OpenAI-compatible |
| `web.extract_backend` | — | `https://r.jina.ai/` | Free URL fetcher, no API key needed |
| `auxiliary.vision.model` | — | `cc/claude-sonnet-4-6` | Dedicated vision model via 9router |
| `auxiliary.compression.model` | — | `cc/claude-haiku-4-5-20251001` | Cheaper context compression |
| `terminal.cwd` | — | `$VIKO_PROJECTS_ROOT` | Terminal starts in projects root |
| `timezone` | — | `Asia/Makassar` | Correct local time for cron (WITA, UTC+8) |
| `skills.external_dirs` | — | `[<repo>/skills]` | Exposes skills as `/skill-name` slash commands |
| `skills.guard_agent_created` | — | `true` | Review before saving AI-generated skills |
| `whatsapp.require_mention` | — | `true` | Silent in groups unless @mentioned |
| `whatsapp.unauthorized_dm_behavior` | — | `ignore` | Ignore DMs from unknown numbers |
| `whatsapp.channel_prompts` | per group ID | project context prompt | Auto-loads project on group message |
| `kanban.auto_decompose` | — | `false` | Manual task control, no auto-split |
| `kanban.max_in_progress_per_profile` | — | `1` | One active task at a time |
| `display.language` | — | `id` | Indonesian UI labels |
| `display.runtime_footer.enabled` | — | `false` | Footer disabled (was: model + context %) |

## Patches (Applied at Build Time)

Patches in `patches/` are applied when building the Docker image (`docker compose build hermes`).
They persist across restarts — only need rebuild to update.

| Patch | What |
|-------|------|
| `whatsapp-bridge.js` | WhatsApp integration bridge |
| `apply-run-py.py` | Applies run.py modifications (base patch) |
| `apply-agent-msgs.py` | Agent message handling improvements |
| `patch-ssh-guard.py` | Narrows SSH threat pattern — allows legitimate SSH, blocks key exfiltration |
| `patch-model-router.py` | Routes messages to `viko-chat` or `viko-code` based on content keywords |

## Model Routing (patch-model-router.py)

Each incoming message is classified before the LLM is called:

```
Message → keyword check → select combo → LLM called

"halo, gimana kabar?"       → viko-chat  → Claude Haiku (fast, cheap)
"debug error di controller" → viko-code  → Claude Sonnet (smarter)
"analisa data penjualan"    → viko-code  → Claude Sonnet
```

**Keywords that trigger viko-code**: `debug`, `fix`, `bug`, `error`, `code`,
`function`, `implement`, `analyze`, `analisa`, `deploy`, `database`, `query`,
`sql`, `api`, `test`, `script`, `refactor`, `optimize`, `review`, `architecture`,
`migration`, `schema`, `component`, `endpoint`, and Indonesian equivalents.

Manual `/model` switches are preserved — the patch only fires when no
user-initiated override is active. Resets on `/new` or `/reset`.

## Skills as Slash Commands

With `skills.external_dirs` pointing to `<repo>/skills`, Viko exposes each skill
file as a slash command in WhatsApp:

| Slash Command | File |
|---------------|------|
| `/debugging` | `skills/debugging.md` |
| `/deployment` | `skills/deployment.md` |
| `/planning` | `skills/planning.md` |
| `/testing` | `skills/testing.md` |
| `/monitoring` | `skills/monitoring.md` |
| `/self-monitoring` | `skills/self-monitoring.md` |
| `/web-research` | `skills/web-research.md` |

## Cron Jobs

Cron definitions: `data/hermes/cron/jobs.json`

| Job | Schedule | Type |
|-----|----------|------|
| `viko-self-monitor-01` | Every 2 hours | LLM agent (reads logs, sends WA if errors found) |
| `cleanup-media-files-01` | Daily 3am WITA | No-agent script (deletes media >30 days) |

Cleanup script: `data/hermes/scripts/cleanup-media.sh`

## WhatsApp Groups

Group-specific prompts are configured in `whatsapp.channel_prompts` (in `config.yaml`
and restored by `init-hermes-config.py`). Each group ID maps to a context injection
that tells Viko which project is active in that group.

To add a new group:
1. Get the group's chat ID (send a message to Viko in the group, check logs)
2. Add to `init-hermes-config.py` under `DESIRED["whatsapp"]["channel_prompts"]`
3. Run `python3 scripts/init-hermes-config.py` and restart Hermes

## Re-pair WhatsApp

If `data/hermes/platforms/whatsapp/session/creds.json` is deleted:
```bash
docker exec -u root viko-hermes chown -R hermes:hermes /opt/hermes/scripts/whatsapp-bridge
docker exec -it -u hermes viko-hermes hermes whatsapp
```
Scan QR with the bot's dedicated number.
