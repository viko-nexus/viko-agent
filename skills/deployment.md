# Skill: Deployment

How Viko handles deployments.

## Authorization

All deployments are **Tier 3** — always require Eksa's explicit approval before proceeding.
See `rules/approval-format.md` for the message format.

## Pre-Deployment Checklist

Before sending the approval request, verify:

1. All tests pass (run them if not already done)
2. No uncommitted changes in the working directory
3. Branch is up to date with the base branch
4. No known critical bugs in the current state

## Deployment Steps

1. Run pre-deployment checklist — abort if anything fails
2. Send Tier 3 approval request to Eksa
3. Wait for approval — do not proceed on timeout (see `rules/timeouts.md`)
4. On approval: execute deployment
5. Monitor logs for at least 5 minutes after deployment
6. Send result notification: success or failure with details

## Post-Deployment Notification

Success:
```
✅ [Project] deployed ke [env] — selesai
```

Failure:
```
❌ [Project] deploy gagal — [error summary]
Rollback? Ya / Tidak
```

## Rollback

- If deployment fails: notify Eksa immediately with error details
- Rollback requires Eksa's explicit approval (Tier 3)
- Never auto-rollback without asking

## Environment Notes

Each project defines its own deployment targets in `projects/<name>/steps.md`.
