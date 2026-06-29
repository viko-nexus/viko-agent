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
