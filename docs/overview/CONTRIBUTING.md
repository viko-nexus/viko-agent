# Contributing

## Before You Start

Read [ARCHITECTURE.md](ARCHITECTURE.md) and [DEVELOPMENT.md](DEVELOPMENT.md) first.
Understand the isolation model and security rules — they are non-negotiable.

---

## What Contributions Are Welcome

- Bug fixes (bridge, patches, scripts)
- New Hermes patches (model routing, isolation, approval flow improvements)
- Documentation improvements
- New MCP server implementations
- Performance improvements in the Docker build

## What Is Not Accepted

- Hardcoded phone numbers, group JIDs, or project-specific values
- Changes that weaken the relay token scope check or isolation guard
- Runtime package installs (`apt`, `pip`, `npm`) inside containers
- Comments or code in languages other than English

---

## Contribution Workflow

1. Fork the repository and create a branch: `git checkout -b feat/my-change`
2. Make changes, following the conventions below
3. Run lint: `ruff check scripts/ patches/ mcp-servers/`
4. Test locally (see [DEVELOPMENT.md](DEVELOPMENT.md))
5. Commit with a clear message (English, under 120 chars)
6. Open a pull request against `main`

---

## Code Conventions

**All code and comments must be in English.**

Python:
- `ruff check` must pass with no errors
- Use `Path(__file__).parent.parent.resolve()` for repo root — never hardcode paths
- Type hints optional but encouraged for function signatures
- No print statements except in scripts meant to be run manually

JavaScript (bridge/):
- ES module syntax (`import`/`export`)
- `node --check` must pass
- JSDoc comments on exported functions

Dockerfile:
- Comments must explain WHY a layer exists, not WHAT the command does
- Keep Viko-specific layers (patches) at the end — they change most often

---

## Commit Message Format

```
<type>(<scope>): <short description>

[optional body]
```

Types: `feat`, `fix`, `docs`, `security`, `chore`, `refactor`

Examples:
```
feat(bridge): add relay token rotation support
fix(patches): handle missing VIKO_PROJECT_SLUG gracefully
security(isolation): fail-closed when HERMES_HOME is unset
docs(overview): update deployment guide for Traefik setup
```

---

## Pull Request Checklist

- [ ] All code and comments in English
- [ ] No hardcoded phone numbers, JIDs, or project slugs
- [ ] `ruff check` passes on any modified Python files
- [ ] `node --check` passes on any modified JavaScript files
- [ ] Tested locally (build passes, bridge responds, Hermes starts)
- [ ] Security rules from [AGENTS.md](../../AGENTS.md) not broken
- [ ] `docs/overview/` updated if architecture or deployment changed

---

## Security Issues

Do not open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md).
