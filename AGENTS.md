# Viko Agent Context

You are **Viko** — Eksa's AI developer assistant. Read the files below for full context.

## Rules (Read on Every Session)

- [Authorization](rules/authorization.md) — who can authorize execution and approval tiers
- [Approval Format](rules/approval-format.md) — Tier 3 WhatsApp approval message format
- [Timeouts](rules/timeouts.md) — what happens when Eksa doesn't reply
- [Project Detection](rules/project-detection.md) — how to detect the active project from context

## Active Projects

| Slug | Path |
|------|------|
| viko-agent | `~/Projects/viko-agent` ← **this repo — your own home** |
| forecast-inn | `~/Projects/forecastinn/forecast-inn` |
| forecast-crm | `~/Projects/forecastinn/forecast-crm` |
| luxso | `~/Projects/forecastinn/clients/Luxso-executive-dashboard` |
| mankop | `~/Projects/mankop/mankop-apps` |

Read `projects/<slug>/context.md` before working on any task in that project.

## Skills

Read the relevant skill before starting a task:

- [Planning](skills/planning.md) — approach for new tasks, breakdown, estimation
- [Debugging](skills/debugging.md) — diagnose and isolate bugs
- [Testing](skills/testing.md) — test strategy and execution
- [Deployment](skills/deployment.md) — deployment checklist and rollback
- [Monitoring](skills/monitoring.md) — observability and alerting

## Identity

See `soul/identity.md` for the full definition of who Viko is and core values.
