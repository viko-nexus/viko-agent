# WhatsApp Approval Format

All Tier 3 actions require an approval message sent to Eksa via WhatsApp before execution.

## Format

```
[Action] <what Viko wants to do>
[Risk]   <consequence if something goes wrong>
[Choice] Ya / Tidak / Tunda
```

## Rules

- Maximum 3 lines — never longer
- No technical jargon unless essential
- Focus on consequence, not implementation detail
- "Tunda" cancels the task; it can be resumed when Eksa replies later

## Examples

```
[Action] Deploy forecast-inn ke staging
[Risk]   Downtime ~2 menit, tidak ada rollback otomatis
[Choice] Ya / Tidak / Tunda
```

```
[Action] Hapus branch feature/old-auth di mankop-apps
[Risk]   Branch tidak bisa dikembalikan setelah dihapus
[Choice] Ya / Tidak / Tunda
```

```
[Action] Push ke main — forecast-crm login fix
[Risk]   Langsung masuk main branch, trigger CI/CD
[Choice] Ya / Tidak / Tunda
```

## Timeout

See `rules/timeouts.md` for what happens if Eksa does not reply.
