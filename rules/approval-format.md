# WhatsApp Approval Format

All Tier 3 actions require an approval message sent to Eksa via WhatsApp before execution.

## Format

```
[Action] <what Viko wants to do>
[Risk]   <consequence if something goes wrong>
[Choice] Yes / No / Postpone
```

## Rules

- Maximum 3 lines — never longer
- No technical jargon unless essential
- Focus on consequence, not implementation detail
- "Postpone" cancels the task; it can be resumed when Eksa replies later

## Examples

```
[Action] Deploy forecast-inn to staging
[Risk]   ~2 min downtime, no automatic rollback
[Choice] Yes / No / Postpone
```

```
[Action] Delete branch feature/old-auth in mankop-apps
[Risk]   Branch cannot be recovered after deletion
[Choice] Yes / No / Postpone
```

```
[Action] Push to main — forecast-crm login fix
[Risk]   Goes directly to main branch, triggers CI/CD
[Choice] Yes / No / Postpone
```

## Timeout

See `rules/timeouts.md` for what happens if Eksa does not reply.
