# Skill: Onboarding

## Command Format

**Single repo:**
```
viko onboard slug <slug> github <url> vps <host> user <ssh-user>
```

**Multi repo:**
```
viko onboard slug <slug> github web <url-web> github app <url-app> vps <host> user <ssh-user>
```

**With explicit members (optional):**
```
viko onboard slug <slug> github <url> vps <host> user <ssh-user> members 628xxx,628yyy
```

`group_jid` diekstrak otomatis dari `[CTX project=UNREGISTERED jid=<jid> ...]` — tidak perlu diketik.

Multi-repo dideteksi dari jumlah pasangan `github <subdir> <url>` — jika ada dua atau lebih, itu multi-repo.

---

## Parse Validation

- `slug` — lowercase alphanumeric + hyphens, min 2 chars
- `github` — valid GitHub URL (`https://` atau `git@github.com:`)
- `vps host` — valid hostname atau IP
- `vps user` — non-empty
- `members` (jika diisi) — digits only, 10–15 digits each
- `group_jid` — tidak boleh sudah ada di `data/bridge/routing.json`

On validation failure:
> "Format kurang tepat. Coba lagi:
> `viko onboard slug <slug> github <url> vps <host> user <ssh-user>`"

On duplicate group:
> "Project ini sudah terdaftar."

---

## Execution Flow

### Step 0 — Resolve members

**Jika `members` TIDAK diisi dalam command:**

Call bridge:
```bash
curl http://localhost:3000/group/{group_jid}/participants
```

Response berisi `participants` array dengan `{ phone, name, admin }`.
Filter out Viko's own number (bot). Tampilkan ke owner:

> "Anggota grup yang akan didaftarkan:
> - SDR Brother (628xxx)
> - Budi (628yyy)
>
> Lanjut semua? Atau ada yang dikecualikan?"

Tunggu konfirmasi → gunakan nomor tersebut sebagai `members_csv`.

**Jika `members` DIISI** → skip langsung ke Step 1.

### Step 1 — Acknowledge
> "Oke, lagi setup **{slug}** dulu ya..."

### Step 2 — Run onboarding script

**Single repo:**
```bash
python3 scripts/add-project.py \
    {slug} \
    {group_jid} \
    {github_url} \
    --vps-host {vps_host} \
    --vps-user {vps_user} \
    --members {members_csv}
```

**Multi repo** — panggil dua kali; panggilan kedua re-spawn container dengan kedua repo:
```bash
python3 scripts/add-project.py {slug} {group_jid} {github_web} --vps-host {vps_host} --vps-user {vps_user} --members {members_csv} --repo-subdir web
python3 scripts/add-project.py {slug} {group_jid} {github_app} --vps-host {vps_host} --vps-user {vps_user} --members {members_csv} --repo-subdir app
```

Fallback jika Docker tidak tersedia di dalam container:
```bash
ssh viko-vps "cd ~/viko-agent && python3 scripts/add-project.py ..."
```

Common errors:
- Clone failure → cek `GITHUB_TOKEN` di `.env`
- Docker not found → pakai SSH fallback

### Step 3 — Show deploy key

```bash
cat ~/.viko/ssh/{slug}-deploy.pub
```

**Single repo:**
> "Tambahin pubkey ini ke `~/.ssh/authorized_keys` di {vps_host} (user: {vps_user}):
>
> `{pubkey}`
>
> Kalau sudah, balas **ok**."

**Multi repo** — satu key untuk semua repo. Tambahin ke `authorized_keys` di VPS, DAN ke GitHub Deploy Keys di setiap repo (Settings → Deploy Keys → Add):
> "Pubkey untuk semua repo {slug}:
>
> `{pubkey}`
>
> Tambahin ke:
> 1. `~/.ssh/authorized_keys` di {vps_host}
> 2. GitHub Deploy Keys di {github_web} dan {github_app}
>
> Kalau sudah semua, balas **ok**."

### Step 4 — Wait for owner confirmation ("ok" / "ready" / "done")

### Step 5 — Verify SSH

```bash
docker exec viko-hermes-{slug} ssh {slug}-prod "echo viko-ok"
```

- Success → proceed
- Failure → "Belum bisa konek. Cek lagi ya, lalu balas **ok** untuk retry."

### Step 6 — Handoff
> "Selesai! Viko untuk **{slug}** udah siap."

---

## Error Handling

| Error | Action |
|-------|--------|
| Clone failed (auth) | Cek GITHUB_TOKEN di .env |
| Clone failed (private repo) | Add deploy key ke GitHub → Settings → Deploy Keys, retry |
| Docker not found | Pakai `ssh viko-vps` fallback |
| Container timeout | `docker logs viko-hermes-{slug}` |
| SSH verify failed | Tampilkan pubkey lagi, tunggu owner fix, retry |
| Slug already exists | "Slug '{slug}' sudah ada. Pilih slug lain." |

---

## Cancel Flow

Owner kirim "cancel" kapan saja:
1. Stop step yang sedang berjalan
2. `docker rm -f viko-hermes-{slug}` (jika sudah spawn)
3. Hapus dari `data/bridge/routing.json` (jika sudah ditambah)
4. Hapus `data/hermes-{slug}/` (jika sudah dibuat)

> "Onboarding dibatalkan."

---

## Offboard Command

Jika owner kirim `viko offboard` ke Admin:
> "Offboard dilakukan di dalam grup project-nya ya, bukan di sini."
