# Skill: Testing

How Viko runs tests and E2E testing.

## Test Types and Authorization

| Type | Tier | Notification |
|------|------|-------------|
| Unit tests | Tier 2 | Report result after run |
| Integration tests | Tier 2 | Report result; notify on failure |
| E2E tests | Tier 2 | Report result; attach screenshot on failure |

## Running Tests

Tests are Tier 2 — execute and report result:

Pass: `"Done — tests passed (47/47) in forecast-inn."`
Fail: `"Done — 3 tests failed in forecast-inn. Detail menyusul."`

## E2E Testing with Agent Browser

For browser-based E2E testing, use `agent-browser` (see `.claude/skills/agent-browser.md`).

Standard flow:
```
1. agent-browser open <target-url>
2. agent-browser snapshot -i        # see the page
3. [execute test steps]
4. agent-browser screenshot         # capture state on failure
5. agent-browser close
```

## Test Failure Handling

1. Capture full failure details (error message, stack trace, screenshot if E2E)
2. Notify Eksa:
   ```
   ⚠️ [Project] test gagal — [test name]
   [Error summary — 1 line]
   ```
3. Draft a fix plan if root cause is clear (see `skills/debugging.md`)
4. Wait for Eksa's direction before applying the fix

## Notes

- Do not skip failing tests — always investigate and report
- Screenshot on every E2E failure for faster debugging
- Propose memory entry for recurring test failures
