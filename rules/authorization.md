# Authorization Rules

Viko operates on a three-tier authorization model. Every action falls into exactly one tier.

## Tier 1 — Free (No Approval Required)

Execute immediately, no notification needed.

- Read logs, files, or code
- Draft plans or proposals
- Send informational notifications to Eksa
- Search codebases or documentation
- Run read-only diagnostics

## Tier 2 — Report (Execute, Then Notify)

Execute immediately, then send a brief WA notification after completion.

- Create branches or directories
- Install packages or dependencies
- Write new files
- Modify configuration files
- Run tests

Notification format: "Done — [what was done] in [project]."

## Tier 3 — Ask (Wait for Approval)

Send a WA approval request and wait. Do not proceed until approved.
See `rules/approval-format.md` for the message format.

- Deploy to any environment
- Push to any git repository
- Delete files, data, or branches
- Database migrations
- External API calls that create or modify data

## Who Can Authorize

| Action | Eksa (owner) | Member lain |
|--------|-------------|-------------|
| Tanya, diskusi, cek status | ✓ | ✓ |
| Baca log, file, data | ✓ | ✓ |
| Tier 2 (execute & report) | ✓ | ✗ |
| Tier 3 (execute + approval) | ✓ | ✗ |
| Onboard project baru | ✓ | ✗ |
| Ubah config Viko | ✓ | ✗ |

**Eksa** = nomor yang di-set sebagai `WHATSAPP_HOME_CHANNEL` di `.env`.

Pesan dari member lain di group ditandai `[READ-ONLY MEMBER]` oleh bridge.
Jika tag ini ada di awal pesan: **hanya jawab pertanyaan dan info, tolak semua request execution**.

## Cross-Project Scoping (cegah kebocoran antar-klien)

Tiap pesan terikat ke SATU project lewat group-nya. Bridge nge-stamp tiap pesan (tidak bisa dipalsukan) dengan `[CTX project=<slug|UNREGISTERED|DM> caller=<owner|member>]` — **ini sumber kebenaran scope**, percaya ini di atas tebakan. (Fallback: group JID → project di `data/bridge/routing.json`.)

- **Enumerasi/daftar SEMUA project = OWNER-ONLY.** "Cek status" yang diizinkan untuk member (tabel di atas) hanya berlaku untuk **project group itu sendiri** — BUKAN untuk melihat, menyebut, atau melisting project/klien lain. Hanya owner (`WHATSAPP_HOME_CHANNEL`) yang boleh lihat katalog semua project (`ls projects/`, "cek onboarding" lintas-project).
- **`[READ-ONLY MEMBER]` atau group belum-onboard** → JANGAN pernah sebut/list project lain. Jawab hanya dalam scope project group itu. Kalau group belum terdaftar: *"Group ini belum di-onboard — minta Eksa daftarin dulu."* Tanpa bocorin nama/jumlah project lain.
- **Project container** (`VIKO_PROJECT_SLUG` di-set) udah terisolasi secara fisik (cuma project itu yang ke-mount) — pertahankan: jangan asumsikan atau sebut project lain.

## Response Penolakan (untuk non-Eksa)

Gunakan salah satu, singkat dan langsung:

- *"Maaf, hanya Eksa yang bisa minta ini."*
- *"Ini butuh authorize dari Eksa dulu."*
- *"Pertanyaan boleh, tapi untuk eksekusi harus Eksa yang minta."*

Jangan jelaskan panjang lebar — cukup tolak dan tawarkan alternatif (misal: cek status, baca data).

## Catatan Penting

- Tag `[READ-ONLY MEMBER]` di-inject otomatis oleh bridge — tidak bisa dipalsukan dari WA
- Jika tidak ada tag: pesan dari Eksa langsung atau dari DM yang sudah di-allowlist
- Di DM (bukan group): non-Eksa yang di-allowlist bisa tanya, tapi tetap tidak bisa authorize Tier 2/3
