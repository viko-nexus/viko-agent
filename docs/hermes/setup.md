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
| `web.extract_backend` | — | `https://r.jina.ai/` | Free URL fetcher (no API key) |
| `auxiliary.vision.model` | — | `cc/claude-sonnet-4-6` | Dedicated vision model |
| `whatsapp.require_mention` | — | `true` | Silent in groups unless @mentioned |
| `whatsapp.channel_prompts` | `120363409428298054@g.us` | Mankop group context | Auto-loads project context |
| `display.language` | — | `id` | Indonesian UI labels |

## Patches (Applied at Build Time)

Patches in `patches/` are applied when building the Docker image (`docker compose build hermes`).
They persist across restarts — only need rebuild to update.

| Patch | What |
|-------|------|
| `whatsapp-bridge.js` | WhatsApp integration bridge |
| `indonesian-locale.py` | Translates system notifications to Indonesian |
| `patch-ssh-guard.py` | SSH security hardening |
| `patch-model-router.py` | Routes messages to viko-chat or viko-code based on content |

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

## Cron Jobs

Cron definitions: `data/hermes/cron/jobs.json`

| Job | Schedule | Type |
|-----|----------|------|
| `viko-self-monitor-01` | Every 2 hours | LLM agent (reads logs, sends WA if errors) |
| `cleanup-media-files-01` | Daily 3am | No-agent script (deletes media >30 days) |

Cleanup script: `data/hermes/scripts/cleanup-media.sh`

## WhatsApp Groups

| Group | Chat ID | Project |
|-------|---------|---------|
| 2a. PRODUK SAAS MANKOP | `120363409428298054@g.us` | mankop |

## Re-pair WhatsApp

If `data/hermes/platforms/whatsapp/session/creds.json` is deleted:
```bash
docker exec -u root viko-hermes chown -R hermes:hermes /opt/hermes/scripts/whatsapp-bridge
docker exec -it -u hermes viko-hermes hermes whatsapp
```
Scan QR with the bot's dedicated number.
