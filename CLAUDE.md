# viko-agent

Config dan patch untuk **Viko** — AI developer assistant berbasis Hermes Agent.

## Struktur Repo

```
viko-agent/
├── patches/
│   ├── whatsapp-bridge.js     ← patch group support (self-chat mode)
│   └── apply-run-py.py        ← patch notifikasi sistem ke Indonesian
├── hooks/
│   └── viko-startup/          ← notifikasi WA saat Viko online
├── scripts/
│   ├── hermes.sh              ← install / update Hermes + desktop app
│   └── post-update.sh         ← re-apply patches setelah hermes update
└── projects/                  ← archived config lama (referensi saja)
```

## Config Hermes (di luar repo)

| File | Path | Isi |
|------|------|-----|
| SOUL.md | `~/.hermes/SOUL.md` | Personality Viko + RBAC |
| config.yaml | `~/.hermes/config.yaml` | Model, gateway, session |
| .env | `~/.hermes/.env` | API keys, WA/GChat config |
| hooks/ | `~/.hermes/hooks/` | Event hooks |

## Projects (AGENTS.md per folder)

| Project | Path |
|---------|------|
| ForecastInn | `~/Projects/forecastinn/forecast-inn/AGENTS.md` |
| ForecastCRM | `~/Projects/forecastinn/forecast-crm/AGENTS.md` |
| Luxso Dashboard | `~/Projects/forecastinn/clients/Luxso-executive-dashboard/AGENTS.md` |
| Mankop | `~/Projects/mankop/mankop-apps/AGENTS.md` |

## Workflow

### Setup mesin baru
```bash
bash scripts/hermes.sh
```

### Setelah hermes update
```bash
bash scripts/post-update.sh
```

### Tambah project baru
```bash
# Buat AGENTS.md di folder project
cat > ~/Projects/<nama>/AGENTS.md << 'EOF'
# Nama Project
...
EOF
```

### Restart gateway
```bash
launchctl stop ai.hermes.gateway && sleep 2 && launchctl start ai.hermes.gateway
```

## Model Stack

```
Primary:  Gemini 3 Flash Preview (Google OAuth, gratis)
Fallback: Groq Llama 3.3 70B (gratis)
Executor: claude --print (Max subscription, via terminal tool)
```
