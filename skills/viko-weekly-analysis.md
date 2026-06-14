# Viko Weekly Analysis — Self-Improvement Cron

This skill runs every Monday 09:00 (Asia/Makassar). The data from the past 7 days is already injected into the prompt by the collection script.

## Your Job

Analyze the data, create Kanban tickets on the `viko-agent` board, then send a WhatsApp summary to Eksa.

---

## Step 1 — Analyze the Data

Look for signals across 4 dimensions:

### Cost
- Weekly total vs previous week (% change)
- Days with abnormal cost spikes (>2× daily average)
- Model mix: is Haiku being used for simple tasks? Are complex tasks hitting Sonnet?

### Error Rate
- `usageHistory` errors: anything with status not `ok`/`success`
- `requestDetails` failed count per day
- `hermes_log_sample`: look for repeated error patterns (SSH failures, tool errors, timeouts)

### Response Time
- Average latency per day — flag if avg > 5000ms
- Max latency — flag if any day has >30s (30000ms) outlier
- TTFT (time-to-first-token) anomalies if visible

### Usage Patterns
- Request volume trend (growing, stable, dropping?)
- Model routing: % Sonnet vs Haiku — is the router working as intended?
- Any unusual spikes in a specific day/time

---

## Step 2 — Generate Tickets

Create 2–5 tickets. Each ticket must be actionable — not just an observation.

### For each ticket, decide the type:

**AUTO-APPROVE** (create as normal `todo` status — Viko executes without asking Eksa):
- Update documentation (SOUL.md, AGENTS.md, skill files)
- Delete old log files (`/opt/data/logs/` older than 30 days)
- Update SOUL.md with a newly learned pattern or correction

**NEEDS EKSA REVIEW** (create as `blocked` status — wait for Eksa's approval):
- Anything touching config.yaml, docker-compose.yml, patches/
- Cost optimization changes
- New features or architectural changes
- Investigation tasks requiring production server access

### How to create a ticket:

```bash
export PATH="/opt/hermes/bin:$PATH"

# Auto-approve ticket (dispatched immediately):
hermes kanban --board viko-agent create \
  "[Type] Title of the ticket" \
  --body "**Evidence:** <data or log excerpt>\n\n**Action:** <exact steps Viko will take>\n\n**Expected outcome:** <what improves>"

# Needs-review ticket (blocked until Eksa approves):
hermes kanban --board viko-agent create \
  "[Type] Title of the ticket" \
  --body "**Evidence:** <data or log excerpt>\n\n**Action:** <exact steps Viko will take>\n\n**Expected outcome:** <what improves>\n\n⏳ Waiting for Eksa's approval. Unblock this ticket in the dashboard to execute." \
  --initial-status blocked
```

Types to use in title: `[Bug]`, `[Cost]`, `[Perf]`, `[Improvement]`, `[Investigation]`

---

## Step 3 — Send WhatsApp Summary to Eksa

After creating all tickets, send a WhatsApp message using the bridge:

```python
import json, urllib.request, os

home_channel = os.environ.get("WHATSAPP_HOME_CHANNEL", "")
message = """YOUR_SUMMARY_HERE"""

payload = json.dumps({"chatId": home_channel, "message": message}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:3000/send",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=10)
```

### WhatsApp message format (keep under 15 lines):

```
📊 *Weekly Viko Report* (DD–DD Mon)

Cost: $XX.XX (+/-X% vs minggu lalu)
Requests: X,XXX | Error rate: X.X%
Avg latency: X.Xs | Sonnet XX% / Haiku XX%

Tickets dibuat:
• [Bug] SSH timeout errors (X kasus) — needs review
• [Cost] Spike Selasa 18 Jun — needs review  
• [Improvement] Hapus log lama — auto-approved ✅

Review: http://localhost:9119
```

Use ✅ for auto-approved tickets, ⏳ for tickets awaiting Eksa's review.

---

## Step 4 — Final Output

After sending the WA, output a short confirmation:
> "Weekly analysis done. X tickets created on viko-agent board. Summary sent to Eksa via WhatsApp."

---

## Error Handling

If the injected data contains `"error"` key:
- Report what went wrong (e.g., "9router DB not found")
- Skip ticket creation
- Still send WA to Eksa: "Weekly analysis failed: [error message]. Please check."

If the data is empty (no requests in last 7 days):
- Create one `[Investigation]` ticket: "No traffic recorded this week — verify 9router is running"
- Notify Eksa
