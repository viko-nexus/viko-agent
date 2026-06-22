#!/usr/bin/env python3
"""
Boot-time isolation guard for project Hermes containers.

Runs before the gateway (s6 cont-init). For a project container
(VIKO_PROJECT_SLUG set) it asserts the capability-isolation invariants actually
hold at runtime — a fail-closed backstop so a future mis-spawn becomes a loud,
visible refusal instead of a silent leak. The admin container (no slug) is a
no-op.

Mode via VIKO_ISOLATION_GUARD:
  enforce  → on failure: tombstone + best-effort alert + go INERT (block startup,
             gateway never starts, container reports unhealthy). NOT a crash-loop.
             (default — fail-closed.)
  warn     → on failure: tombstone + log, but continue startup.
  off      → skip entirely.

The capability layer (per-project mount, per-project SSH key, dropped token,
relay-token send scoping) is what ENFORCES isolation; this guard only verifies it.
"""
import os
import sys
import json
import time
import urllib.request
from pathlib import Path

TOMBSTONE = Path("/opt/data/.isolation-tombstone")
SSH_ALLOWED = {"id_viko", "id_viko.pub", "config", "known_hosts"}


def main() -> int:
    mode = os.environ.get("VIKO_ISOLATION_GUARD", "enforce").strip().lower()
    slug = os.environ.get("VIKO_PROJECT_SLUG", "").strip()
    if not slug or mode == "off":
        return 0  # admin container or disabled → no-op

    root = Path(os.environ.get("VIKO_PROJECTS_ROOT", "/home/viko/projects"))
    vroot = root / "viko-agent"
    failures = []

    def check(name, ok, detail=""):
        print(f"[isolation-guard] {'PASS' if ok else 'FAIL'}: {name} {detail}".rstrip())
        if not ok:
            failures.append(name)

    # ── Structural checks (deterministic — safe to enforce) ──────────────────
    def names(p):
        try:
            return sorted(x.name for x in p.iterdir())
        except Exception:
            return []

    root_extra = [e for e in names(root) if e not in {slug, "viko-agent"}]
    check("root-scope", not root_extra, f"(leaked: {root_extra})" if root_extra else f"({names(root)})")

    proj_extra = [p for p in names(vroot / "projects") if p != slug]
    check("projects-scope", not proj_extra, f"(leaked: {proj_extra})" if proj_extra else "")

    check("no-env-secrets", not (vroot / ".env").exists())
    check("no-data-dir", not (vroot / "data").exists())
    check("no-mcp-gateway", not Path("/opt/viko/mcp-servers").exists())
    check("no-github-token", not os.environ.get("GITHUB_TOKEN", "").strip())

    cfg = Path("/opt/data/.ssh/config")
    foreign_aliases = []
    if cfg.exists():
        for line in cfg.read_text().splitlines():
            s = line.strip()
            if s.lower().startswith("host "):
                foreign_aliases += [a for a in s.split()[1:] if not a.startswith(f"{slug}-")]
    check("ssh-single-alias", not foreign_aliases, f"(foreign: {foreign_aliases})" if foreign_aliases else "")

    foreign_keys = [f for f in names(Path("/opt/data/.ssh")) if f not in SSH_ALLOWED]
    check("ssh-no-foreign-keys", not foreign_keys, f"(foreign: {foreign_keys})" if foreign_keys else "")

    token = os.environ.get("HERMES_RELAY_TOKEN", "").strip()
    check("relay-token-present", bool(token))

    # ── Network check (best-effort — admin may be momentarily down at boot) ──
    if token:
        try:
            req = urllib.request.Request(
                "http://viko-hermes:3000/relay/scope",
                headers={"Host": "viko-hermes-admin", "Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            jids = data.get("allowed_jids", [])
            port_ok = str(data.get("port")) == os.environ.get("WHATSAPP_PORT_FILTER", "")
            check("relay-scope-own-group", len(jids) == 1 and port_ok, f"({data})")
        except Exception as e:
            print(f"[isolation-guard] WARN: /relay/scope check skipped (admin unreachable: {e})")

    # ── Verdict ──────────────────────────────────────────────────────────────
    if not failures:
        if TOMBSTONE.exists():
            TOMBSTONE.unlink()  # clear any stale tombstone on a clean boot
        print(f"[isolation-guard] OK — all isolation invariants hold for '{slug}'")
        return 0

    msg = f"slug={slug} mode={mode} failed={failures}"
    print(f"[isolation-guard] ISOLATION CHECK FAILED — {msg}", file=sys.stderr)
    try:
        TOMBSTONE.write_text(msg + "\n")
    except Exception:
        pass
    _alert(slug, failures, token)

    if mode != "enforce":
        print("[isolation-guard] mode=warn → continuing despite failures (capability layer still enforces)")
        return 0

    print("[isolation-guard] mode=enforce → refusing to start gateway; container is INERT (unhealthy).", file=sys.stderr)
    while True:
        time.sleep(3600)


def _alert(slug, failures, token):
    """Best-effort: post one alert to this project's OWN group (the relay token
    only authorizes that JID — it cannot reach the admin home channel by design).
    Silent on any error; the tombstone + unhealthy state is the durable signal."""
    if not token:
        return
    try:
        req = urllib.request.Request(
            "http://viko-hermes:3000/relay/scope",
            headers={"Host": "viko-hermes-admin", "Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            jid = json.loads(r.read()).get("allowed_jids", [None])[0]
        if not jid:
            return
        body = json.dumps({
            "chatId": jid,
            "message": f"⛔ Viko-{slug}: isolation guard gagal ({', '.join(failures)}). "
                       f"Container ditahan (inert) demi keamanan. Cek konfigurasi spawn.",
        }).encode()
        post = urllib.request.Request(
            "http://viko-hermes:3000/send", data=body, method="POST",
            headers={"Host": "viko-hermes-admin", "Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
        )
        urllib.request.urlopen(post, timeout=8).read()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
