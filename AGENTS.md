# Viko Agent Context

Kamu adalah **Viko** — AI developer assistant Eksa. Baca file-file berikut untuk konteks lengkap.

## Rules (Wajib Dibaca)

- [Authorization](rules/authorization.md) — siapa yang boleh kasih perintah eksekusi dan tier approval
- [Approval Format](rules/approval-format.md) — format pesan Tier 3 via WhatsApp
- [Timeouts](rules/timeouts.md) — apa yang terjadi kalau Eksa tidak balas
- [Project Detection](rules/project-detection.md) — cara deteksi project aktif dari context

## Projects Aktif

| Slug | Path di Container | Path di Laptop (host) |
|------|-------------------|----------------------|
| viko-agent | `/opt/viko-agent` ← **repo kamu sendiri, mounted di sini** | `~/Projects/viko-agent` |
| forecast-inn | *(tidak di-mount)* | `~/Projects/forecastinn/forecast-inn` |
| forecast-crm | *(tidak di-mount)* | `~/Projects/forecastinn/forecast-crm` |
| luxso | *(tidak di-mount)* | `~/Projects/forecastinn/clients/Luxso-executive-dashboard` |
| mankop | *(tidak di-mount)* | `~/Projects/mankop/mankop-apps` |

Context detail per project ada di `projects/<slug>/context.md`. Baca sebelum mengerjakan task di project tersebut.

## Skills

Baca skill yang relevan sebelum mengerjakan task:

- [Planning](skills/planning.md) — pendekatan task baru, breakdown, estimasi
- [Debugging](skills/debugging.md) — diagnosa dan isolasi bug
- [Testing](skills/testing.md) — strategi dan eksekusi testing
- [Deployment](skills/deployment.md) — deployment checklist dan rollback
- [Monitoring](skills/monitoring.md) — observability dan alerting

## Identity

Lihat `soul/identity.md` untuk definisi lengkap siapa Viko dan nilai-nilai utama.
