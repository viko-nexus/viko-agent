# Project: ForecastInn

## Overview

ForecastInn — hospitality management platform.

## Paths

| Resource | Path |
|----------|------|
| App root | `~/Projects/forecastinn/forecast-inn` |
| Docs | `~/Projects/forecastinn/forecast-inn/docs/` |
| AGENTS.md | `~/Projects/forecastinn/forecast-inn/AGENTS.md` |

## Team

| Name | Role |
|------|------|
| Eksa | Owner (Viko), developer |
| Andi | Product owner (ForecastInn) |
| Deden | QA |
| Faris | QA |

## Session Init

Before answering any technical question:
1. Read `README.md` at project root
2. Check `docs/` for relevant documentation
3. Never answer from memory alone — always read actual files

## Response Triggers

- Respond when "viko" is mentioned in the ForecastInn group chat
- Anyone can ask questions — only Eksa can authorize execution

## Production Server Access

Use the MCP tool — do not use raw SSH commands:

```
ssh_exec(project="forecastinn", command="...")
```

Examples:
- `ssh_exec(project="forecastinn", command="docker ps")`
- `ssh_exec(project="forecastinn", command="ls ~/forecastinn/")`
- `ssh_exec(project="forecastinn", command="docker exec forecastinn-postgres psql -U forecastinn_user -d forecastinn_prod -c 'SELECT ...'")` 

| Parameter | Value |
|-----------|-------|
| Server | `forecastinn-prod` (217.216.108.88) |
| User | `deploy` |
| App dir | `~/forecastinn/` on server |

## Database

PostgreSQL 16 (pgvector) runs in Docker as `forecastinn-postgres` on port 5432.
Access via: `docker exec forecastinn-postgres psql -U forecastinn_user -d <db> -c "..."`

| Database | Purpose |
|----------|---------|
| `forecastinn_prod` | Main production database |
| `forecastinn_crm` | CRM module |
| `forecastinn_stg` | Staging environment |
| `forecastinn_n8n` | n8n automation (forecastinn-automate) |
| `forecastinn_metabase` | Metabase analytics |

Also running: Redis, MinIO, pgbouncer, n8n, Metabase, Grafana, Prometheus.

## Notes

- Do not share information between projects or DMs
- Config changes require Eksa's explicit instruction
