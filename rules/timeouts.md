# Timeout Rules

## WhatsApp Approval Timeout

- Default timeout: **30 minutes** from when the approval message is sent
- On timeout: task is **cancelled** — no partial execution
- Task state is preserved — Eksa can resume by replying to the original message
- Viko will not re-send or re-attempt without a reply

## Task Resumption

When Eksa replies to a timed-out approval message:

1. Viko confirms it understood the reply (Ya / Tidak / Tunda)
2. **Ya** — Viko re-executes from the cancelled point, not from the beginning
3. **Tidak** — task is permanently cancelled
4. **Tunda** — task is queued; Viko will not re-ask unprompted

## Non-Pausable Tasks

Some tasks cannot be safely interrupted mid-execution (e.g., live database migrations,
production deployments). These must be flagged clearly in the approval message:

```
[Action] Migrate database mankop ke production
[Risk]   Tidak bisa di-pause — kalau tidak balas 30 menit, seluruh proses dibatalkan
[Choice] Ya / Tidak / Tunda
```

## Stateful Requirement

All tasks must be designed as resumable. Viko must always know:
- What has already been executed
- What still needs to be executed
- What to undo if cancelled mid-way
