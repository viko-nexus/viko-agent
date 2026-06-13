# Skill: Planning

How Viko creates plans for tasks.

## When to Use

- User requests a new feature, task, or change
- An error or bug requires investigation before fixing
- Before any significant code change that affects multiple files

## Process

1. Read the active project context (`projects/<name>/context.md`)
2. Read existing code or documentation relevant to the task
3. Draft a plan with: goal, steps, dependencies, risks
4. Propose memory entry if a significant decision is being made
5. Send plan to Eksa for review — wait for approval before executing

## Plan Format

```markdown
## Goal
[What we're trying to achieve and why]

## Steps
1. [Step — expected outcome]
2. [Step — expected outcome]
...

## Dependencies
- [What must be in place before starting]

## Risks
- [What could go wrong — and how to mitigate]

## Estimated Scope
[Files affected, rough time estimate]
```

## Storage

- Plans are saved to `projects/<name>/plans/YYYY-MM-DD-<slug>.md` after approval
- Plans reference specific file paths and line numbers where possible
- Never execute a plan without Eksa's approval (Tier 3)
