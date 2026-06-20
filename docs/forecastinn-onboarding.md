# ForecastInn — Onboarding Reference

Dokumen ini berisi data lengkap untuk onboarding semua project ForecastInn ke viko-agent.
Dibaca oleh Hermes-Admin saat menjalankan perintah `viko onboard`.

---

## Projects dalam Ekosistem ForecastInn

| Project | Slug | Server | User |
|---|---|---|---|
| Forecast Inn (main platform) | `forecast-inn` | `217.216.108.88` | `deploy` |
| Forecast CRM | `forecast-crm` | `69.62.81.224` | `forecastcrm` |
| Luxso Executive Dashboard | `luxso` | `217.216.108.88` | `deploy` |

**Catatan:** `forecast-inn` dan `luxso` berbagi VPS yang sama (`217.216.108.88`), masing-masing dengan
container terpisah pada network `forecastinn_net`.

---

## 1. Forecast Inn

### Onboard Command

```
viko onboard project Forecast Inn slug forecast-inn github https://github.com/Hotelrevenuepro/forecast-inn vps 217.216.108.88 deploy member <wa_member,...>
```

### project.json

```json
{
  "name": "Forecast Inn",
  "slug": "forecast-inn",
  "github": "https://github.com/Hotelrevenuepro/forecast-inn",
  "deploy_vps": {
    "host": "217.216.108.88",
    "user": "deploy"
  },
  "app_container": "forecastinn-backend",
  "databases": {
    "postgres": {
      "host": "forecastinn-postgres",
      "port": 5432,
      "user": "forecastinn_user",
      "password": "<DB_PASSWORD>",
      "name": "forecastinn_prod"
    },
    "redis": {
      "host": "forecastinn-redis",
      "port": 6379,
      "password": "<REDIS_PASSWORD>",
      "db_index": 0
    }
  }
}
```

### Tech Stack

- **Backend**: Go 1.25 / Gin / GORM — port 8000 (`forecastinn-backend`)
- **Frontend**: React 18 / TypeScript / Vite — port 4028
- **Intelligence**: Go / Gin — port 8900 (`forecastinn-intelligence`)
- **Forecast Service**: Python / FastAPI — port 8800 (`forecastinn-service`)
- **Worker**: Go async jobs (`forecastinn-worker`)
- **Database**: PostgreSQL 16 (`forecastinn-postgres`) + Redis (`forecastinn-redis`)
- **Network**: `forecastinn_net` (shared Docker network)

### Catatan untuk Hermes-Project

- Monorepo dengan 5+ service — Hermes fokus ke `apps/backend/` untuk API changes
- DB credentials dari `project.json`, bukan env vars
- Deploy via `docker compose -f docker-compose-prod.yml up -d --build` di masing-masing `apps/<service>/`
- Schema migrations: `apps/backend/migrations/` format `YYYYMMDDHHMMSS_<name>.up.sql`
- Internal service auth via `INTERNAL_API_KEY` header (bukan JWT)

---

## 2. Forecast CRM

### Onboard Command

```
viko onboard project Forecast CRM slug forecast-crm github https://github.com/Hotelrevenuepro/forecast-crm vps 69.62.81.224 forecastcrm member <wa_member,...>
```

### project.json

```json
{
  "name": "Forecast CRM",
  "slug": "forecast-crm",
  "github": "https://github.com/Hotelrevenuepro/forecast-crm",
  "deploy_vps": {
    "host": "69.62.81.224",
    "user": "forecastcrm"
  },
  "app_container": "forecastcrm-backend",
  "databases": {
    "postgres": {
      "host": "<DB_HOST>",
      "port": 5432,
      "user": "<DB_USER>",
      "password": "<DB_PASSWORD>",
      "name": "<DB_NAME>"
    },
    "redis": {
      "host": "<REDIS_HOST>",
      "port": 6379,
      "password": "<REDIS_PASSWORD>",
      "db_index": 0
    }
  }
}
```

> **Catatan**: Forecast CRM menggunakan `DATABASE_URL` dan `REDIS_URL` (connection string format)
> di `.env`. Saat mengisi `project.json`, parse komponen dari connection string tersebut.

### Tech Stack

- **Backend**: Go 1.23 / Chi — port 8080 (`forecastcrm-backend`)
- **Frontend**: React 18 / TypeScript / Vite — port 5173
- **Database**: PostgreSQL + Redis (external managed, lihat `backend/.env`)
- **SSH key**: `~/.ssh/id_rsa_forecastcrm`

### Catatan untuk Hermes-Project

- Root-level `package.json` untuk menjalankan backend+frontend sekaligus
- Backend entry: `backend/cmd/server/`
- Migrations: `backend/migrations/` via `golang-migrate`
- Deploy: `make deploy` atau `docker compose -f docker-compose-prod.yml up -d --build` di `backend/`

---

## 3. Luxso Executive Dashboard

### Onboard Command

```
viko onboard project Luxso slug luxso github https://github.com/Hotelrevenuepro/luxso-executive-dashboard vps 217.216.108.88 deploy member <wa_member,...>
```

### project.json

```json
{
  "name": "Luxso",
  "slug": "luxso",
  "github": "https://github.com/Hotelrevenuepro/luxso-executive-dashboard",
  "deploy_vps": {
    "host": "217.216.108.88",
    "user": "deploy"
  },
  "app_container": "luxso-backend",
  "databases": {
    "postgres": {
      "host": "luxso-postgres",
      "port": 5432,
      "user": "luxso",
      "password": "<DB_PASSWORD>",
      "name": "luxso_dashboard"
    }
  }
}
```

> **Catatan**: Luxso tidak menggunakan Redis — field `redis` di `databases` dikosongkan.

### Tech Stack

- **Backend**: Go 1.25 / Chi / SQLC — port 4000 (`luxso-backend`)
- **Frontend**: React 18 / TypeScript / Vite — served via nginx (`luxso-frontend`)
- **Database**: PostgreSQL 16 (`luxso-postgres`)
- **Integrasi**: Beds24 API v2, Xero OAuth2
- **SSH key**: `~/.ssh/id_rsa_forecastinn` (berbagi dengan forecast-inn, VPS sama)

### Catatan untuk Hermes-Project

- Credential Beds24 dan Xero **dienkripsi di DB** dengan AES-256 (`ENCRYPTION_KEY`)
- First-run wizard wajib diselesaikan sebelum dashboard bisa diakses
- Migrations: `server/db/migrations/` via `golang-migrate`
- Build: `docker compose up -d --build` dari root project

---

## SSH Keys Reference

| Server | Host | User | SSH Key |
|---|---|---|---|
| forecastinn-prod | `217.216.108.88` | `deploy` | `~/.ssh/id_rsa_forecastinn` |
| forecastcrm-prod | `69.62.81.224` | `forecastcrm` | `~/.ssh/id_rsa_forecastcrm` |
| luxso-prod | `217.216.108.88` | `deploy` | `~/.ssh/id_rsa_forecastinn` |

SSH config aliases tersedia di `~/.ssh/config`:
- `forecastinn-prod` → `217.216.108.88`
- `forecastcrm-prod` → `69.62.81.224`
- `luxso-prod` → `217.216.108.88`

---

## GitHub Org

Semua repo ada di org **Hotelrevenuepro**: https://github.com/orgs/Hotelrevenuepro/repositories

| Repo | URL |
|---|---|
| forecast-inn | https://github.com/Hotelrevenuepro/forecast-inn |
| forecast-crm | https://github.com/Hotelrevenuepro/forecast-crm |
| luxso-executive-dashboard | https://github.com/Hotelrevenuepro/luxso-executive-dashboard |

---

## Checklist Onboarding per Project

Setelah `viko onboard` selesai (Phase 1), lakukan Phase 2 setup:

- [ ] SSH deploy key sudah ditambahkan ke GitHub repo
- [ ] `project.json` sudah diisi credentials DB yang benar (mode 600)
- [ ] `db-connector.py` bisa konek ke PostgreSQL (test: `pg_query` → `SELECT 1`)
- [ ] Hermes-Project container up dan merespons di WA group
- [ ] Perintah `viko status` dari owner menampilkan info yang benar
