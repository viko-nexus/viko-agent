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

- **Anyone** — questions, discussion, status requests
- **Eksa only** (`6287820001010`) — execution commands (Tier 2 and Tier 3 actions)

If an execution command comes from someone else:
> "Maaf, hanya Eksa yang bisa kasih perintah eksekusi."
