# viko-agent

Konfigurasi dan patch untuk **Viko** — AI developer assistant berbasis [Hermes Agent](https://hermes-agent.nousresearch.com) yang aktif di WhatsApp dan Google Chat.

## Arsitektur

```
WhatsApp / Google Chat
        ↓ mention "viko"
Hermes Gateway (launchd service)
        ↓ model: Gemini Flash (gratis) → fallback: Groq Llama 3.3
SOUL.md → Viko personality + RBAC
        ↓ viko exec: / viko task:
claude --print (Claude Max subscription)
```

## Struktur Repo

```
viko-agent/
├── patches/
│   ├── whatsapp-bridge.js     ← patch group support di self-chat mode
│   └── apply-run-py.py        ← patch notifikasi sistem ke Indonesian
├── hooks/
│   └── viko-startup/          ← notifikasi WA saat Viko online
├── scripts/
│   ├── hermes.sh              ← install / update Hermes
│   └── post-update.sh         ← re-apply patches setelah hermes update
└── projects/                  ← referensi config per project (archived)
```

## Setup

```bash
# Install Hermes + desktop app
bash scripts/hermes.sh

# Setelah hermes update, re-apply patches
bash scripts/post-update.sh
```

## Config Utama

| File | Lokasi | Isi |
|------|--------|-----|
| SOUL.md | `~/.hermes/SOUL.md` | Personality Viko + RBAC |
| config.yaml | `~/.hermes/config.yaml` | Model, gateway, session settings |
| .env | `~/.hermes/.env` | API keys, WA config |

## Projects

Setiap project punya `AGENTS.md` di folder project-nya (auto-load oleh Hermes desktop):

| Project | Path | AGENTS.md |
|---------|------|-----------|
| ForecastInn | `~/Projects/forecastinn/forecast-inn` | ✅ |
| ForecastCRM | `~/Projects/forecastinn/forecast-crm` | ✅ |
| Luxso Dashboard | `~/Projects/forecastinn/clients/Luxso-executive-dashboard` | ✅ |
| Mankop | `~/Projects/mankop/mankop-apps` | ✅ |

Di Hermes desktop: navigasi ke folder project → AGENTS.md auto-load sebagai konteks.

## Patches

Custom patches yang diterapkan ke Hermes installation:

1. **whatsapp-bridge.js** — enable group messages di self-chat mode
2. **apply-run-py.py** — translate system notifications ke Indonesian

Jalankan `bash scripts/post-update.sh` setelah setiap `hermes update`.
