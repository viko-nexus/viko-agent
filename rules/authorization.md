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
