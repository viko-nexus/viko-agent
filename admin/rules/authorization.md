# Authorization — Hermes-Admin

## Who Can Give Commands

Only the system owner — configured via the `WHATSAPP_OWNER_NUMBER` environment variable.
This is set at deploy time and never hardcoded.

If `WHATSAPP_OWNER_NUMBER` is empty or unset, no commands are processed and a startup
warning is logged.

---

## In Group Messages

Routing check happens before any LLM processing (at bridge code layer):

```
Incoming group message
    │
    ├── Group JID in routing.json?
    │       YES → forward to Hermes-Project, Admin is blind (no LLM invoked)
    │       NO  ↓
    │
    ├── Sender == WHATSAPP_OWNER_NUMBER?
    │       YES → pass to Admin LLM
    │       NO  → ignore silently (no response)
```

There is no condition under which Admin responds to a registered group.
No exceptions — not for re-onboard commands, not for config questions.

---

## In Direct Messages (DMs)

Admin can respond in DMs, but only provides general info:
- What Viko is
- How to onboard a project
- Status of a recent onboard attempt

DMs from non-owners: brief, non-technical response only. No commands executed.
> "Gue cuma bisa bantu owner setup project baru. Untuk bantuan lainnya, tanya di grup project-nya ya."

---

## Valid Owner Commands

Onboarding is owner-only. Owner mulai dengan `onboard` (wizard percakapan) atau
shortcut one-liner. Hanya `slug` + `github` yang wajib; server/SSH user opsional
(tanpa server = project jalan lokal tanpa SSH); members opsional (default dibaca
dari anggota grup).

Prosedur lengkap (langkah wizard, validasi, eksekusi) ada di
`admin/skills/onboarding.md`.

Everything else from non-owners: ignore silently.

---

## Sender Validation

Sender phone is read from WA protocol metadata (from the bridge layer),
not from message text. This cannot be spoofed by writing a phone number in
the message content.
