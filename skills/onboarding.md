# Skill: Project Onboarding

Jalankan ini saat Eksa minta "viko onboard project X" dari dalam group WA project tersebut.

## Pra-syarat — kumpulkan info dari Eksa

Tanya jika belum ada:
- slug: nama project (lowercase, e.g. mankop)
- github_url: full URL (e.g. github.com/forgeyard/mankop-apps)
- vps_host: IP atau domain VPS project (optional)
- vps_user: SSH username di VPS project (optional, default: viko-exec)
- member_phones: nomor yang boleh DM Viko (optional, comma-separated)

Pastikan Eksa sudah menambahkan `id_viko.pub` ke VPS user sebelum lanjut:
```
VIKO_SSH_PUB dari .env — atau: cat /home/viko/.viko/ssh/id_viko.pub di trahku
```

## Dapatkan group JID saat ini

```bash
python3 -c "
import json
s = json.load(open('/opt/data/sessions/sessions.json'))
groups = [(k, v) for k, v in s.items() if '@g.us' in k]
if groups:
    latest = max(groups, key=lambda x: x[1].get('updated_at', ''))
    print(latest[0].split(':')[4])
else:
    print('NOT_FOUND')
"
```

## Phase 1 — Update SSH config (opsional, hanya jika ada VPS)

⚠️ WAJIB: jalankan via `ssh viko-vps` — JANGAN dari terminal container langsung.

```bash
ssh viko-vps python3 ~/projects/viko-agent/scripts/setup-keys.py \
  <slug> <github_url> [vps_host] [vps_user]
```

Script akan:
- Menambahkan `{slug}-vps` alias ke ~/.viko/ssh/config pakai `id_viko`
- Print `id_viko.pub` sebagai reminder kalau belum dipasang di VPS
- TIDAK generate keypair baru (satu key untuk semua project)
- TIDAK butuh GitHub deploy key (clone via HTTPS + GITHUB_TOKEN)

Jika tidak ada VPS: skip Phase 1, langsung ke Phase 2.

## Phase 2 — Clone + spawn (setelah key terpasang di VPS)

⚠️ WAJIB: semua perintah di bawah via `ssh viko-vps` — JANGAN dari terminal container.

```bash
# Test SSH ke VPS (skip jika tidak ada VPS)
ssh viko-vps ssh -F ~/.viko/ssh/config -o BatchMode=yes -o ConnectTimeout=10 <slug>-vps echo OK

# Run full onboarding (clone via HTTPS + token, context stubs, spawn Hermes)
ssh viko-vps python3 ~/projects/viko-agent/scripts/add-project.py \
  <slug> <group_jid> <github_url> [--vps-host <vps_host>] [--vps-user <vps_user>] [--members "<phones>"]
```

Baca output. Cek SPAWN_COMPLETE.

## Resolve nama member dari WA

Setelah spawn selesai, fetch nama semua participant dari group:

```bash
curl -s http://localhost:3000/group/<group_jid>/participants
```

Gunakan field `name` (WA profile name) untuk identifikasi member di context.md.
Jika `name` null → tampilkan phone saja, nama diketahui saat mereka kirim pesan pertama.

## Scan codebase + update context.md

```bash
ssh viko-vps ls ~/projects/<slug>/
ssh viko-vps cat ~/projects/<slug>/package.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('NestJS' if 'nest' in str(d) else 'Node.js')"
ssh viko-vps cat ~/projects/<slug>/go.mod 2>/dev/null | head -3
```

Tulis hasil ke projects/<slug>/context.md via edit.

## Kirim konfirmasi ke group

Setelah spawn selesai, kirim ringkasan:
- ✓ Project <slug> onboarded
- Stack yang terdeteksi
- Instance Hermes-<slug> berjalan terpisah (memory isolated)
- Siapa yang bisa tanya (semua) vs authorize (Eksa only)

KIRIM KONFIRMASI SEBELUM apapun yang mungkin memutus sesi.

## Add Member ke DM Allowlist

Ketika Eksa minta "viko allow @X bisa DM":

```bash
ssh viko-vps python3 ~/projects/viko-agent/scripts/allow-member.py 628xxx
ssh viko-vps "cd ~/projects/viko-agent && docker compose --profile full up -d --force-recreate hermes"
```

## Catatan

- GitHub clone: selalu via HTTPS + GITHUB_TOKEN, tidak butuh deploy key per repo
- VPS SSH: selalu pakai id_viko — Eksa tinggal add id_viko.pub ke VPS user baru
- setup-keys.py idempotent — aman dijalankan ulang (update SSH config alias saja)
- add-project.py idempotent — clone jadi pull jika repo sudah ada
- Routing.json hot-reload: bridge detect perubahan dalam <1 detik, tidak perlu restart
- Memory isolation: setiap project Hermes punya memory_store.db sendiri
