# Skill: Project Onboarding

Jalankan ini saat Eksa minta "viko onboard project X" dari dalam group WA project tersebut.

## Pra-syarat — kumpulkan info dari Eksa

Tanya jika belum ada:
- slug: nama project (lowercase, e.g. forecastinn)
- github_url: full URL (e.g. github.com/eksa/forecastinn)
- vps_host: IP atau domain VPS project (optional)
- vps_user: SSH username di VPS project (optional, default: viko-exec)
- member_phones: nomor yang boleh DM Viko (optional, comma-separated)

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

## Phase 1 — Generate keys + GitHub deploy key

```bash
ssh viko-vps GITHUB_TOKEN=$GITHUB_TOKEN python3 ~/projects/viko-agent/scripts/setup-keys.py \
  <slug> <github_url> [vps_host] [vps_user]
```

Baca output. Cek marker PHASE1_COMPLETE.

Kirim ke group WA:
- Jika GitHub key otomatis: "✓ GitHub deploy key ditambahkan otomatis"
- Jika ada VPS: tampilkan public key + instruksi 1 baris untuk Eksa
- Minta Eksa reply "done" setelah VPS key dipasang

## Phase 2 — Test + clone + spawn (setelah Eksa reply "done")

```bash
# Test SSH connections — SELALU pakai alias, bukan raw IP
# (alias ada di ~/.viko/ssh/config, dibuat oleh setup-keys.py)
ssh viko-vps ssh -i ~/.viko/ssh/<slug>-deploy -o BatchMode=yes -o ConnectTimeout=10 <slug>-github echo OK
ssh viko-vps ssh -i ~/.viko/ssh/<slug>-deploy -o BatchMode=yes -o ConnectTimeout=10 <slug>-vps echo OK  # skip if no vps

# Run full onboarding (clone + context stubs + spawn Hermes instance)
ssh viko-vps python3 ~/projects/viko-agent/scripts/add-project.py \
  <slug> <group_jid> <github_url> [--vps-host <vps_host>] [--vps-user <vps_user>] [--members "<phones>"]
```

Baca output. Cek SPAWN_COMPLETE.

## Scan codebase + update context.md

```bash
# Deteksi stack
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

Cara 1 — via @mention (phone dari [Mentioned: 628xxx] di body pesan):
```bash
ssh viko-vps python3 ~/projects/viko-agent/scripts/allow-member.py 628xxx
ssh viko-vps "cd ~/projects/viko-agent && docker compose --profile full up -d --force-recreate hermes"
```

Cara 2 — dari pesan X di group (phone dari sender JID):
```bash
ssh viko-vps python3 ~/projects/viko-agent/scripts/allow-member.py 628xxx
```

Cara 3 — phone disebut langsung oleh Eksa:
```bash
ssh viko-vps python3 ~/projects/viko-agent/scripts/allow-member.py 628xxx
```

## Catatan

- setup-keys.py idempotent — aman dijalankan ulang
- spawn-hermes.py idempotent — skip jika group JID sudah ada di routing.json  
- add-project.py idempotent — clone jadi pull jika repo sudah ada
- Routing.json hot-reload: bridge detect perubahan dalam <1 detik, tidak perlu restart
- Memory isolation: setiap project Hermes punya memory_store.db sendiri
- Untuk private GitHub repo: GITHUB_TOKEN dengan scope repo sudah cukup (personal + org)
