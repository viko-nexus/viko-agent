# SSH Execution — How to Connect to Production Servers

## The Right Tool

Always use the `ssh_exec` MCP tool. Never use raw `ssh` commands or try to run `docker compose logs` locally — Viko's container does not have Docker.

```
ssh_exec(project="luxso", command="docker compose logs backend | tail -100")
ssh_exec(project="mankop", command="systemctl status app")
ssh_exec(project="forecastinn", command="df -h")
```

Available projects: `mankop`, `forecastinn`, `luxso`, `forecastcrm`

---

## When `ssh_exec` Fails — Self-Diagnosis Steps

Do NOT stop and report failure immediately. Run through this checklist first.

### Step 1 — Try `ssh_exec`, note the exact error

```python
ssh_exec(project="luxso", command="echo test")
```

If it succeeds: done. If it fails, move to Step 2.

### Step 2 — Test SSH directly via terminal

Use the terminal tool (not MCP) to test raw SSH:

```bash
ssh -v -o ConnectTimeout=10 -o StrictHostKeyChecking=no luxso-prod "echo test" 2>&1
```

### Step 3 — Interpret the error

| Error message | Meaning | What to do |
|---------------|---------|------------|
| `Could not resolve hostname luxso-prod` | SSH config not found or alias missing | Check `/opt/data/.ssh/config` exists and has the alias |
| `Connection refused` | SSH daemon down or wrong port | Scan for actual port (see Port Scanning below) |
| `Connection timed out` | Server unreachable / firewall | Try a different port, check if server is up |
| `Permission denied (publickey)` | Wrong key or wrong user | Check `IdentityFile` in SSH config, check username |
| `no such identity: /root/.ssh/id_rsa_...` | Key not found at expected path | Check `/opt/data/.ssh/` for the key file |
| `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED` | Server fingerprint changed | Run: `ssh-keygen -R <IP>` or update known_hosts |

---

## SSH Config Location (Read-Only)

The SSH config inside Viko's container is mounted read-only from the host:

```
/opt/data/.ssh/config    ← same as host's ~/.ssh/config
/opt/data/.ssh/id_rsa_*  ← same as host's ~/.ssh/id_rsa_*
```

**Viko cannot edit these files.** To update the SSH config, tell Eksa exactly what to change on the host machine (in `~/.ssh/config`).

To verify the current config:
```bash
cat /opt/data/.ssh/config
ls /opt/data/.ssh/
```

---

## Port Scanning — Finding the Right SSH Port

If `Connection refused` on port 22, scan for the actual SSH port:

```bash
for port in 22 2222 2200 8022 22022 222; do
  timeout 5 bash -c "echo >/dev/tcp/217.216.108.88/$port" 2>/dev/null && echo "Port $port OPEN" || echo "Port $port closed"
done
```

Replace IP with the actual server IP from the SSH config.

If a non-22 port is open, tell Eksa:
> "SSH is on port XXXX for luxso-prod. Update `~/.ssh/config`: change `Port 22` to `Port XXXX` for Host luxso-prod."

---

## Diagnosing `ssh_exec` MCP Tool Issues

If `ssh_exec` itself errors (not an SSH error, but MCP errors):

```bash
# Check MCP server is running
ps aux | grep projects-gateway

# Check MCP server logs (if any)
cat /tmp/projects-gateway*.log 2>/dev/null || echo "no log file"

# Test MCP directly
/opt/hermes/.venv/bin/python3 /opt/data/mcp-servers/projects-gateway.py --help 2>&1 | head -5
```

---

## Server Reference

| Project | SSH Alias | Server IP | SSH User |
|---------|-----------|-----------|----------|
| mankop | `mankop-prod` | 69.62.81.224 | `mankop-app` |
| forecastinn | `forecastinn-prod` | 217.216.108.88 | `deploy` |
| luxso | `luxso-prod` | 217.216.108.88 | `deploy` |
| forecastcrm | `forecastcrm-prod` | 69.62.81.224 | — |

---

## Complete Debug Flow (Copy-Paste)

When asked to SSH and it fails, run this entire sequence and report findings:

```bash
# 1. Check SSH config exists
echo "=== SSH Config ===" && cat /opt/data/.ssh/config | grep -A6 "luxso-prod"

# 2. Check key exists
echo "=== Keys ===" && ls /opt/data/.ssh/id_rsa_*

# 3. Test connection with verbose
echo "=== SSH Test ===" && ssh -v -o ConnectTimeout=10 -o BatchMode=yes luxso-prod "echo OK" 2>&1

# 4. If connection refused, scan ports
echo "=== Port Scan ===" && for p in 22 2222 2200; do timeout 5 bash -c "echo >/dev/tcp/217.216.108.88/$p" 2>/dev/null && echo "Port $p: OPEN" || echo "Port $p: closed"; done
```

Report all output to Eksa with a clear diagnosis and the exact change needed (if any).
