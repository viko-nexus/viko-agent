# Project: viko-agent

## Overview

`viko-agent` adalah home Viko sendiri — repo yang mendefinisikan identitas, rules, skills, dan
project context. Viko boleh (dan diharapkan) memodifikasi repo ini untuk memperbaiki dirinya
sendiri, selama mengikuti authorization tier di bawah.

## Paths

| Resource | Host Path | Container Path |
|----------|-----------|----------------|
| Repo root | `/Users/eksa/Projects/viko-agent` | `/opt/viko-agent` |
| Data / runtime | `/Users/eksa/Projects/viko-agent/data/hermes` | `/opt/data` |
| SOUL.md (runtime) | `data/hermes/SOUL.md` | `/opt/data/SOUL.md` |
| Config | `data/hermes/config.yaml` | `/opt/data/config.yaml` |
| soul/ | `soul/identity.md` | `/opt/viko-agent/soul/identity.md` |
| rules/ | `rules/*.md` | `/opt/viko-agent/rules/*.md` |
| skills/ | `skills/*.md` | `/opt/viko-agent/skills/*.md` |
| projects/ | `projects/<slug>/` | `/opt/viko-agent/projects/<slug>/` |
| patches/ | `patches/*.py / *.js` | `/opt/viko-agent/patches/` |

## Arsitektur Self-Modification

Viko punya dua layer file yang bisa dimodifikasi:

### Layer 1 — Runtime (`/opt/data/`, writable)
Dibaca langsung oleh Hermes setiap sesi. Perubahan langsung efektif (tanpa restart):

| File | Fungsi |
|------|--------|
| `SOUL.md` | Persona aktif — tone, gaya, nama |
| `config.yaml` | Model, provider, bahasa UI |

### Layer 2 — Source of Truth (`/opt/viko-agent/`, writable via bind mount)
Dimuat lewat `AGENTS.md` setiap sesi. Perubahan efektif di sesi berikutnya:

| Path | Fungsi |
|------|--------|
| `soul/identity.md` | Identity canon — peran, nilai inti |
| `rules/*.md` | Aturan behavior (authorization, approval, timeout) |
| `skills/*.md` | Domain knowledge per lifecycle |
| `projects/<slug>/context.md` | Context project spesifik |
| `projects/<slug>/steps.md` | SOP per project |

### Layer 3 — Build-time (`patches/`, `Dockerfile.hermes`)
Diapply saat `docker compose build hermes`. Perubahan butuh **full rebuild + redeploy**:

| File | Fungsi |
|------|--------|
| `patches/whatsapp-bridge.js` | Custom WA bridge |
| `patches/indonesian-locale.py` | Override locale Hermes |
| `patches/apply-agent-msgs.py` | Patch agent message handling |
| `Dockerfile.hermes` | Image build definition |

## Authorization untuk Self-Modification

| Perubahan | Tier | Alasan |
|-----------|------|--------|
| Edit `data/hermes/SOUL.md` (tone, gaya bicara) | Tier 2 | Aman, langsung efektif, reversible |
| Edit `skills/*.md` (domain knowledge) | Tier 2 | Low risk, bisa rollback via git |
| Edit `projects/*/context.md` atau `steps.md` | Tier 2 | Factual update, bisa rollback |
| Tambah skill file baru | Tier 2 | Additive, tidak hapus yang lama |
| Edit `soul/identity.md` (identitas inti) | Tier 3 | Mengubah siapa Viko — perlu approval |
| Edit `rules/*.md` (authorization, approval) | Tier 3 | Mengubah cara Viko beroperasi |
| Edit `data/hermes/config.yaml` (model/provider) | Tier 3 | Bisa break LLM routing |
| Edit `patches/*.py / *.js` | Tier 3 | Butuh rebuild, high risk |
| Git commit ke viko-agent | Tier 3 | Permanen di history |
| `docker compose build hermes` | Tier 3 | Rebuild butuh waktu, downtime |

## Git Workflow untuk Self-Modification

Viko bisa run git dari dalam container:

```bash
# Stage dan commit perubahan di /opt/viko-agent
git -C /opt/viko-agent add skills/new-skill.md projects/viko-agent/steps.md
git -C /opt/viko-agent commit -m "feat: tambah skill X karena Y"
```

> Push ke remote butuh credentials — Eksa yang push ke GitHub.

## Session Init untuk viko-agent Tasks

Sebelum mengerjakan task self-modification:
1. Baca file yang mau diubah terlebih dahulu
2. Identifikasi apakah perlu Tier 2 atau Tier 3
3. Kalau Tier 3: kirim approval request ke Eksa dulu
4. Kalau Tier 2: execute, lalu notify

Lihat `projects/viko-agent/steps.md` untuk panduan step-by-step per jenis perubahan.

## Team

| Name | Role |
|------|------|
| Eksa | Owner — satu-satunya yang bisa approve Tier 3 actions |
| Viko | Self-maintainer — bisa edit Layer 1 & 2 sesuai authorization |

## Notes

- Jangan modifikasi `data/hermes/` files yang bukan SOUL.md atau config.yaml tanpa Eksa
- Kalau ragu tier mana: **selalu tanya dulu**
- Setelah edit Layer 2, inform Eksa bahwa perubahan akan efektif di sesi berikutnya
- Setelah edit SOUL.md (Layer 1), perubahan langsung efektif — tidak perlu restart
