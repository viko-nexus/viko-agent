# Project: Mankop

## Overview

Mankop (Koperasi Multi Pihak) — SaaS platform for Indonesian digital cooperative management.
Supports conventional and sharia cooperatives: savings & loans, member management, financial
reports, QR payment.

## Paths

| Resource | Path |
|----------|------|
| Monorepo root | `~/Projects/mankop/mankop-apps` |
| Frontend | `~/Projects/mankop/mankop-apps/frontend` |
| Backend | `~/Projects/mankop/mankop-apps/backend` |
| Landing page | `~/Projects/mankop/mankop-web` |
| AGENTS.md | `~/Projects/mankop/mankop-apps/AGENTS.md` |

> "mankop" always means mankop-apps. "mankop web" means the landing page.

## Team

| Name | Role |
|------|------|
| Eksa | Owner (Viko), developer |
| Pak Hery | Client / stakeholder |

## GitHub

- Repo: `git@github.com:forgeyard/mankop-apps.git`
- Package image: `ghcr.io/forgeyard/mankop-apps/backend:latest`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite, TypeScript, Tailwind CSS 4, TanStack Router/Query/Table |
| Backend | NestJS, TypeORM, MySQL, Redis, JWT, Socket.io |
| Storage | MinIO (S3-compatible) |
| Mail | Hostinger SMTP (smtp.hostinger.com:465) |
| Deploy | Docker + Watchtower (auto-pull from ghcr.io) |
| Tunnel | SSH tunnel to production MySQL (via `scripts/tunnel.sh`) |
| Package | pnpm workspaces, Node v22 |

## SSH Access

```bash
ssh -i ~/.ssh/id_rsa_mankop_app mankop-app@69.62.81.224
```

| Parameter | Value |
|-----------|-------|
| Key | `~/.ssh/id_rsa_mankop_app` |
| User | `mankop-app` |
| Host | `69.62.81.224` |
| Port | 22 (default) |

SSH tunnel — forwards production MySQL to local `localhost:3307 → 69.62.81.224:3306`:

```
SSH_HOST=69.62.81.224
SSH_USER=mankop-app
SSH_KEY_PATH=~/.ssh/id_rsa_mankop_app
```

## Environment Variables

### Backend (`backend/.env.example`)

| Variable | Description |
|----------|-------------|
| `PORT` | Backend port (default: 3811, prod: 4000) |
| `NODE_ENV` | `development` / `production` |
| `DB_HOST` | MySQL host (local: 127.0.0.1 via SSH tunnel) |
| `DB_PORT` | MySQL port (default: 3307 via tunnel) |
| `DB_USER` | MySQL username |
| `DB_PASS` | MySQL password *(sensitive)* |
| `DB_NAME` | Database name (prod: `mankop-prod`) |
| `SSH_HOST` | Production server IP |
| `SSH_PORT` | SSH port (default: 22) |
| `SSH_USER` | SSH username |
| `SSH_KEY_PATH` | Path to private key |
| `JWT_SECRET` | JWT signing secret *(sensitive)* |
| `JWT_EXPIRES_IN` | Access token TTL (default: 15m) |
| `JWT_REFRESH_EXPIRES_IN` | Refresh token TTL (default: 7d) |
| `MAIL_HOST` | SMTP host (`smtp.hostinger.com`) |
| `MAIL_PORT` | SMTP port (465) |
| `MAIL_USER` | SMTP username (`no-reply@mankop.com`) |
| `MAIL_PASSWORD` | SMTP password *(sensitive)* |
| `APP_URL` | Base URL (for email verification links) |
| `CORS_ORIGIN` | Allowed origins (comma-separated) |
| `STORAGE_ENDPOINT` | MinIO endpoint URL |
| `STORAGE_ACCESS_KEY` | MinIO access key |
| `STORAGE_SECRET_KEY` | MinIO secret key *(sensitive)* |
| `STORAGE_BUCKET` | Bucket name (default: `mankop`) |
| `STORAGE_PUBLIC_URL` | Public URL for image URLs in frontend |

### Frontend (`frontend/.env.example`)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL (default: `http://localhost:4000`) |
| `VITE_DEFAULT_COOPERATIVE_ID` | Default cooperative ID on registration page |

## Deployment Architecture

Production runs on VPS with Docker:
- Backend: container from `ghcr.io/forgeyard/mankop-apps/backend:latest`
- MinIO: object storage container (network_mode: host)
- Watchtower: auto-pulls new image every 60 seconds
- MySQL: on the same server, accessed via SSH tunnel from local

## Platform Roles

| Role | Scope |
|------|-------|
| `superadmin` | Platform-wide: all cooperatives, billing, CMS |
| `owner` | Full access to one cooperative |
| `employee` | Custom role with granular permissions |
| `member` | Self-service: loan applications, QR payment |

## Session Init

Before answering any technical question:
1. Read `README.md` at `~/Projects/mankop/mankop-apps`
2. Read `~/Projects/mankop/mankop-apps/AGENTS.md` if present
3. Never answer from memory alone — always read actual files

## Notes

- Production database is accessed via SSH tunnel only — no direct connection
- Backend `.env` contains SSH credentials — never commit
- Watchtower auto-deploys whenever a new image is pushed to ghcr.io
- Do not share information between projects or DMs
- Only Eksa can authorize execution actions
