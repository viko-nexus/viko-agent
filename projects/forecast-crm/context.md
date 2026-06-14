# Project: ForecastCRM

## Overview

CRM system for ForecastInn — manages customer relationships and bookings.

## Paths

| Resource | Path |
|----------|------|
| App root | `~/Projects/forecastinn/forecast-crm` |
| AGENTS.md | `~/Projects/forecastinn/forecast-crm/AGENTS.md` |

## Team

| Name | Role |
|------|------|
| Eksa | Owner (Viko), developer |
| Andi | Product owner |

## Session Init

Before answering any technical question:
1. Read `README.md` at project root
2. Never answer from memory alone — always read actual files

## Production Server Access

Use the MCP tool — do not use raw SSH commands:

```
ssh_exec(project="forecastcrm", command="...")
```

Examples:
- `ssh_exec(project="forecastcrm", command="docker ps")`
- `ssh_exec(project="forecastcrm", command="ls ~/forecastcrm/")`

| Parameter | Value |
|-----------|-------|
| Server | `forecastcrm-prod` (same server as mankop) |
| User | `forecastcrm` |
| App dir | `~/prod/backend/` |

## Database

ForecastCRM uses **Neon.tech** (cloud PostgreSQL), not a local DB. Database name: `neondb`.
Credentials are in `.env` inside the release directory on the server:
`ssh_exec(project="forecastcrm", command="cat ~/prod/backend/releases/release_20260601_144958/.env")`

## Notes

- Do not share information between projects or DMs
- Only Eksa can authorize execution actions
