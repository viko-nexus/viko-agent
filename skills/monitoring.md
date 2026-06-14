# Skill: Monitoring

How Viko monitors CI/CD pipelines and application logs.

## What Viko Monitors

- CI/CD pipeline status (build, test, deploy stages)
- Application error logs (Docker container logs)
- Deployment health after rollout

## Error Severity Classification

| Severity | Criteria | Action |
|----------|----------|--------|
| Critical | App down, data loss risk, auth failure | Notify Eksa immediately, investigate in parallel |
| Warning | Elevated error rate, degraded performance | Investigate first, then notify with findings |
| Info | Single isolated error, non-breaking | Log to memory, no notification unless pattern detected |

## Error Detection Flow

When an error is detected in logs:

1. Classify severity (see table above)
2. For **critical** — send Tier 1 notification immediately:
   ```
   ⚠️ [Project] error in [component]
   [Error summary — 1 line]
   Investigating now.
   ```
3. Read error context and relevant source files
4. Identify root cause
5. Draft fix plan and send for approval (Tier 3)

## CI/CD Failure Flow

When a pipeline fails:

1. Read the full failure output
2. Identify the failing step and reason
3. Notify Eksa:
   ```
   ❌ [Project] CI failed — [step]: [reason]
   ```
4. Draft fix if cause is clear
5. Wait for Eksa's direction before applying

## Memory

All detected errors are proposed as memory entries:
- Type: `error`
- Content: error message, root cause (if found), resolution (if applied)
- TTL: 30 days, renewed on each recurrence
