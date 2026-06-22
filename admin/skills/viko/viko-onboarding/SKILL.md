---
name: viko-onboarding
description: "Daftarkan grup WhatsApp jadi project Viko lewat wizard percakapan (nama->slug, repo GitHub, server opsional, members), lalu jalankan add-project.py."
version: 1.0.0
author: Viko
metadata:
  hermes:
    tags: [onboarding, project, whatsapp, viko, setup]
---

# Skill: Onboarding

> **Sumber kebenaran perilaku runtime ada di `admin/SOUL.md`** (section
> "## Onboarding Wizard"). Skill ini referensi eksekusi detail: error handling,
> tampilan deploy-key, verify SSH, cancel flow, dan offboard. Kalau ada beda,
> SOUL.md yang menang.

Onboarding jalan lewat **wizard percakapan** — tanya satu hal per langkah, santai,
nggak nyuruh owner ngapalin format apa pun. Yang **wajib cuma `slug` + `github`**;
server/SSH user/members **opsional**. Ada juga shortcut one-liner buat power user.

`group_jid` selalu diekstrak otomatis dari `[CTX project=UNREGISTERED jid=<jid> ...]`
yang ditambahin bridge — owner tidak pernah ngetik ini.

---

## Entry — Cara Mulai

**Wizard (default):**
Owner ketik `onboard`, atau jelas-jelas mau daftarin grup ini ("daftarin dong",
"register grup ini", dll) → mulai wizard dari Langkah 1.

**Shortcut one-liner (power user, tetap didukung):**
Kalau owner kirim one-liner LENGKAP dengan field wajib (`slug` + `github`), SKIP
wizard — langsung parse dan jalankan eksekusi.

```
viko onboard slug <slug> github <url> [vps <host> user <ssh-user> port <port>] [members 628xxx,628yyy]
```

Multi repo (tiap label jadi `--repo-subdir`):
```
viko onboard slug <slug> github web <url-web> github app <url-app> [vps <host> user <ssh-user>]
```

- `vps <host> user <ssh-user> port <port>` opsional — kalau tidak ada, project jalan
  lokal tanpa SSH. Kalau `vps` ada tapi `user` tidak → default `viko-exec`; `port`
  tidak ada → default `22`.
- `members` opsional — kalau tidak ada, anggota dibaca otomatis dari grup.
- Multi-repo dideteksi dari ≥2 entri repo.

**One-liner PARSIAL** (ada `onboard` tapi field wajib belum lengkap, mis. slug doang
tanpa github) → JANGAN tolak. Mulai wizard, tapi lewati langkah yang sudah terisi —
cuma tanya field yang masih kurang.

---

## Wizard — Aturan Umum

- **Satu pertanyaan per langkah.** Jangan dump seluruh format sekaligus.
- **Input salah → tanya ulang HANYA field itu**, dengan kalimat santai. Jangan
  pernah balas "Format kurang tepat, coba lagi: <one-liner>".
- Sesi owner 15 menit dari bridge bikin follow-up ngalir mulus — owner nggak perlu
  nyebut "viko" lagi di tiap balasan selama wizard jalan.
- Sebelum mulai: kalau `group_jid` sudah ada di `data/bridge/routing.json` →
  > "Project ini sudah terdaftar." (stop, jangan lanjut wizard) — KECUALI owner
  > eksplisit minta re-onboard ulang grup ini. Cuma kalau ada niat re-onboard
  > eksplisit baru lanjut, dan eksekusi nanti pakai `--force` (lihat Execution Flow).
- Status per langkah singkat: "Slug `x` ✓", "Repo dicatat ✓".

### Langkah 1 — Nama → Slug

> "Nama project-nya apa?"

Dari jawaban, **auto-slugify**: huruf kecil semua; spasi/underscore → hyphen;
buang karakter selain `[a-z0-9-]`; hyphen dobel dirapatkan jadi satu; buang hyphen di
awal/akhir. Lalu konfirmasi:

> "Oke slug-nya `man-kop` ya?"

Validasi slug: lowercase alphanumeric + hyphen, minimal 2 char. Kalau hasil
slugify kosong / kependekan → tanya ulang nama aja:
> "Namanya kurang pas buat slug. Coba kasih nama lain ya."

### Langkah 2 — Repo

Minta **sekali** pakai format (single ATAU multi dalam 1 pesan):
> "Repo GitHub-nya? Single: kirim URL aja. Multi: `label = url, label = url`
> (mis. `app = https://github.com/x/app, web = https://github.com/x/web`)."

- Validasi tiap URL: `https://github.com/...` atau `git@github.com:...`. Bukan
  GitHub → tanya ulang yang itu aja: "cuma support GitHub ya".
- **1 URL tanpa label** → single repo.
- **≥2 entri** → multi-repo; tiap `label` jadi `--repo-subdir`.
- Kalau multi tapi owner lupa label → **auto-derive dari nama repo**
  (`siprodev-app` → `app`) lalu konfirmasi sekali.
- JANGAN loop "ada lagi?" — satu pesan format itu cukup.

### Langkah 3 — Server (opsional)

Minta **sekali** pakai format:
> "Server buat deploy/SSH? Format `host/user/port` (mis. `159.65.0.1/root/22`) —
> `user` default `viko-exec`, `port` default `22` kalau dikosongin. Atau bales *skip*
> (Viko kelola lokal aja)."

- Parse `host` / `user` / `port` dari satu pesan itu.
- `user` tidak diisi → `viko-exec`. `port` tidak diisi → `22`.
- **`skip`** → `vps_host` kosong. Artinya project jalan **lokal tanpa SSH** —
  bukan "deploy di VPS central". Jangan minta user/port.

### Langkah 4 — Members

Baca anggota grup sebagai **REFERENSI** (bukan auto-daftar semua):
```bash
curl http://localhost:3000/group/{group_jid}/participants
```

Response: `participants` array `{ jid, lid, phone, name, resolved, admin }`.
- `resolved:true` → `phone` adalah **nomor HP asli** (sudah di-resolve dari LID). Hanya ini yang boleh didaftarkan.
- `resolved:false` → no HP belum terhubung di session (anggota itu belum pernah chat / belum di kontak). `phone` = `null`. **JANGAN daftarkan `lid` sebagai nomor** — itu identifier internal WhatsApp, BUKAN no HP.
- `name` bisa `null` (anggota yang belum pernah kirim pesan) — tampilkan nomornya saja.

Filter nomor Viko sendiri (bot), lalu tampilkan sebagai referensi dan minta owner **pilih**:

> "Anggota grup (referensi dari WhatsApp):
> - Budi (6287884834521)
> - 6282235383168 (nama belum kebaca)
> - 1 anggota lagi no HP-nya belum kebaca — kasih nomornya kalau mau dimasukkan
>
> Mau daftarkan yang mana jadi member? Bales nomor/nama yang dipilih, `semua yang ada nomornya`, atau `skip`."

**WAJIB:**
- Hanya masukkan nomor dengan `resolved:true`, ATAU nomor manual valid dari owner.
- JANGAN PERNAH masukkan `lid` (mis. `84942340026497`) ke `members_csv` — itu lolos cek "10–15 digit" tapi bukan no HP. Ini akar bug member ke-daftar nyasar.
- Default **bukan** "semua masuk" — owner pilih eksplisit. Kalau owner bilang "semua", pakai semua yang `resolved:true` saja.

Owner bisa: pilih sebagian, kasih nomor manual `628xxx, 628yyy` (comma-separated), atau `skip`.
Validasi nomor manual: digits only, 10–15 digit, diawali kode negara. (Nomor manual yang nggak valid → tanya ulang nomor itu.)

Kalau daftar akhirnya **kosong** (owner `skip` / cuma ada Viko) → `members_csv` kosong;
nanti pas eksekusi `--members` di-OMIT.

### Langkah 5 — Konfirmasi

Tampilkan ringkasan, lalu minta lanjut:

> "Siap daftarin:
> - slug: `man-kop`
> - repo: <url> (atau daftar repo + subdir buat multi-repo)
> - server: 1.2.3.4 (user viko-exec, port 22) — atau "lokal aja, tanpa SSH"
> - members: SDR Brother, Budi
>
> Lanjut? (ya/cancel)"

`ya` → ke Execution Flow. `cancel` → Cancel Flow.

### Langkah 6 — Jalankan

Lanjut ke **Execution Flow** di bawah.

---

## Execution Flow

Field datang dari wizard (atau shortcut one-liner): `slug`, `group_jid`, repo(s),
opsional `vps_host` + `vps_user` + `vps_port`, dan `members_csv`.

### Step 1 — Acknowledge
> "Oke, lagi setup **{slug}** dulu ya..."

### Step 2 — Run onboarding script

Selalu pakai **path absolut** ke skrip (cwd agent bukan repo root). Bangun command
dengan **flag opsional**:
- Tambah `--vps-host {vps_host}` HANYA kalau ada server (bukan lokal-only).
- Tambah `--vps-user {vps_user}` HANYA kalau user-nya BUKAN `viko-exec`.
- Tambah `--vps-port {vps_port}` HANYA kalau port-nya BUKAN `22`.
- Tambah `--members {members_csv}` HANYA kalau csv-nya tidak kosong. Kalau kosong,
  OMIT `--members` (script otomatis baca anggota grup).
- Tambah `--force` HANYA kalau ini RE-ONBOARD eksplisit atas grup yang `group_jid`-nya
  sudah ada di `routing.json` (guard add-project.py bakal nolak tanpa flag ini).
  Onboard normal grup baru → JANGAN pakai `--force`.

**Single repo, ada server:**
```bash
python3 "$VIKO_PROJECTS_ROOT/viko-agent/scripts/add-project.py" \
    {slug} \
    {group_jid} \
    {github_url} \
    --vps-host {vps_host} \
    --members {members_csv}
```

**Single repo, lokal-only (skip server)** — OMIT `--vps-host`:
```bash
python3 "$VIKO_PROJECTS_ROOT/viko-agent/scripts/add-project.py" {slug} {group_jid} {github_url} --members {members_csv}
```

**Multi repo** — panggil **per repo** dengan `--repo-subdir {label}`; panggilan
terakhir re-spawn container dengan semua repo. Tambahkan
`--vps-host`/`--vps-user`/`--vps-port` mengikuti aturan opsional di atas.
Panggilan multi-repo per-`--repo-subdir` ini TIDAK perlu `--force` — guard
add-project.py memang mengizinkan `group_jid` yang sama untuk subdir berbeda:
```bash
python3 "$VIKO_PROJECTS_ROOT/viko-agent/scripts/add-project.py" {slug} {group_jid} {github_web} --members {members_csv} --repo-subdir web
python3 "$VIKO_PROJECTS_ROOT/viko-agent/scripts/add-project.py" {slug} {group_jid} {github_app} --members {members_csv} --repo-subdir app
```

Common errors:
- Clone failure → cek `GITHUB_TOKEN` di `.env`
- Docker not found → cek environment container

### Step 3 — Show deploy key

```bash
cat ~/.viko/ssh/{slug}-deploy.pub
```

> **Lokal-only (tanpa server)** — kalau owner pilih *skip* di wizard, deploy key
> tetap dibuat untuk akses repo, tapi TIDAK ada `authorized_keys` server yang
> perlu disetel. Untuk single repo lokal-only, deploy key cukup ditambahkan ke
> GitHub Deploy Keys repo-nya (kalau repo private). Lewati instruksi server.

**Single repo (ada server):**
> "Tambahin pubkey ini ke `~/.ssh/authorized_keys` di {vps_host} (user: {vps_user}):
>
> `{pubkey}`
>
> Kalau sudah, balas **ok**."

**Multi repo** — satu key untuk semua repo. Tambahin ke `authorized_keys` di VPS
(kalau ada server), DAN ke GitHub Deploy Keys di setiap repo (Settings → Deploy
Keys → Add):
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

### Step 5 — Verify SSH (HANYA kalau ada server)

**Lokal-only (skip server di wizard) → LEWATI langkah ini sepenuhnya**, langsung
ke Handoff. Nggak ada SSH yang perlu diverifikasi.

**Kalau ada server:**
```bash
docker exec -u hermes viko-hermes-{slug} ssh {slug}-prod "echo viko-ok"
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
| Docker not found | Cek environment container |
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
