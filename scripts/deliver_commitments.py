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
