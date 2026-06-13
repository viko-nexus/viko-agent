# viko-agent — Self-Modification Playbook

Panduan step-by-step untuk setiap jenis perubahan. Selalu baca context.md dulu.

---

## 1. Ubah Gaya Bicara / Persona (Tier 2)

Target file: `data/hermes/SOUL.md` → langsung efektif

```
1. Baca /opt/data/SOUL.md
2. Identifikasi bagian yang mau diubah
3. Edit file langsung
4. Kirim notif ke Eksa: "Done — updated SOUL.md: [apa yang diubah]"
5. Perubahan efektif di pesan berikutnya (tidak perlu restart)
```

---

## 2. Update / Tambah Skill (Tier 2)

Target: `skills/<nama>.md` → efektif sesi berikutnya

```
1. Baca skill yang relevan di /opt/viko-agent/skills/
2. Edit atau buat file baru
3. Kalau file baru: tambahkan entry di AGENTS.md (bagian ## Skills)
4. Git commit (Tier 3 — minta approval atau inform Eksa)
5. Kirim notif: "Done — updated skills/debugging.md: [apa yang diubah]"
```

---

## 3. Update Project Context (Tier 2)

Target: `projects/<slug>/context.md` atau `steps.md`

```
1. Baca file context yang mau diupdate
2. Edit langsung — paths, team, notes, SOP
3. Kirim notif: "Done — updated projects/forecast-inn/context.md: [apa yang diubah]"
4. Info: "Perubahan efektif di sesi berikutnya"
```

---

## 4. Ubah Rules / Authorization (Tier 3)

Target: `rules/*.md` — **wajib approval Eksa**

```
1. Draft perubahan yang diinginkan
2. Kirim WA approval request ke Eksa (format sesuai rules/approval-format.md):
   "⚙️ viko-agent · rules/authorization.md
    Mau tambah rule: [deskripsi]
    Alasan: [mengapa diperlukan]
    ✅ Setuju / ❌ Tolak"
3. Tunggu approval
4. Setelah disetujui: edit file, git commit, notify
```

---

## 5. Ubah Identity Canon (Tier 3)

Target: `soul/identity.md` — **wajib approval Eksa**

```
1. Draft perubahan identitas
2. Kirim approval request ke Eksa
3. Setelah disetujui: edit soul/identity.md
4. Update data/hermes/SOUL.md juga kalau perlu sinkronisasi
5. Git commit + notify
```

---

## 6. Ubah Config (Model, Provider) (Tier 3)

Target: `data/hermes/config.yaml`

```
1. Baca config saat ini: /opt/data/config.yaml
2. Kirim approval request ke Eksa
3. Setelah disetujui: edit config.yaml
4. Restart gateway: s6-svc -t /run/service/gateway
   atau: hermes restart (jika tersedia)
5. Verify: cek log bahwa LLM provider aktif
6. Notify: "Done — config.yaml updated, gateway restarted"
```

---

## 7. Ubah Patch atau Dockerfile (Tier 3 + Rebuild)

Target: `patches/*.py`, `patches/*.js`, `Dockerfile.hermes`

```
1. Identifikasi patch yang perlu diubah
2. Kirim approval request ke Eksa — sertakan:
   - File yang diubah
   - Apa yang diubah dan kenapa
   - Estimasi downtime (biasanya 5-10 menit rebuild)
3. Setelah disetujui: edit file di /opt/viko-agent/patches/
4. Inform Eksa untuk rebuild:
   "Silakan run: docker compose build hermes && docker compose --profile full up -d"
5. Setelah online kembali: verify perubahan berjalan
```

---

## 8. Tambah Project Baru (Tier 2)

```
1. Buat direktori: projects/<slug>/
2. Buat context.md dengan format standar (lihat projects/forecast-inn/context.md)
3. Buat steps.md kosong (bisa diisi bertahap)
4. Tambahkan entry di AGENTS.md (## Projects Aktif table)
5. Notify Eksa: "Done — added project context for [slug]"
```

---

## Rollback

Kalau ada perubahan yang salah di Layer 2 (repo files):

```bash
# Lihat perubahan terakhir
git -C /opt/viko-agent log --oneline -5

# Revert file spesifik
git -C /opt/viko-agent checkout HEAD -- rules/authorization.md

# Revert commit terakhir (hati-hati)
git -C /opt/viko-agent revert HEAD
```

Untuk SOUL.md (Layer 1): baca isi dan edit manual, atau copy dari soul/identity.md.
