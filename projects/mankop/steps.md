# Mankop — Steps & Runbook

## 1. First-Time Setup

```bash
cd ~/Projects/mankop/mankop-apps

# Install all dependencies
pnpm install

# Copy env files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Fill in backend/.env:
# - DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
# - SSH_HOST, SSH_USER, SSH_KEY_PATH
# - JWT_SECRET, MAIL_PASSWORD
# - STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY
```

## 2. Running Locally

### A. With SSH Tunnel to Production DB

Use when development needs real data (production MySQL).

```bash
# Terminal 1: open SSH tunnel
pnpm tunnel
# → localhost:3307 forwarded to server:3306

# Terminal 2: run backend + frontend
pnpm dev
```

> SSH key path inside container: `/opt/data/.ssh/id_rsa_mankop_app`
> Always use the absolute path — tilde paths (`~/.ssh`) are blocked by the security filter.

Or both in one command:
```bash
pnpm dev:tunnel
```

### B. Without Tunnel (Local DB)

If a local MySQL is available, update `backend/.env`:
```
DB_HOST=127.0.0.1
DB_PORT=3306
```

Then:
```bash
# Run migrations + seed (first time only)
pnpm -F backend migration:run
pnpm -F backend seed

# Start dev
pnpm dev
```

### C. Frontend Only

```bash
pnpm dev:frontend
# → http://localhost:5173
```

### D. Backend Only

```bash
pnpm dev:backend
# → http://localhost:3811 (or PORT from .env)
```

## 3. Object Storage (MinIO)

MinIO is required for file/image uploads.

```bash
# Start MinIO via Docker
pnpm storage
# → API:     http://localhost:9000
# → Console: http://localhost:9001 (minioadmin/minioadmin)

# Stop MinIO
pnpm storage:stop
```

## 4. Database Migrations

```bash
# Generate new migration
pnpm -F backend migration:generate src/database/migrations/<MigrationName>

# Run all pending migrations
pnpm -F backend migration:run

# Rollback last migration
pnpm -F backend migration:revert
```

## 5. SSH Tunnel (Manual)

```bash
bash scripts/tunnel.sh
# Reads SSH_* from backend/.env automatically
# Press Ctrl+C to close

# Override local port
LOCAL_PORT=3308 bash scripts/tunnel.sh
```

## 6. Build for Production

```bash
# Build frontend
pnpm -F frontend build
# → output: frontend/dist/

# Build backend
pnpm -F backend build
# → output: backend/dist/
```

## 7. Deploy to Production

Deployment is done via Docker image push to GitHub Container Registry.
Watchtower on the server auto-pulls the new image within 60 seconds.

```
[Action] Push Docker image to ghcr.io/forgeyard/mankop-apps/backend
[Risk]   Server auto-deploys immediately after image is available
[Choice] Yes / No / Postpone
```

> Always request Eksa's approval before pushing image to registry.

## 8. Lint, Type Check, Format

```bash
pnpm lint          # lint all packages
pnpm typecheck     # typecheck all packages
pnpm format        # format all packages
pnpm format:check  # check format without writing
```

## 9. Testing

```bash
pnpm test             # run all tests (backend: jest)
pnpm -F backend test  # backend only
```

## 10. Development Workflow (Planning + Subagent)

For every new feature or fix request in mankop:

**Step 1 — Plan first**
- Read relevant files before drafting (never plan from memory)
- Create a plan using the format in `skills/planning.md`
- Save to `projects/mankop/plans/YYYY-MM-DD-<slug>.md`
- Send plan to Eksa for approval — **do not execute before approved**

**Step 2 — Execute with subagents**
- Use `delegate_task` for tasks that can run in parallel or need deep focus:
  - Implementing a feature
  - Writing tests
  - Code review
  - Investigating a bug
- Each subagent gets a focused, scoped task — not the whole plan at once

**Step 3 — Report**
After completion, send a summary:
- What was done
- Files changed
- Anything that needs review or follow-up

## 11. URL Reference

| Environment | URL |
|-------------|-----|
| Frontend dev | http://localhost:5173 |
| Backend dev | http://localhost:3811 |
| MinIO API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |
| Frontend prod | https://app.mankop.com |
| Backend prod | https://api.mankop.com |
| Landing prod | https://mankop.com |
