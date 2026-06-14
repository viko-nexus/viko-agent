# 9router Setup

LLM gateway with multi-provider fallback routing. Runs at `http://localhost:20128`.

## Combos

Combos define ordered fallback chains. Hermes automatically selects the right
combo per message via the **model-router patch** (`patches/patch-model-router.py`).

| Combo | Use Case | Models (in order) |
|-------|----------|-------------------|
| `viko-chat` | Casual chat, simple questions | haiku → groq/llama-3.3 → groq/maverick |
| `viko-code` | Code, debug, analysis, data | sonnet → groq/llama-3.3 → groq/maverick |
| `viko-combo` | Fallback / manual override | groq/llama-3.3 → groq/maverick → sonnet → haiku |

**Routing logic**: keywords like `debug`, `fix`, `code`, `analisa`, `deploy`, `api`
→ `viko-code` (sonnet). Everything else → `viko-chat` (haiku).

Round Robin is **OFF** on all combos — fallback/sequential mode.

## Auto-Initialization

On every `docker compose up`, the `9router-init` service runs automatically:
```bash
docker compose --profile full up -d
# → 9router starts → 9router-init runs → combos created/updated → exits
```

To run manually (e.g., after a data wipe):
```bash
python3 scripts/init-9router.py
```

## Provider API Keys

API keys are stored in `data/9router/db/data.sqlite` (gitignored).
After a fresh install or data wipe, re-add keys via the dashboard:

1. Open `http://localhost:20128`
2. **Providers → Claude Code** → connect Anthropic account (OAuth)
3. **Providers → Groq** → add API key from console.groq.com

The `viko-hermes` API key for 9router is in `.env` as `OPENAI_API_KEY`.
Re-create it at: **Endpoint → API Keys → Create Key**.

## Caveman Compression (Token Saver)

To enable ~65% fewer output tokens:
1. Open `http://localhost:20128` → **Endpoint**
2. Toggle **"Compress LLM output (Caveman)"** → ON

Not automated — enable manually after setup.

## Key Endpoints

| Path | What |
|------|------|
| `/v1/chat/completions` | Main LLM (OpenAI-compatible) |
| `/v1/models` | List available models |
| `/v1/images/generations` | Image generation |
| `/v1/audio/speech` | Text-to-speech |
| `/v1/audio/transcriptions` | Speech-to-text |
