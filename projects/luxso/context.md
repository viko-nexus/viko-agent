# Project: Luxso Executive Dashboard

## Overview

Executive dashboard for Luxso Villa & Resort Management — KPI tracking, P&L, and
occupancy analytics.

## Paths

| Resource | Path |
|----------|------|
| App root | `~/Projects/forecastinn/clients/Luxso-executive-dashboard` |
| Docs | `docs/` |
| Plans | `docs/superpowers/plans/` |
| Integration docs | `docs/integration/` |
| Backend handlers | `server/internal/handlers/` |
| AGENTS.md | `~/Projects/forecastinn/clients/Luxso-executive-dashboard/AGENTS.md` |

## Stack

React 18 · TypeScript · Vite · Tailwind · Go 1.25 · Chi · SQLC · PostgreSQL 16 ·
Docker · Beds24 API v2 · Xero OAuth2

## Team

| Name | Role |
|------|------|
| Eksa | Developer & product lead |
| Andi | Owner / stakeholder |

## Session Init

On first message, read these in order before replying:
1. Read `README.md` at app root
2. Read `docs/integration/README.md`
3. List latest plans: `ls docs/superpowers/plans/ | sort -r | head -5`
4. Read the most recent plan file

## Navigation by Topic

| Topic | Where to look |
|-------|--------------|
| Status / roadmap | Latest plan in `docs/superpowers/plans/` |
| Technical (code, architecture) | `server/` or `client/src/` |
| Business data (P&L, revenue, occupancy) | `docs/data/` |
| Architecture / integration | `docs/integration/data-model.md`, `sync-strategy.md` |
| Bugs / QA | `server/internal/handlers/` |

## Production Server Access

Use the MCP tool — do not use raw SSH commands:

```
ssh_exec(project="luxso", command="...")
```

Examples:
- `ssh_exec(project="luxso", command="docker ps")`
- `ssh_exec(project="luxso", command="ls ~/luxso/")`

| Parameter | Value |
|-----------|-------|
| Server | `luxso-prod` (217.216.108.88, same VPS as forecastinn) |
| User | `deploy` |
| App dir | `~/luxso/` on server |

## Database

Luxso shares the `forecastinn-postgres` PostgreSQL cluster (same VPS). Database: `luxso`, owned by role `forecastinn_client`.
Access via forecastinn SSH: `ssh_exec(project="forecastinn", command="docker exec forecastinn-postgres psql -U forecastinn_client -d luxso -c '...'")`

## Notes

- Do not share information between projects or DMs
- Only Eksa can authorize execution actions
