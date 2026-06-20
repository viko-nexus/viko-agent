# Security

## Security Model

viko-agent is designed around the principle that **the AI cannot be trusted to enforce
security on its own**. All critical security boundaries are enforced at the code layer
(the bridge and isolation guard), not by LLM behavior or prompting.

---

## Trust Boundaries

### Owner Authentication

The `WHATSAPP_OWNER_NUMBER` environment variable is the root of all trust. Only messages from
this WhatsApp number can trigger commands. This check happens in the bridge code
before the LLM is ever invoked:

```
Message arrives → bridge checks sender == WHATSAPP_OWNER_NUMBER → PASS or SILENT IGNORE
```

`WHATSAPP_OWNER_NUMBER` is never hardcoded in committed code. It is set at deploy time via
environment variable, making the system self-hostable without exposing credentials.

### Project Isolation

Each Hermes-Project container can only:
1. Send WhatsApp messages to its own registered group (enforced by relay token)
2. Read files in its own `/home/deploy/{slug}/config/` directory
3. Access the deploy VPS for its own project via its own SSH key

The **relay token** is the cryptographic enforcement layer. It is a 64-character
hex token stored in `routing.json`, unique per project. The bridge validates this
token on every outbound send — no token, no send.

### Bridge CTX Stamping

The bridge stamps `[CTX project=slug caller=owner|member]` on every message it
routes. This stamp:
- Is injected by the bridge at the code layer (cannot be spoofed by the LLM)
- Allows Admin to know which project and which sender type sent a message
- Is stripped before sending back to WhatsApp (users don't see it)

### Isolation Guard

`patches/isolation-guard.py` runs at container startup before Hermes initializes.
It verifies:
- `VIKO_PROJECT_SLUG` is set and non-empty
- `HERMES_HOME` path is scoped to the correct slug
- No cross-project SSH key access is possible
- `VIKO_ISOLATION_GUARD=enforce` → container goes inert on failure (no gateway start)
- `VIKO_ISOLATION_GUARD=warn` → logs warning but continues (default during initial rollout)

---

## Sensitive Data

| Data | Location | Protection |
|------|----------|------------|
| API keys | `.env` | gitignored, provisioned via CI secrets |
| WA session files | `data/hermes/` | gitignored, bind-mounted |
| Per-project DB credentials | `/home/deploy/{slug}/config/project.json` | mode 600, not in env vars |
| Relay tokens | `data/bridge/routing.json` | gitignored, unique per project |
| Deploy SSH keys | `/home/deploy/{slug}/.ssh/id_ed25519` | mode 600, gitignored |
| 9router data | `data/9router/` | gitignored, not exposed externally |

**Never commit:**
- `.env` files
- WhatsApp session directories
- `routing.json`
- API keys or tokens
- Phone numbers (including owner number)
- WhatsApp group JIDs

---

## Known Limitations

- WhatsApp session is tied to one phone number. If that number is banned or the
  session expires, the entire system goes offline.
- 9router is currently exposed on loopback only (`VIKO_BIND_ADDR=127.0.0.1`).
  Do not expose it publicly without authentication.
- The `warn` mode of isolation-guard allows a misconfigured container to start.
  Set `VIKO_ISOLATION_GUARD=enforce` in production after verifying correct setup.

---

## Responsible Disclosure

If you discover a security vulnerability, please report it privately:

**Email**: eksant@gmail.com  
**Subject**: `[viko-agent] Security disclosure`

Please include:
- Description of the vulnerability
- Steps to reproduce
- Affected versions or components
- Suggested fix (if known)

We aim to respond within 48 hours and will credit researchers in the changelog.
Do not open public GitHub issues for security vulnerabilities.
