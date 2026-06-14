# Skill: Self-Monitoring Viko Agent

Viko can analyze its own logs to detect errors, then send a summary to Eksa via WhatsApp.

## When to Use

- Scheduled automatically via cron every 2 hours
- Can also be triggered manually: "viko check your own logs"

---

## Step 1 — Read Logs

All logs are in `/opt/data/logs/` inside the container.

```bash
# Errors & criticals in the last 2 hours
grep -E "ERROR|CRITICAL" /opt/data/logs/errors.log | tail -50

# API/model failures in agent log
grep -E "Non-retryable|API call failed|context length exceeded|max_tokens|model_not_found" \
  /opt/data/logs/agent.log | tail -30

# Gateway crash / bridge exit
grep -E "Fatal|bridge.*exited|Shutdown.*signal" /opt/data/logs/gateway.log | tail -20

# Restart history
cat /opt/data/logs/gateway-restart.log 2>/dev/null | tail -10
```

---

## Step 2 — Classify Findings

Categorize each error into one of these levels:

| Level | Examples | Action |
|-------|----------|--------|
| 🔴 Critical | Bridge exited, gateway crash, DB corrupt | Report + suggest restart |
| 🟡 Warning | max_tokens exceeded, context loop, model fallback | Report + suggest config fix |
| ✅ Normal | SIGTERM on restart, compression summary | Ignore |

**Ignore** if all errors are normal SIGTERM/shutdown events (expected during restarts).

---

## Step 3 — Format Summary

```
🔍 *Viko Self-Check* — <date & time>

[if findings exist]
🔴 Critical:
• <error> — <brief suggestion>

🟡 Warning:
• <error> — <brief suggestion>

[if clean]
✅ All normal — no significant errors found.
```

Max 10 lines. Concise and actionable.

---

## Step 4 — Send to Eksa

```bash
# Get Eksa's JID from environment (WHATSAPP_HOME_CHANNEL in .env)
EKSA_JID=$(printenv WHATSAPP_HOME_CHANNEL)

curl -s -X POST http://localhost:3000/send \
  -H "Content-Type: application/json" \
  -d "{\"chatId\":\"$EKSA_JID\",\"message\":\"<summary from step 3>\"}"
```

Send **only if findings exist** (level 🔴 or 🟡). If all is normal, **do not send**.

---

## Rules

- Do not send a message if there are no significant findings — avoid spam
- One message per run, not per error
- If the WhatsApp bridge is not connected (`curl localhost:3000/health` → not `"connected"`),
  skip sending and log to `/tmp/monitor-skip.log`
