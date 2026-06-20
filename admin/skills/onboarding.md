# Skill: Onboarding

## Command Format

```
viko onboard project <name> slug <slug> github <url> vps <host> <user> member <wa,...> [port <port>] [container <name>] [folder <path>]
```

Example — standard (port 22, folder /home/deploy/{slug}):
```
viko onboard project Mankop slug mankop github https://github.com/doa-sas/mankop-app vps 103.x.x.x deploy member 6281234567890 container mankop-api
```

Example — non-standard port + binary deploy folder:
```
viko onboard project ForecastInn slug forecastinn github https://github.com/xxx/forecast-inn vps 217.x.x.x deploy member 6281234567890 port 2222 container forecastinn-backend folder /home/deploy/forecastinn/prod/backend/current
```

Optional params:
- `port` — SSH port on deploy VPS (default: 22)
- `container` — Docker container name on deploy VPS (default: `{slug}-api`)
- `folder` — Working folder for deploy commands (default: `/home/deploy/{slug}`)

---

## Parse Validation

Before doing anything, validate:
- `name` — non-empty
- `slug` — lowercase alphanumeric + hyphens, no spaces, min 2 chars
- `github` — starts with `https://github.com/`
- `vps host` — valid hostname or IP
- `vps user` — non-empty
- `member` — comma-separated, digits only, 10–15 digits each
- `port` (if provided) — numeric, 1–65535
- `container` (if provided) — alphanumeric + hyphens, no spaces
- `folder` (if provided) — starts with `/`
- `group_jid` — must not already exist in `routing.json`

On validation failure:
> "Format kurang tepat. Coba lagi:
> `viko onboard project <nama> slug <slug> github <url> vps <host> <user> member <nomor,...>`"

On duplicate group:
> "Project ini sudah terdaftar."

---

## Execution Flow

### Step 1 — Acknowledge
> "Oke, lagi setup **{name}** dulu ya..."

### Step 2 — Generate SSH keypair
Call `scripts/setup-ssh.py {slug}`.

Send public key to group:
> "SSH key udah dibuat. Tambahin ini ke `~/.ssh/authorized_keys` di server `{host}` (user: `{user}`):
>
> `{public_key}`
>
> Kalau sudah, balas **ok**."

### Step 3 — Wait for owner confirmation ("ok" / "ready" / "done")

### Step 4 — Verify SSH connection
```bash
ssh -i /home/deploy/{slug}/.ssh/id_ed25519 \
    -p {port} \
    -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    {user}@{host} "echo viko-ok"
```

- Success → proceed
- Failure →
  > "Belum bisa konek ke server. Cek lagi key-nya ya, lalu balas **ok** untuk retry."

### Step 5 — Clone repository
```bash
GIT_SSH_COMMAND="ssh -i /home/deploy/{slug}/.ssh/id_ed25519 -o StrictHostKeyChecking=no" \
    git clone {github_url} /home/deploy/{slug}/repo
```

- Success → proceed
- Failure (private repo) →
  > "Repo-nya private. Tambahin deploy key ini ke GitHub → Settings → Deploy Keys:
  >
  > `{public_key}`
  >
  > Kalau sudah, balas **ok**."
  
  Then retry the clone once.

### Step 6 — Generate config from templates
Call `scripts/onboard.py` with all parsed parameters, including `--app-container`.

This creates:
- `/home/deploy/{slug}/config/SOUL.md`
- `/home/deploy/{slug}/config/rules/`
- `/home/deploy/{slug}/config/skills/`
- `/home/deploy/{slug}/config/project.json`

### Step 7 — Spawn container
Call `scripts/spawn-project.py {slug}`.

> "Hampir selesai, lagi nyalain AI-nya..."

Wait up to 30 seconds for health check to pass.

### Step 8 — Update routing
Add entry to `/home/deploy/bridge/routing.json`:
```json
"{group_jid}": { "slug": "{slug}", "port": {port}, "name": "{name}" }
```

### Step 9 — Handoff (last message from Admin in this group)
> "Selesai! Viko untuk **{name}** udah siap, gue serahin sekarang."

---

## Step Status Format

Each step: one short line while working.
```
SSH key dibuat ✓
Testing koneksi ke server...
Koneksi berhasil ✓
Cloning repo...
Repo berhasil di-clone ✓
Generating config...
Config siap ✓
Nyalain container...
```

---

## Error Handling

| Error | Action |
|-------|--------|
| SSH connection failed | Show pubkey again, wait for owner to fix, retry |
| Git clone 128/permission denied | Show deploy key, wait for owner to add, retry once |
| Port range exhausted (3001–3999) | "Tidak ada port tersedia, cek container yang berjalan." |
| Slug already exists on disk | "Slug '{slug}' sudah ada di server. Pilih slug lain." |
| Container health check timeout | "Container tidak bisa jalan dalam 30 detik — `docker logs viko-{slug}`" |
| `OWNER_WA` not set | Refuse all onboarding with explicit warning |

---

## Cancel Flow

Owner sends "cancel" at any point during onboarding:

1. Stop current step immediately
2. `docker stop {VIKO_NAME}-{slug} && docker rm {VIKO_NAME}-{slug}` (if container was spawned)
3. `rm -rf /home/deploy/{slug}/` (if directory was created)
4. Do not write to `routing.json`

> "Onboarding dibatalkan. Folder `/home/deploy/{slug}/` sudah dihapus."

---

## Offboard Command

The offboard command is handled by **Hermes-Project**, not Admin.
If owner sends `viko offboard` to Admin (unregistered group), respond:
> "Offboard dilakukan di dalam grup project-nya ya, bukan di sini."
