## Type of Change

- [ ] Bug fix (bridge, patches, scripts)
- [ ] New Hermes patch
- [ ] New MCP server
- [ ] Documentation update
- [ ] CI/CD improvement
- [ ] Security fix
- [ ] Chore / refactor

## Summary

<!-- What does this PR change and why? -->

## Security Checklist

- [ ] No hardcoded phone numbers, group JIDs, or project slugs in committed files
- [ ] `OWNER_WA` only comes from env var
- [ ] Relay token scope check in `patches/whatsapp-bridge.js` not bypassed
- [ ] Isolation guard in `patches/isolation-guard.py` not weakened
- [ ] No deployment-specific values committed (channel_prompts, routing entries)
- [ ] No sensitive files committed (`.env`, `data/`, `backups/`, `projects/*/`)

## Code Quality

- [ ] `ruff check scripts/ patches/ mcp-servers/` passes (if Python files changed)
- [ ] `node --check bridge/*.js` passes (if JS files changed)
- [ ] All comments and code in English

## Testing

- [ ] Tested locally (docker compose build hermes runs without error)
- [ ] Bridge responds to health check: `curl http://localhost:3000/health`
- [ ] Onboarding dry-run passes (if scripts changed)

## Docs

- [ ] `docs/overview/` updated if architecture or deployment changed
- [ ] `AGENTS.md` updated if container naming or security rules changed
