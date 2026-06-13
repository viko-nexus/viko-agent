# Skill: Debugging

How Viko handles errors and bugs.

## When to Use

- Error appears in logs or CI/CD output
- A test fails unexpectedly
- User reports unexpected behavior
- Monitoring detects an anomaly (see `skills/monitoring.md`)

## Process

1. Read the full error message — do not assume the cause from the first line
2. Locate the relevant code files (never from memory alone — always read the actual file)
3. Identify the root cause, not just the symptom
4. Draft a fix plan using `skills/planning.md`
5. If error is in production: notify Eksa immediately (Tier 1 — informational)
6. Execute fix per the authorization tier (see `rules/authorization.md`)

## Auto-Detected Error Flow

When Viko detects an error in monitored logs:

1. Send informational WA (Tier 1):
   ```
   ⚠️ [Project] error di [component]
   [Error summary — 1 line]
   Saya investigasi sekarang.
   ```
2. Read relevant source files and logs
3. Identify root cause
4. Draft fix plan and send to Eksa for approval (Tier 3)

## Rules

- Never guess at a fix without reading the actual code
- Always document root cause — not just the fix
- If the same error has appeared before, check memory for prior resolution
- Propose a memory entry for each new error pattern resolved
