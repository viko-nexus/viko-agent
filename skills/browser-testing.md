# Skill: Browser Testing & Automation

Use `agent-browser` for UI testing, form filling, and web interaction. It uses
accessibility tree snapshots instead of screenshots — far fewer tokens than Playwright.

## Workflow

```bash
# 1. Start daemon (runs in background, reuse across commands)
agent-browser daemon &

# 2. Navigate to a URL
agent-browser navigate https://staging.example.com

# 3. Snapshot the page — get accessibility tree with element refs
agent-browser snapshot

# 4. Interact using refs from snapshot (@e1, @e2, etc.)
agent-browser click @e5
agent-browser type @e3 "text to type"
agent-browser select @e7 "option-value"

# 5. Re-snapshot after page changes
agent-browser snapshot

# 6. Stop daemon when done
agent-browser daemon stop
```

## When to Use

- Verify staging UI before asking Eksa to approve deploy
- Test login flows, form submissions, CRUD operations
- Check that a bug fix actually works in the browser
- Navigate multi-step flows (checkout, registration, etc.)

## When to Use Playwright Instead

Playwright MCP (already connected) is better when:
- Eksa needs a screenshot sent to WA for visual review
- Testing requires pixel-level visual comparison

## Tips

- Always `snapshot` after navigation or interaction — page state changes
- Refs (@e1, @e2) are stable per snapshot but reset on re-snapshot
- `CHROME_PATH=/usr/bin/chromium` is already set in the container
- For headless mode (no display): agent-browser works headless by default
- If a staging app is on localhost inside Docker, use the container's internal IP or host.docker.internal
