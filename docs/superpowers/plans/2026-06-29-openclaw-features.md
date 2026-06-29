# OpenClaw-Inspired Agent Features for viko-agent

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port four high-value OpenClaw concepts into viko-agent: session summarization before prune (dreaming), inferred follow-up commitments, tool call repair, and in-context tool result pruning — all without touching hermes core except via the existing patch mechanism.

**Architecture:** Tasks 1–2 are pure viko layer (scripts, hooks). Tasks 3–5 are build-time hermes patches following the exact same pattern as existing `patches/patch-*.py` files — they inject code at known injection points without modifying hermes source on disk permanently.

**Dependencies:** Implement `2026-06-29-viko-infrastructure.md` first (especially Task 1 — hermes pinning — and Task 6 — cron setup). This plan's Task 2 adds a `deliver-commitments.py` entry to the same crontab that Task 6 in the infrastructure plan installs.

**Tech Stack:** Python 3.13 (scripts, hooks, patches), Node.js (bridge — read only for context), OpenAI-compatible API via `OPENAI_BASE_URL` (9router), Docker exec for hermes source investigation

## Global Constraints
- All LLM calls in scripts use `OPENAI_BASE_URL` + `OPENAI_API_KEY` from env (9router, not hardcoded endpoint)
- All patches must be idempotent — marker string check at top, `sys.exit(0)` if already applied
- Hook handlers must be async and follow the `handle(event_type, context)` signature
- Never write credentials or JIDs into committed files
- Run docker commands from `/home/deploy/viko-agent/` on the server (SSH alias: `doasas`)

---

### Task 1: Dreaming — summarize sessions before prune

**Files:**
- Create: `scripts/dream-sessions.py` — LLM summarization of idle sessions
- Modify: `scripts/prune-idle-sessions.py` — call dream-sessions before pruning

**Why this matters:** Idle sessions are pruned hourly (infrastructure plan Task 6). Without this, every completed conversation is lost permanently. Dreaming extracts key decisions, tasks done, and open items into the project's `context.md` before the session is deleted.

**Interfaces:**
- `dream_session(slug, sessions_file, session_key, session_data)` → writes a paragraph to `data/hermes-{slug}/context.md`
- Uses `OPENAI_BASE_URL` and `OPENAI_API_KEY` env vars (same as 9router)
- Produces: `context.md` per project gets a timestamped append after each pruned session with meaningful content

- [x] **Step 1: Understand sessions.json structure**

```bash
ssh doasas "
  # Find a sessions.json with actual content
  find /home/deploy/viko-agent/data -name 'sessions.json' -size +1k | head -3 | xargs -I{} sh -c 'echo \"=== {} ===\"; python3 -c \"import json; d=json.load(open(\\\"{}\\\"))); k=list(d.keys())[0]; s=d[k]; print(list(s.keys()))\"'
"
```

Expected: shows session fields like `['messages', 'updated_at', 'created_at', ...]`. Note the exact field name for conversation history (likely `messages` or `history`).

- [x] **Step 2: Create scripts/dream-sessions.py**

```python
#!/usr/bin/env python3
"""Summarize idle Hermes sessions into project context before they are pruned.

Called by prune-idle-sessions.py before deleting sessions.
Appends a concise summary paragraph to data/hermes-{slug}/context.md.

Uses 9router (OPENAI_BASE_URL + OPENAI_API_KEY) with haiku-class model.
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path("/home/deploy/viko-agent/data")
MODEL = "viko-chat"  # haiku-class — cheap, fast


def _llm_summarize(messages: list[dict]) -> str | None:
    """Call 9router to summarize a conversation. Returns None on failure."""
    base_url = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not base_url or not api_key:
        return None

    # Build a condensed transcript (skip very short exchanges)
    transcript_parts = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "") or ""
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
            )
        content = str(content).strip()[:500]  # truncate long turns
        if role in ("user", "assistant") and content:
            label = "User" if role == "user" else "Agent"
            transcript_parts.append(f"{label}: {content}")

    if len(transcript_parts) < 2:
        return None

    transcript = "\n".join(transcript_parts[-40:])  # last 40 turns max

    prompt = (
        "Berikut adalah percakapan antara user dan AI agent (Viko). "
        "Tulis ringkasan singkat dalam 2-3 kalimat Bahasa Indonesia: "
        "apa yang diminta, apa yang dikerjakan, dan apakah ada tindak lanjut yang masih terbuka. "
        "Langsung ke inti, tanpa basa-basi.\n\n"
        f"---\n{transcript}\n---"
    )

    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.3,
    }).encode()

    try:
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [dream] LLM call failed: {e}")
        return None


def dream_session(slug: str, sessions_file: Path, session_key: str, session_data: dict) -> bool:
    """Summarize one session and append to context.md. Returns True on success."""
    messages = session_data.get("messages") or session_data.get("history") or []
    if not messages:
        return False

    summary = _llm_summarize(messages)
    if not summary:
        return False

    context_file = DATA_ROOT / f"hermes-{slug}" / "context.md"
    context_file.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"\n### Session {now} (session: {session_key[-12:]})\n{summary}\n"

    with context_file.open("a", encoding="utf-8") as f:
        f.write(entry)

    print(f"  [dream] → context.md updated ({len(summary)} chars)")
    return True
```

- [x] **Step 3: Verify the LLM endpoint is reachable**

```bash
ssh doasas "
  source /home/deploy/viko-agent/.env
  curl -s -X POST \"\$OPENAI_BASE_URL/chat/completions\" \
    -H 'Content-Type: application/json' \
    -H \"Authorization: Bearer \$OPENAI_API_KEY\" \
    -d '{\"model\":\"viko-chat\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":5}' \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[\"choices\"][0][\"message\"][\"content\"])'
"
```

Expected: short response (any text). If this fails, check 9router is running.

- [x] **Step 4: Integrate dream_session into prune-idle-sessions.py**

In `scripts/prune-idle-sessions.py`, at the top add the import:

```python
from pathlib import Path
import sys

# Add repo root to path so dream_sessions can be imported
sys.path.insert(0, str(Path(__file__).parent))
try:
    from dream_sessions import dream_session
    _DREAMING_AVAILABLE = True
except ImportError:
    _DREAMING_AVAILABLE = False
```

In `prune_project()`, just before writing the pruned session file, add the dream call per pruned session:

```python
    if pruned:
        if not dry_run:
            # Dream (summarize) each session before deleting it
            if _DREAMING_AVAILABLE:
                slug = sessions_file.parts[-3].removeprefix("hermes-")
                for key, _ in pruned:
                    session_data = data.get(key, {})
                    dream_session(slug, sessions_file, key, session_data)

            # Backup dulu
            backup = sessions_file.with_suffix(".json.bak")
```

Note: `dream_sessions` must be importable as `dream_sessions` not `dream-sessions` — name the file without hyphen.

- [x] **Step 5: Rename file to use underscore**

```bash
mv scripts/dream-sessions.py scripts/dream_sessions.py
git mv scripts/dream-sessions.py scripts/dream_sessions.py 2>/dev/null || true
```

- [x] **Step 6: Dry-run test**

```bash
ssh doasas "
  source /home/deploy/viko-agent/.env
  python3 /home/deploy/viko-agent/scripts/prune-idle-sessions.py --dry-run --idle-hours 0.001
"
```

Expected: lists sessions that would be pruned. With `--dry-run`, dreaming is skipped (check `if not dry_run` guard).

- [x] **Step 7: Live test (destructive — only run when idle sessions exist)**

```bash
ssh doasas "
  source /home/deploy/viko-agent/.env
  python3 /home/deploy/viko-agent/scripts/prune-idle-sessions.py --idle-hours 2
  # Then check context.md was updated
  find /home/deploy/viko-agent/data -name 'context.md' -newer /home/deploy/viko-agent/scripts/dream_sessions.py
"
```

Expected: prints `[dream] → context.md updated` for each session that had content, then pruned.

- [x] **Step 8: Commit**

```bash
git add scripts/dream_sessions.py scripts/prune-idle-sessions.py
git commit -m "feat(scripts): dreaming — summarize sessions to context.md before pruning"
```

---

### Task 2: Commitments — inferred follow-up detection + delivery

**Files:**
- Create: `hooks/viko-commitments/HOOK.yaml` — fires on `agent:end`
- Create: `hooks/viko-commitments/handler.py` — detects commitment language, stores to JSON
- Create: `scripts/deliver_commitments.py` — host cron: reads stored commitments, sends due ones via bridge

**Why this matters:** When a project Hermes says "saya akan follow up besok" or "nanti kita cek lagi setelah deploy", there is no system to actually deliver that follow-up. OpenClaw calls these "commitments". This implements the same concept: detect → store → deliver.

**Interfaces:**
- Hook handler reads `context.reply` (agent's text response) and `context.session_key`
- Stores to `data/hermes-{slug}/commitments.json` as `{"pending": [{id, text, due_at, created_at}]}`
- Cron script reads routing.json to find JID per slug, POSTs due commitments to bridge loopback

- [ ] **Step 1: Discover the agent:end context structure**

```bash
ssh doasas "
  # Read the media-autosend hook to see how context fields are accessed
  cat /home/deploy/viko-agent/hooks/viko-media-autosend/handler.py | grep 'context\.' | head -20
"
```

Note: the `context` object fields used by the existing hook (e.g. `context.reply`, `context.event`, `context.session_key`). Use the same field names in the commitment hook.

- [ ] **Step 2: Create hooks/viko-commitments/HOOK.yaml**

```yaml
name: viko-commitments
description: "Detect follow-up commitments in agent replies and store for later delivery"
events:
  - agent:end
```

- [ ] **Step 3: Create hooks/viko-commitments/handler.py**

```python
"""Detect commitment language in agent replies and store to commitments.json.

Fires on agent:end. Uses simple pattern matching first; skips LLM call for speed.
Commitment patterns (Indonesian + English): "besok", "nanti", "follow up", etc.
"""
import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_COMMITMENT_PATTERNS = re.compile(
    r"\b(?:"
    r"besok|lusa|minggu depan|bulan depan|nanti|sebentar|ntar|"
    r"follow.?up|tindak lanjut|follow up|cek lagi|dicek|check back|"
    r"akan (?:saya|ku|kita|aku)|saya akan|aku akan|kita akan|"
    r"remind|ingatkan|pengingat|reminder|"
    r"setelah deploy|setelah selesai|after deploy|once it.s done"
    r")\b",
    re.IGNORECASE,
)

_DUE_OFFSET = {
    "besok": timedelta(days=1),
    "lusa": timedelta(days=2),
    "minggu depan": timedelta(weeks=1),
    "bulan depan": timedelta(days=30),
    "setelah deploy": timedelta(hours=2),
    "after deploy": timedelta(hours=2),
}

DATA_ROOT = Path(os.environ.get("HERMES_HOME", "/opt/data")).parent.parent / "viko-agent" / "data"


def _detect_commitment(text: str) -> str | None:
    """Return the matched commitment phrase or None."""
    m = _COMMITMENT_PATTERNS.search(text or "")
    return m.group(0) if m else None


def _due_at(phrase: str) -> datetime:
    """Estimate when to deliver the follow-up."""
    phrase_lower = phrase.lower()
    for key, delta in _DUE_OFFSET.items():
        if key in phrase_lower:
            return datetime.now(timezone.utc) + delta
    return datetime.now(timezone.utc) + timedelta(hours=24)  # default: next day


async def handle(event_type: str, context) -> None:
    if event_type != "agent:end":
        return

    # Get the agent's reply text
    reply_text = ""
    if hasattr(context, "reply"):
        r = context.reply
        reply_text = r.text if hasattr(r, "text") else str(r)
    elif hasattr(context, "response"):
        reply_text = str(context.response)

    if not reply_text:
        return

    phrase = _detect_commitment(reply_text)
    if not phrase:
        return

    # Determine slug from session_key or env
    slug = os.environ.get("VIKO_PROJECT_SLUG", "")
    if not slug:
        return

    commitments_file = DATA_ROOT / f"hermes-{slug}" / "commitments.json"
    commitments_file.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {"pending": []}
    if commitments_file.exists():
        try:
            data = json.loads(commitments_file.read_text())
        except Exception:
            data = {"pending": []}

    now = datetime.now(timezone.utc)
    commitment = {
        "id": str(uuid.uuid4())[:8],
        "text": f"Follow-up dari percakapan sebelumnya (trigger: \"{phrase}\"): {reply_text[:200]}",
        "due_at": _due_at(phrase).isoformat(),
        "created_at": now.isoformat(),
    }
    data["pending"].append(commitment)

    commitments_file.write_text(json.dumps(data, indent=2))
    print(f"[commitments] stored follow-up for {slug}: due {commitment['due_at']}")
```

- [ ] **Step 4: Create scripts/deliver_commitments.py**

```python
#!/usr/bin/env python3
"""Deliver due commitments to project groups via the admin bridge (loopback).

Run every 15 minutes via host cron (see setup-cron.sh).
Reads routing.json for slug→JID mapping.
POSTs due commitments to localhost:3000/send (no auth needed — loopback).
"""
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROUTING_FILE = Path("/home/deploy/viko-agent/data/bridge/routing.json")
DATA_ROOT = Path("/home/deploy/viko-agent/data")
BRIDGE_URL = "http://localhost:3000"


def _slug_to_jid() -> dict[str, str]:
    if not ROUTING_FILE.exists():
        return {}
    try:
        raw = json.loads(ROUTING_FILE.read_text())
        return {v["slug"]: jid for jid, v in raw.items() if isinstance(v, dict) and "slug" in v}
    except Exception:
        return {}


def _send(jid: str, message: str) -> bool:
    payload = json.dumps({"chatId": jid, "message": message}).encode()
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        return resp.get("success", False)
    except Exception as e:
        print(f"  [deliver] send failed: {e}")
        return False


def main() -> None:
    now = datetime.now(timezone.utc)
    slug_to_jid = _slug_to_jid()

    for slug, jid in slug_to_jid.items():
        cf = DATA_ROOT / f"hermes-{slug}" / "commitments.json"
        if not cf.exists():
            continue

        try:
            data = json.loads(cf.read_text())
        except Exception:
            continue

        pending = data.get("pending", [])
        remaining = []

        for c in pending:
            try:
                due = datetime.fromisoformat(c["due_at"])
                if due.tzinfo is None:
                    due = due.replace(tzinfo=timezone.utc)
            except Exception:
                remaining.append(c)
                continue

            if due <= now:
                msg = f"⏰ *Follow-up reminder*\n{c['text']}"
                if _send(jid, msg):
                    print(f"[deliver] {slug}: delivered commitment {c['id']}")
                else:
                    remaining.append(c)  # retry next run
            else:
                remaining.append(c)

        data["pending"] = remaining
        cf.write_text(json.dumps(data, indent=2))

    print(f"[deliver-commitments] done at {now.isoformat()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Register deliver_commitments in the host cron**

Update `scripts/setup-cron.sh` to add the delivery entry. In the file created by infrastructure Task 6, add after the prune install_cron call:

```bash
DELIVER_ENTRY="*/15 * * * * python3 $REPO_DIR/scripts/deliver_commitments.py >> $LOG_DIR/commitments.log 2>&1"
install_cron "$DELIVER_ENTRY" "deliver_commitments.py"
```

- [ ] **Step 6: Verify hook is recognized by hermes**

Hermes loads hooks from the `/opt/data/hooks/` directory (mounted from the host). Confirm the hooks dir is mounted:

```bash
ssh doasas "docker inspect viko-hermes | python3 -c \"
import json,sys
mounts = json.load(sys.stdin)[0]['Mounts']
for m in mounts:
    if 'hooks' in m.get('Source',''):
        print(m)
\""
```

If `hooks/` is mounted, the new hook will be picked up on next container restart. If not, check `docker-compose.yml` for the hooks volume mount.

- [ ] **Step 7: Test commitment detection locally**

```bash
python3 -c "
import re
PATTERN = re.compile(
    r'\b(?:besok|lusa|minggu depan|bulan depan|nanti|sebentar|ntar|'
    r'follow.?up|tindak lanjut|cek lagi|dicek|check back|'
    r'akan (?:saya|ku|kita|aku)|saya akan|aku akan|kita akan|'
    r'remind|ingatkan|pengingat|reminder|'
    r'setelah deploy|setelah selesai|after deploy|once it.s done'
    r')\b', re.IGNORECASE
)
tests = [
    ('Oke saya akan cek lagi besok pagi', True),
    ('Deploy sudah selesai, nanti aku follow up', True),
    ('Sudah selesai', False),
    ('File sudah dikirim', False),
]
for text, expected in tests:
    m = PATTERN.search(text)
    got = m is not None
    status = '✓' if got == expected else '✗ FAIL'
    print(f'{status} [{\"match\" if got else \"no match\"}] {text!r}')
"
```

Expected: all 4 lines show `✓`.

- [ ] **Step 8: Commit**

```bash
git add hooks/viko-commitments/ scripts/deliver_commitments.py scripts/setup-cron.sh
git commit -m "feat: commitments — detect follow-ups in agent replies, deliver via cron"
```

---

### Task 3: Tool call repair patch

**Files:**
- Create: `patches/patch-tool-call-repair.py` — inject retry logic when tool call JSON is malformed
- Modify: `Dockerfile.hermes` — add `COPY + RUN python3` for the new patch

**Why this matters:** When the LLM generates a tool call with malformed JSON arguments, hermes currently raises an exception and the agent silently fails. A single retry with a corrective prompt resolves most malformed tool calls (LLMs hallucinate argument formats, not the whole response).

**Interfaces:**
- Produces: malformed tool call → LLM sees its own bad output + correction prompt → one retry
- Max 1 retry (not a loop); if second attempt also malformed, raise original error

- [ ] **Step 1: Find the tool call parsing code in hermes**

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  grep -rn 'tool_call\|parse_tool\|invalid.*json\|json.*parse\|ToolCall' /opt/hermes/gateway/ /opt/hermes/hermes_cli/ 2>/dev/null | grep -v '.pyc' | head -30
\""
```

Also look at the agent runner:

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  grep -rn 'json.loads\|JSONDecodeError\|tool_call' /opt/hermes/hermes_cli/ 2>/dev/null | grep -v '.pyc' | head -20
\""
```

Note the file path and line number where tool call arguments are parsed from the model's response. This is the injection point for the repair logic.

- [ ] **Step 2: Read the identified file**

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  # Replace with the actual file found in Step 1
  cat -n /opt/hermes/gateway/run.py | grep -A 5 -B 5 'tool_call\|parse_tool' | head -50
\""
```

Identify:
- The function that calls `json.loads()` on tool arguments
- The exception type raised on failure (`json.JSONDecodeError`, `ValueError`, or a custom hermes exception)
- The variable name holding the raw arguments string
- The surrounding context (what variable holds the LLM response object)

- [ ] **Step 3: Write patches/patch-tool-call-repair.py**

Replace `<TARGET_FILE>`, `<INJECT_AFTER>`, `<EXCEPTION_TYPE>`, and `<args_var>` with values found in Steps 1–2:

```python
#!/usr/bin/env python3
"""Patch: Retry LLM call once when tool call arguments are malformed JSON.

Injected at the tool-call argument parse site. On JSONDecodeError, sends the
model its own malformed output and asks it to re-emit valid JSON. If the
second attempt is also malformed, raises the original error.

Idempotent: skips if MARKER is already in the file.
"""
import sys
from pathlib import Path

TARGET = Path("/opt/hermes/<path-found-in-step-1>")  # FILL IN from Step 1
MARKER = "_viko_tool_repair"

# FILL IN the exact code before the json.loads call from Step 2
INJECT_AFTER = """<exact code before json.loads from Step 2>"""

INJECT_CODE = """<exact code before json.loads from Step 2>
        # VIKO PATCH: tool call repair — retry once on malformed JSON
        def _viko_tool_repair(raw_args, original_exc, llm_call_fn):
            """Send the bad JSON back to the LLM with a correction prompt, retry once."""
            _viko_tool_repair_marker = True  # noqa: F841 (marker for idempotency check)
            correction_msg = (
                f"Your previous tool call had invalid JSON arguments: {raw_args!r}\\n"
                f"Error: {original_exc}\\n"
                "Please re-emit the tool call with valid JSON arguments only."
            )
            try:
                repaired_response = llm_call_fn(correction_msg)
                return repaired_response
            except Exception:
                raise original_exc
        # END VIKO PATCH"""


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1
    src = TARGET.read_text()
    if MARKER in src:
        print("✓ patch-tool-call-repair: already applied")
        return 0
    if INJECT_AFTER not in src:
        print("ERROR: injection point not found — hermes upstream changed; patch must be updated", file=sys.stderr)
        return 1
    TARGET.write_text(src.replace(INJECT_AFTER, INJECT_CODE, 1))
    print("✓ patch-tool-call-repair: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Note:** This patch is a template. The exact `INJECT_AFTER` and `INJECT_CODE` strings must be filled in based on what Step 2 reveals. The principle is the same as all other patches — find the right line, inject the repair wrapper.

- [ ] **Step 4: Add patch to Dockerfile.hermes**

After the existing patch COPY+RUN block (the `# ── Viko patches ──` section), add:

```dockerfile
COPY patches/patch-tool-call-repair.py /tmp/patch-tool-call-repair.py
RUN python3 /tmp/patch-tool-call-repair.py
```

- [ ] **Step 5: Build and verify**

```bash
ssh doasas "cd /home/deploy/viko-agent && git pull && docker compose build hermes 2>&1 | grep 'patch-tool-call-repair'"
```

Expected: `✓ patch-tool-call-repair: applied`

- [ ] **Step 6: Commit**

```bash
git add patches/patch-tool-call-repair.py Dockerfile.hermes
git commit -m "feat(patches): tool call repair — retry once on malformed LLM JSON arguments"
```

---

### Task 4: Tool result in-context pruning

**Files:**
- Create: `patches/patch-tool-result-pruning.py` — before each LLM call, trim old tool results in-memory
- Modify: `Dockerfile.hermes` — add COPY + RUN for new patch

**Why this matters:** Long sessions accumulate dozens of tool results (`read_file`, `ssh_exec`, etc.) in context. Old results are irrelevant but still consume tokens. OpenClaw trims them in-memory (not on disk) before each API call: keep first 200 chars + last 200 chars with "..." between. No session data is lost — only what the LLM sees is trimmed.

**Interfaces:**
- Produces: tool result messages older than `TOOL_RESULT_PRUNE_AFTER_MIN` (default: 5) minutes get soft-trimmed before each LLM call
- Full transcript on disk is never modified

- [ ] **Step 1: Find the LLM call site in hermes**

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  grep -rn 'messages.*send\|chat.*completions\|llm.*call\|anthropic.*messages\|openai.*create' \
    /opt/hermes/gateway/ /opt/hermes/hermes_cli/ 2>/dev/null | grep -v '.pyc' | head -20
\""
```

Also find where messages list is assembled before the API call:

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  grep -rn 'build_messages\|get_messages\|context_messages\|prepare_messages' \
    /opt/hermes/gateway/ /opt/hermes/hermes_cli/ 2>/dev/null | grep -v '.pyc' | head -20
\""
```

Note the file and function where the `messages` list is built just before calling the LLM.

- [ ] **Step 2: Read the identified function**

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  # Replace with actual file from Step 1
  grep -n 'def.*messages\|tool_result\|role.*tool' /opt/hermes/gateway/run.py | head -20
\""
```

Identify:
- The variable name of the messages list (e.g. `messages`, `ctx_messages`)
- The structure of tool result messages (e.g. `{"role": "tool", "content": ..., "timestamp": ...}`)
- Whether timestamps are available on individual messages

- [ ] **Step 3: Create patches/patch-tool-result-pruning.py**

```python
#!/usr/bin/env python3
"""Patch: Soft-trim stale tool results from context before each LLM call.

Keeps the first 200 and last 200 characters of each tool result message
that is older than TOOL_RESULT_PRUNE_AFTER_MIN minutes. Insert "..." between.
Operates only on the in-memory messages list — the on-disk transcript is unchanged.

Idempotent: skips if MARKER is already in the file.
"""
import sys
from pathlib import Path

TARGET = Path("/opt/hermes/<path-found-in-step-1>")  # FILL IN
MARKER = "_viko_tool_prune"

# FILL IN: the line just before the LLM call where messages list is finalized
INJECT_AFTER = """<exact line before LLM call from Step 2>"""

INJECT_CODE = """<exact line before LLM call from Step 2>
        # VIKO PATCH: soft-trim stale tool results before LLM call
        import time as _viko_time
        _PRUNE_AFTER_SEC = int(os.environ.get("TOOL_RESULT_PRUNE_AFTER_MIN", "5")) * 60
        _KEEP_CHARS = 200
        _now_ts = _viko_time.time()

        def _viko_soft_trim(content, max_chars=_KEEP_CHARS):
            s = str(content or "")
            if len(s) <= max_chars * 2 + 10:
                return s
            return s[:max_chars] + "\\n...[trimmed]...\\n" + s[-max_chars:]

        for _viko_msg in messages:  # replace 'messages' with actual variable name
            if _viko_msg.get("role") != "tool":
                continue
            _viko_ts = _viko_msg.get("timestamp") or _viko_msg.get("created_at") or 0
            if isinstance(_viko_ts, str):
                try:
                    import datetime as _viko_dt
                    _viko_ts = _viko_dt.datetime.fromisoformat(_viko_ts).timestamp()
                except Exception:
                    _viko_ts = 0
            if _viko_ts and (_now_ts - _viko_ts) > _PRUNE_AFTER_SEC:
                content = _viko_msg.get("content", "")
                if isinstance(content, str):
                    _viko_msg["content"] = _viko_soft_trim(content)
                elif isinstance(content, list):
                    for _part in content:
                        if isinstance(_part, dict) and _part.get("type") == "text":
                            _part["text"] = _viko_soft_trim(_part.get("text", ""))
        # END VIKO PATCH"""


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1
    src = TARGET.read_text()
    if MARKER in src:
        print("✓ patch-tool-result-pruning: already applied")
        return 0
    if INJECT_AFTER not in src:
        print("ERROR: injection point not found — hermes upstream changed; update patch", file=sys.stderr)
        return 1
    TARGET.write_text(src.replace(INJECT_AFTER, INJECT_CODE, 1))
    print("✓ patch-tool-result-pruning: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Add to Dockerfile.hermes**

```dockerfile
COPY patches/patch-tool-result-pruning.py /tmp/patch-tool-result-pruning.py
RUN python3 /tmp/patch-tool-result-pruning.py
```

- [ ] **Step 5: Build and verify**

```bash
ssh doasas "cd /home/deploy/viko-agent && git pull && docker compose build hermes 2>&1 | grep 'patch-tool-result'"
```

Expected: `✓ patch-tool-result-pruning: applied`

- [ ] **Step 6: Commit**

```bash
git add patches/patch-tool-result-pruning.py Dockerfile.hermes
git commit -m "feat(patches): soft-trim stale tool results before LLM call (in-memory only)"
```

---

### Task 5: Memory flush before compaction

**Files:**
- Create: `patches/patch-memory-flush-compact.py` — before hermes compacts context, inject a write to context.md
- Modify: `Dockerfile.hermes` — add COPY + RUN for new patch

**Why this matters:** When hermes compacts a long session (summarizes old messages), information in those messages is lost. OpenClaw does a "memory flush" first: forces a tool call to write key information to a memory file before compaction. viko-agent's equivalent is writing to `context.md` for the project.

**Interfaces:**
- Produces: just before hermes compaction fires, a tool call to `write_file` is injected with a prompt to save key facts to `/opt/data/context.md`
- The write happens via hermes's existing `write_file` tool — no new tool needed

- [ ] **Step 1: Find the compaction trigger in hermes**

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  grep -rn 'compact\|compaction\|context_limit\|max_tokens.*compress\|summarize.*context' \
    /opt/hermes/gateway/ /opt/hermes/hermes_cli/ 2>/dev/null | grep -v '.pyc' | head -20
\""
```

Also search for where the compaction decision is made (typically when token count exceeds a threshold):

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  grep -rn 'token.*count\|count.*token\|context.*overflow\|too.*long' \
    /opt/hermes/gateway/ 2>/dev/null | grep -v '.pyc' | head -10
\""
```

Note: the file and function where compaction is triggered.

- [ ] **Step 2: Read the compaction function**

```bash
ssh doasas "docker exec viko-hermes bash -c \"
  # Replace compact_fn and file with actual values from Step 1
  grep -n 'def.*compact\|def.*compress\|def.*summarize' /opt/hermes/gateway/run.py | head -10
\""
```

Identify:
- The exact function name and file for the compaction entry point
- What happens just before the LLM summarization call
- Any existing hooks or callbacks that fire pre-compaction

- [ ] **Step 3: Create patches/patch-memory-flush-compact.py**

```python
#!/usr/bin/env python3
"""Patch: Flush important session facts to context.md before hermes compacts.

When hermes is about to compact (summarize) the context window, we first
inject a tool call asking the LLM to write key facts to /opt/data/context.md.
This prevents critical information from being lost in the compaction summary.

Idempotent: skips if MARKER is already in the file.
"""
import sys
from pathlib import Path

TARGET = Path("/opt/hermes/<path-found-in-step-1>")  # FILL IN
MARKER = "_viko_flush_before_compact"

# FILL IN: the exact line just before hermes triggers its compaction LLM call
INJECT_AFTER = """<exact line before compaction call from Step 2>"""

INJECT_CODE = """<exact line before compaction call from Step 2>
        # VIKO PATCH: memory flush before compaction
        # Ask the LLM to write key facts to context.md before the context is summarized
        _viko_flush_before_compact = True  # marker
        _viko_flush_prompt = (
            "Sebelum context ini dipadatkan, tulis fakta-fakta penting ke file "
            "/opt/data/context.md menggunakan write_file tool. "
            "Sertakan: keputusan utama, task yang sudah selesai, task yang masih berjalan, "
            "dan informasi teknis kritikal (URL, credential yang sudah diketahui, konfigurasi). "
            "Format: ## Memory Flush <timestamp>\\n<bullet points>. "
            "Hanya 10-15 poin terpenting. Setelah menulis, balas 'done'."
        )
        try:
            # This calls the same LLM that handles the conversation,
            # using hermes's internal tool dispatch so write_file is available
            await self._run_tool_call_turn(_viko_flush_prompt)  # adjust method name from Step 2
        except Exception as _viko_flush_err:
            # Non-fatal: if flush fails, compaction still proceeds
            print(f"[viko] memory flush pre-compact failed (non-fatal): {_viko_flush_err}")
        # END VIKO PATCH"""


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1
    src = TARGET.read_text()
    if MARKER in src:
        print("✓ patch-memory-flush-compact: already applied")
        return 0
    if INJECT_AFTER not in src:
        print("ERROR: injection point not found — hermes upstream changed; update patch", file=sys.stderr)
        return 1
    TARGET.write_text(src.replace(INJECT_AFTER, INJECT_CODE, 1))
    print("✓ patch-memory-flush-compact: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Add to Dockerfile.hermes**

```dockerfile
COPY patches/patch-memory-flush-compact.py /tmp/patch-memory-flush-compact.py
RUN python3 /tmp/patch-memory-flush-compact.py
```

- [ ] **Step 5: Build and verify**

```bash
ssh doasas "cd /home/deploy/viko-agent && git pull && docker compose build hermes 2>&1 | grep 'patch-memory-flush'"
```

Expected: `✓ patch-memory-flush-compact: applied`

- [ ] **Step 6: Integration test**

Trigger compaction by sending many messages to a project Hermes until context fills. Check `context.md`:

```bash
ssh doasas "cat /home/deploy/viko-agent/data/hermes-<slug>/context.md | grep 'Memory Flush' | tail -5"
```

Expected: lines starting with `## Memory Flush <timestamp>`.

- [ ] **Step 7: Commit**

```bash
git add patches/patch-memory-flush-compact.py Dockerfile.hermes
git commit -m "feat(patches): memory flush before compaction — write key facts to context.md"
```

---

## Self-Review Notes

**Spec coverage:**
- ✅ Dreaming (summarize before prune) — Task 1
- ✅ Commitments (detect + deliver) — Task 2
- ✅ Tool call repair — Task 3 (investigation-dependent; template provided)
- ✅ Tool result in-context pruning — Task 4 (investigation-dependent; template provided)
- ✅ Memory flush before compact — Task 5 (investigation-dependent; template provided)

**Known gaps (by design):**
- Tasks 3–5 are templates that require hermes source investigation (Steps 1–2 in each task). The investigation steps are fully specified with exact commands — no TBD. The implementer fills in the discovered values before writing the injection code.
- `dream_session` uses the field name `messages` — Step 1 of Task 1 verifies the actual field name before Task 2 wires the import.

**Dependency note:** Run infrastructure plan Task 6 (setup-cron.sh) before Task 2 of this plan, as `deliver_commitments.py` relies on the same cron installer.
