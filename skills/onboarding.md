# Skill: Project Onboarding

Jalankan ini saat Eksa minta "viko onboard project X" dari dalam group WA project tersebut.

## Langkah-langkah

### 1. Dapatkan group JID (dari context sesi saat ini)

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

### 2. Jalankan add-project.py via SSH ke viko-vps

```bash
ssh viko-vps python3 ~/projects/viko-agent/scripts/add-project.py \
  <slug> <group_jid> <github_url> [phones]
```

Contoh:
```bash
ssh viko-vps python3 ~/projects/viko-agent/scripts/add-project.py \
  siprodev \
  120363407940533307@g.us \
  https://github.com/forgeyard/siprodev \
  "6282112124452"
```

### 3. Scan codebase dan update context.md

```bash
# Di trahku, via SSH:
ssh viko-vps ls ~/projects/<slug>/
ssh viko-vps cat ~/projects/<slug>/package.json 2>/dev/null \
  || ssh viko-vps cat ~/projects/<slug>/go.mod 2>/dev/null \
  || ssh viko-vps ls ~/projects/<slug>/
```

Tulis hasil scan ke `~/projects/viko-agent/projects/<slug>/context.md`.

### 4. Restart hermes

```bash
ssh viko-vps "cd ~/projects/viko-agent && docker compose --profile full up -d --force-recreate hermes"
```

### 5. Kirim konfirmasi ke group

Setelah restart, kirim ringkasan singkat:
- Project X sudah di-onboard
- Stack yang terdeteksi
- Siapa yang bisa bertanya

## Catatan

- Selalu jalankan dari dalam group WA project yang akan di-onboard (supaya JID benar)
- Script idempotent — aman dijalankan ulang jika ada yang gagal
- Jika github_url butuh token (private repo): gunakan `https://<token>@github.com/...`
- Restart akan memutus sesi aktif — kirim konfirmasi SEBELUM restart
