# Skill: Onboarding

## Command Format

```
viko onboard project <name> slug <slug> github <url> vps <host> <user> member <wa,...>
```

`group_jid` diekstrak otomatis dari `[CTX unregistered_group=<jid>]` di pesan — tidak perlu diketik.

Example:
```
viko onboard project Siprodev slug siprodev github https://github.com/doa-sas/siprodev-web vps 168.231.119.52 deploy member 6287820001010
```

Optional params:
- `member` — nomor HP untuk akses DM (comma-separated, boleh lebih dari satu)

---

## Parse Validation

Before doing anything, validate:
- `name` — non-empty
- `slug` — lowercase alphanumeric + hyphens, no spaces, min 2 chars
- `github` — valid GitHub URL (https:// or git@github.com:)
- `vps host` — valid hostname or IP
- `vps user` — non-empty
- `member` — digits only, 10–15 digits each
- `group_jid` — must not already exist in `data/bridge/routing.json`

On validation failure:
> "Format kurang tepat. Coba lagi:
> `viko onboard project <nama> slug <slug> github <url> vps <host> <user> member <nomor>`"

On duplicate group:
> "Project ini sudah terdaftar."

---

## Execution Flow

### Step 1 — Acknowledge
> "Oke, lagi setup **{name}** dulu ya..."

### Step 2 — Run onboarding script

Run `add-project.py` — handles clone, SSH key generation, container spawn, GitHub deploy key, routing update.

```bash
python3 scripts/add-project.py \
    {slug} \
    {group_jid} \
    {github_url} \
    --vps-host {vps_host} \
    --vps-user {vps_user} \
    --members {members_csv}
```

If the above fails with a Docker error (no socket inside container), fall back to SSH:
```bash
ssh viko-vps "cd ~/viko-agent && python3 scripts/add-project.py {slug} {group_jid} {github_url} --vps-host {vps_host} --vps-user {vps_user} --members {members_csv}"
```

Common errors:
- Clone failure → check `GITHUB_TOKEN` in `.env`, ensure repo is accessible
- Port conflict → script auto-allocates next port, should not happen
- Docker not found → use SSH fallback above

### Step 3 — Show VPS deploy key

```bash
cat ~/.viko/ssh/{slug}-deploy.pub
```

> "Tambahin pubkey ini ke `~/.ssh/authorized_keys` di server {vps_host} (user: {vps_user}) biar Viko bisa SSH ke sana untuk deploy:
>
> `{pubkey}`
>
> Kalau sudah, balas **ok**."

### Step 4 — Wait for owner confirmation ("ok" / "ready" / "done")

### Step 5 — Verify SSH

```bash
docker exec viko-hermes-{slug} ssh {slug}-prod "echo viko-ok"
```

- Success → proceed
- Failure → "Belum bisa konek. Cek lagi `authorized_keys`-nya ya, lalu balas **ok** untuk retry."

### Step 6 — Handoff (last message from Admin in this group)
> "Selesai! Viko untuk **{name}** udah siap, gue serahin sekarang."

---

## Step Status Format

```
Cloning repo...
Repo berhasil di-clone ✓
Generating config...
Config siap ✓
Nyalain container...
Container jalan ✓
Routing updated ✓
```

---

## Error Handling

| Error | Action |
|-------|--------|
| Clone failed (auth) | Check GITHUB_TOKEN in .env |
| Clone failed (private repo) | Add deploy key to GitHub → Settings → Deploy Keys, retry |
| Docker not found | Use `ssh viko-vps` fallback |
| Container health check timeout | `docker logs viko-hermes-{slug}` |
| SSH verify failed | Show pubkey again, wait for owner to fix, retry |
| `WHATSAPP_OWNER_NUMBER` not set | Refuse all onboarding with explicit warning |
| Slug already exists | "Slug '{slug}' sudah ada. Pilih slug lain." |

---

## Cancel Flow

Owner sends "cancel" at any point:

1. Stop current step
2. `docker rm -f viko-hermes-{slug}` (if container was spawned)
3. Remove from `data/bridge/routing.json` (if added)
4. Remove `data/hermes-{slug}/` (if created)

> "Onboarding dibatalkan."

---

## Offboard Command

If owner sends `viko offboard` to Admin: respond:
> "Offboard dilakukan di dalam grup project-nya ya, bukan di sini."
