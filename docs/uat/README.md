# viko-agent — User Acceptance Testing (UAT)

## Scope

This UAT plan covers the deployed viko-agent system: Hermes-Admin, the WhatsApp
bridge (admin + relay modes), per-project Hermes containers, 9router, the 8
behavior patches, hooks, MCP servers, and the operational scripts/cron jobs
that keep the fleet running. It does **not** cover individual project app
code (that lives in each project's own repo/UAT).

Each file below is one test area with a table of cases: **ID | Precondition |
Steps | Expected Result | Pass/Fail | Notes**. Testers fill in the last two
columns during a test pass.

## Test Areas

| File | Covers |
|---|---|
| [01-onboarding-and-admin.md](01-onboarding-and-admin.md) | Hermes-Admin persona, authorization rules, full onboarding wizard |
| [02-whatsapp-bridge-and-routing.md](02-whatsapp-bridge-and-routing.md) | Bridge modes, relay-token scope gate, rate limiting, owner-priority queue, group mention gate, reconnection |
| [03-patches-and-agent-behavior.md](03-patches-and-agent-behavior.md) | The 8 behavior patches baked into the Hermes image |
| [04-hooks-mcp-and-scripts.md](04-hooks-mcp-and-scripts.md) | Event hooks, MCP tool servers, cron/ops scripts |
| [05-security-and-isolation.md](05-security-and-isolation.md) | Cross-project isolation, boot-time guard, dashboard auth, secrets handling |
| [06-deployment-and-versioning.md](06-deployment-and-versioning.md) | CI/CD pipeline, version bumps, per-project redeploy propagation |

## Environment Under Test

Fill in per test run — values come from `.env` (never copy real secrets into
this doc, reference the variable name only):

| Field | Value |
|---|---|
| Date | |
| Tester | |
| VPS / host | (e.g. `doasas` production) |
| `viko-hermes` image tag / commit | |
| `viko-9router` image tag | |
| Active project containers tested | |
| WhatsApp account used for testing | (a non-owner test number recommended for negative cases) |

## Prerequisites

- Owner WhatsApp number configured (`WHATSAPP_OWNER_NUMBER`) and paired.
- At least one **registered** project group and one **unregistered** group
  available for routing test cases.
- A second WhatsApp number (non-owner) available for negative-path testing
  (unauthorized command, non-owner DM, member message in a group).
- Dashboard credentials (`HERMES_DASHBOARD_BASIC_AUTH_*`) available to the
  tester for admin-dashboard cases.
- SSH access to the deploy VPS for container/log inspection during tests.

## Sign-off

| Area | Result | Signed off by | Date |
|---|---|---|---|
| Onboarding & Admin | | | |
| WhatsApp Bridge & Routing | | | |
| Patches & Agent Behavior | | | |
| Hooks, MCP & Scripts | | | |
| Security & Isolation | | | |
| Deployment & Versioning | | | |
