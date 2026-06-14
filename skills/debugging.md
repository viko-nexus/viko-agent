# Skill: Debugging

How Viko investigates errors and bugs across all projects.

## Process

1. Read the full error — do not assume cause from the first line
2. Check logs (most errors announce themselves)
3. Query the database if data integrity is suspect
4. Read the actual source code — never guess from memory
5. Identify root cause, not just symptom
6. Draft a fix plan (see `skills/planning.md`) and send for Eksa's approval

If error is in production: send a brief WA first, then investigate.

```
⚠️ [Project] error in [component]
[Error summary — 1 line]
Investigating now.
```

---

## 1. Checking Logs

### mankop

```
ssh_exec(project="mankop", command="docker logs mankop-backend --tail 100")
ssh_exec(project="mankop", command="docker logs mankop-backend --tail 200 --since 1h")
```

### forecastinn

```
ssh_exec(project="forecastinn", command="docker logs forecastinn-backend --tail 100")
ssh_exec(project="forecastinn", command="docker logs forecastinn-worker --tail 100")
ssh_exec(project="forecastinn", command="docker logs forecastinn-automate --tail 50")
ssh_exec(project="forecastinn", command="docker logs forecastinn-intelligence --tail 50")
```

### luxso

```
ssh_exec(project="luxso", command="docker logs luxso-backend --tail 100")
```

Luxso backend runs on the forecastinn VPS. Container name: `luxso-backend`.

### forecastcrm

```
ssh_exec(project="forecastcrm", command="docker logs forecastcrm-backend --tail 100")
ssh_exec(project="forecastcrm", command="docker logs forecastcrm-backend --since 1h")
```

---

## 2. Querying the Database

### mankop (MySQL)

Get password from running container, then query:

```
ssh_exec(project="mankop", command="DB_PASS=$(docker exec mankop-backend printenv DB_PASS) && mysql mankop-prod -u mankop-user -p\"$DB_PASS\" -e 'SELECT ...'")
```

Key tables: `cooperatives`, `members`, `loans`, `transactions`.

### forecastinn (PostgreSQL 16)

Access via docker exec on `forecastinn-postgres`:

```
ssh_exec(project="forecastinn", command="docker exec forecastinn-postgres psql -U forecastinn_user -d forecastinn_prod -c 'SELECT ...'")
```

Key tables: `reservations`, `properties`, `rooms`, `bills`, `organizations`, `room_types`, `events`.

### luxso (PostgreSQL, shared cluster)

```
ssh_exec(project="forecastinn", command="docker exec forecastinn-postgres psql -U forecastinn_client -d luxso -c 'SELECT ...'")
```

Key tables: `bookings`, `revenue_monthly`, `properties`, `users`, `targets`, `availability_calendar`.

### forecastcrm (Neon.tech — cloud PostgreSQL)

No psql on server. Get `DATABASE_URL` from the latest release, then run psql locally:

```
ssh_exec(project="forecastcrm", command="cat $(ls -dt ~/prod/backend/releases/*/  | head -1).env | grep DATABASE_URL")
```

Ask Eksa to run `psql <DATABASE_URL>` locally to query the Neon DB.

---

## 3. Reading Source Code

All project source code is mounted read-write into the Hermes container at the same path as on the host:

| Project | Local path |
|---------|-----------|
| mankop | `~/Projects/mankop/mankop-apps` |
| forecastinn | `~/Projects/forecastinn/forecast-inn` |
| luxso | `~/Projects/forecastinn/clients/Luxso-executive-dashboard` |
| forecastcrm | `~/Projects/forecastinn/forecast-crm` |

Read files directly — no SSH needed for code. Always read the actual file, never guess from memory.

---

## Rules

- Never guess at a fix without reading the actual code
- Always document root cause — not just the fix
- If the same error appeared before, check memory for prior resolution
- Propose a memory entry for each new error pattern resolved
- For production errors: notify first, investigate second, fix third (requires Eksa approval — Tier 3)
