#!/usr/bin/env python3
"""
Spawn a new isolated Hermes container for a project.

Run on trahku as viko user:
  python3 ~/projects/viko-agent/scripts/spawn-hermes.py <slug> <group_jid>

What this does:
  1. Allocate next available port (starts at 8101)
  2. Create data/hermes-{slug}/ with isolated config.yaml + .env
  3. Run docker run -d to start the container
  4. Update data/bridge/routing.json atomically (bridge hot-reloads in <1s)
  5. Print the allocated port

Port allocation: scans routing.json for highest used port, increments.
Container name: viko-hermes-{slug}
Docker network: viko_default (created by docker compose)
Image: viko-viko-hermes (built by docker compose build hermes)
"""

import sys
import os
import re
import json
import shutil
import secrets
import argparse
import subprocess
import yaml
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.resolve()
ROUTING_FILE = REPO_DIR / "data" / "bridge" / "routing.json"
MIN_PORT = 8101
HERMES_IMAGE = "viko-hermes"

# Per-project SSH material lives here on the host (one keypair + 1-alias config
# per project). Only the project's own dir is mounted into its container, so a
# container physically cannot present another project's key or resolve its alias.
SSH_DIR = Path.home() / ".viko" / "ssh"
SSH_PROJECTS_DIR = SSH_DIR / "projects"


def _read_env() -> dict:
    env_path = REPO_DIR / ".env"
    result = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def load_routing() -> dict:
    if ROUTING_FILE.exists():
        try:
            return json.loads(ROUTING_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_routing(routing: dict) -> None:
    ROUTING_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ROUTING_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(routing, indent=2))
    tmp.rename(ROUTING_FILE)


def _container_running(name: str) -> bool:
    """Return True if container exists and is running."""
    r = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True, text=True
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def _container_exists(name: str) -> bool:
    """Return True if container exists (running or stopped)."""
    r = subprocess.run(
        ["docker", "inspect", "-f", "{{.Id}}", name],
        capture_output=True, text=True
    )
    return r.returncode == 0


def _wait_healthy(name: str, timeout: int = 90) -> None:
    """Wait until container is running. Raises RuntimeError on timeout."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _container_running(name):
            return
        time.sleep(2)
    raise RuntimeError(f"Container {name} did not start within {timeout}s")


def _entry_port(val) -> int:
    """Port from a routing entry — new schema {port,...} or legacy bare int."""
    if isinstance(val, dict):
        return int(val.get("port", 0))
    return int(val) if str(val).isdigit() else 0


def next_port(routing: dict) -> int:
    used = {_entry_port(v) for v in routing.values()}
    used.discard(0)
    port = MIN_PORT
    while port in used:
        port += 1
    return port


def _run(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _parse_ssh_host_block(config_text: str, *aliases: str) -> dict:
    """Extract HostName/User for the first Host block matching any alias."""
    out, capture = {}, False
    for line in config_text.splitlines():
        s = line.strip()
        if s.lower().startswith("host "):
            capture = bool(set(s.split()[1:]) & set(aliases))
            continue
        if capture:
            m = re.match(r"(?i)\s*(hostname|user)\s+(\S+)", line)
            if m:
                out.setdefault(m.group(1).lower(), m.group(2))
    return out


def _resolve_vps(slug: str, vps_host: str, vps_user: str) -> tuple:
    """Resolve (vps_host, vps_user) from args, then per-project config, then the
    legacy shared config. Returns ('', '') if this project has no VPS."""
    if vps_host:
        return vps_host, (vps_user or "viko-exec")

    proj_cfg = SSH_PROJECTS_DIR / slug / "config"
    if proj_cfg.exists():
        d = _parse_ssh_host_block(proj_cfg.read_text(), f"{slug}-vps", f"{slug}-prod")
        if d.get("hostname"):
            return d["hostname"], d.get("user", "viko-exec")

    shared = SSH_DIR / "config"
    if shared.exists():
        d = _parse_ssh_host_block(shared.read_text(), f"{slug}-vps", f"{slug}-prod")
        if d.get("hostname"):
            return d["hostname"], d.get("user", "viko-exec")

    return "", ""


def _ensure_project_key(slug: str) -> Path:
    """Generate a dedicated {slug}-deploy keypair if missing. Returns the private
    key path. The .pub must be authorized ONLY on this project's VPS user."""
    SSH_DIR.mkdir(parents=True, exist_ok=True)
    priv = SSH_DIR / f"{slug}-deploy"
    if not priv.exists():
        r = _run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", f"viko-{slug}", "-f", str(priv)])
        if r.returncode != 0:
            raise RuntimeError(f"ssh-keygen failed for {slug}: {r.stderr.strip()}")
        print(f"  ✓ Generated dedicated key {slug}-deploy")
    priv.chmod(0o600)
    return priv


def _build_project_ssh_dir(slug: str, vps_host: str, vps_user: str) -> Path:
    """Build ~/.viko/ssh/projects/{slug}/ holding ONLY this project's key + a
    single-alias config + pre-seeded known_hosts. This whole dir is what gets
    mounted at /opt/data/.ssh — so the container has no other project's key and
    cannot resolve any other {slug}-vps alias."""
    proj_dir = SSH_PROJECTS_DIR / slug
    proj_dir.mkdir(parents=True, exist_ok=True)

    priv = _ensure_project_key(slug)
    shutil.copy2(priv, proj_dir / "id_viko")
    (proj_dir / "id_viko").chmod(0o600)
    if (SSH_DIR / f"{slug}-deploy.pub").exists():
        shutil.copy2(SSH_DIR / f"{slug}-deploy.pub", proj_dir / "id_viko.pub")

    # Single-alias config — both {slug}-vps and {slug}-prod point to the one host.
    if vps_host:
        (proj_dir / "config").write_text(
            f"Host {slug}-vps {slug}-prod\n"
            f"    HostName {vps_host}\n"
            f"    User {vps_user}\n"
            f"    IdentityFile /opt/data/.ssh/id_viko\n"
            f"    IdentitiesOnly yes\n"
            f"    StrictHostKeyChecking accept-new\n"
            f"    UserKnownHostsFile /opt/data/.ssh/known_hosts\n"
        )
    else:
        (proj_dir / "config").write_text("# no VPS configured for this project\n")

    # Pre-seed known_hosts from the shared file so accept-new doesn't need to
    # write into the read-only mount on first connect. Also seed github.com so
    # the container can `git push` over SSH (scoped per-repo deploy key).
    shared_kh = SSH_DIR / "known_hosts"
    kh = shared_kh.read_text() if shared_kh.exists() else ""
    if "github.com" not in kh:
        try:
            kh += _run(["ssh-keyscan", "-t", "ed25519", "github.com"]).stdout
        except Exception:
            pass
    (proj_dir / "known_hosts").write_text(kh)
    return proj_dir


def preflight(slug: str, projects_root: Path, proj_ssh_dir: Path, vps_host: str) -> None:
    """Fail-closed invariants checked BEFORE docker run. Raise to abort spawn.

    Security invariants (ssh config has only this slug's aliases, key present) are
    hard failures. A missing code dir is an onboarding-completeness warning, not a
    security failure — the container still runs fully isolated over an empty dir.
    """
    errors = []

    project_code = projects_root / slug
    if not project_code.is_dir():
        print(f"  ⚠ project code dir missing ({project_code}) — not onboarded yet; "
              f"container will run isolated over an empty dir")

    cfg = proj_ssh_dir / "config"
    if not cfg.exists():
        errors.append(f"per-project ssh config missing: {cfg}")
    else:
        # Exactly one Host line, and every alias on it must belong to this slug.
        host_lines = [l for l in cfg.read_text().splitlines() if l.strip().lower().startswith("host ")]
        if vps_host and len(host_lines) != 1:
            errors.append(f"ssh config must have exactly 1 Host block, found {len(host_lines)}")
        for hl in host_lines:
            for alias in hl.split()[1:]:
                if not alias.startswith(f"{slug}-"):
                    errors.append(f"ssh config leaks foreign alias: {alias}")

    key = proj_ssh_dir / "id_viko"
    if not key.exists():
        errors.append(f"per-project key missing: {key}")

    if errors:
        raise RuntimeError("preflight failed:\n  - " + "\n  - ".join(errors))
    print(f"  ✓ preflight passed (code={project_code.name}, ssh=1 alias, key present)")


def _build_project_config(slug: str, group_jid: str, env: dict) -> dict:
    ninerouter_url = env.get("OPENAI_BASE_URL", "http://viko-9router:20128/v1")
    ninerouter_key = env.get("OPENAI_API_KEY", "")

    prompt = (
        f"Kamu ada di group WhatsApp {slug.upper()}. Project aktif: {slug.upper()} — hanya {slug}.\n\n"
        f"ATURAN ISOLASI (wajib, tanpa pengecualian):\n"
        f"- Hanya bahas hal yang berkaitan dengan project {slug}\n"
        f"- Jika ditanya tentang project lain: jawab 'Untuk [nama project], diskusikan di group-nya langsung.' — lalu stop\n"
        f"- Memory atau konteks dari project lain tidak relevan di sini, abaikan\n\n"
        f"Siapapun boleh bertanya — hanya Eksa yang bisa authorize eksekusi (deploy, kode, infra).\n"
        f"Jika pesan diawali [READ-ONLY MEMBER]: hanya jawab pertanyaan/info, "
        f"tolak eksekusi dengan 'Hanya Eksa yang bisa minta ini.'\n\n"
        f"Balas dalam Bahasa Indonesia."
    )

    return {
        "model": {
            "default": "viko-combo",
            "provider": "openai",
            "base_url": ninerouter_url,
        },
        "providers": {
            "openai": {"api_key": ninerouter_key, "base_url": ninerouter_url}
        },
        "web": {"extract_backend": "https://r.jina.ai/"},
        "whatsapp": {
            "require_mention": True,
            # Treat the name "viko" (any case) as a mention, so members can address
            # the bot by name in the group instead of needing a WhatsApp @-tag.
            "mention_patterns": [r"\bviko\b"],
            "unauthorized_dm_behavior": "ignore",
            "channel_prompts": {group_jid: prompt},
        },
        "skills": {
            "external_dirs": ["/opt/viko/skills"],
            "guard_agent_created": True,
        },
        "terminal": {
            "cwd": env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))
        },
        "timezone": "Asia/Makassar",
        "kanban": {"auto_decompose": False, "max_in_progress_per_profile": 1},
        "display": {
            "language": "id",
            "runtime_footer": {"enabled": False, "fields": ["model", "context_pct"]},
            "platforms": {
                "whatsapp": {
                    "tool_progress": "off",
                    "interim_assistant_messages": False,
                    "streaming": False,
                }
            },
        },
        "auxiliary": {
            "vision": {
                "provider": "openai",
                "model": "cc/claude-sonnet-4-6",
                "base_url": ninerouter_url,
                "api_key": ninerouter_key,
                "timeout": 120,
                "extra_body": {},
                "download_timeout": 30,
            },
            "compression": {
                "provider": "openai",
                "model": "cc/claude-haiku-4-5-20251001",
                "base_url": ninerouter_url,
                "api_key": ninerouter_key,
                "timeout": 120,
                "extra_body": {},
            },
        },
        "memory": {"provider": "holographic"},
        "command_allowlist": [
            "script execution via -e/-c flag",
            "script execution via heredoc",
            "docker restart/stop/kill (container lifecycle)",
            "hermes kanban",
            "execute_code",
            "overwrite system file via redirection",
            f"ssh {slug}-vps (deploy to {slug} VPS)",
        ],
    }


def create_hermes_data_dir(slug: str, port: int, group_jid: str, env: dict) -> Path:
    data_dir = REPO_DIR / "data" / f"hermes-{slug}"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create the in-container HOME (/opt/data/home) as the host user so Docker
    # doesn't auto-create it root-owned when it mounts .ssh into /opt/data/home/.ssh.
    # A root-owned HOME makes $HOME/.cache unwritable for the hermes user, which
    # breaks uv/pip/execute_code and any on-the-fly document tooling.
    home_dir = data_dir / "home"
    home_dir.mkdir(parents=True, exist_ok=True)

    # Agent git config (HOME=/opt/data/home). Trust the mounted repo (else git aborts
    # with "dubious ownership"), set the Viko identity, and pin the per-project SSH key
    # so `git pull/commit/push` from the already-cloned repo just works — the agent
    # must use the repo at {projects_root}/{slug} and never re-clone to /tmp.
    projects_root = env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))
    repo_path = f"{projects_root}/{slug}"
    (home_dir / ".gitconfig").write_text(
        f"[safe]\n\tdirectory = {repo_path}\n"
        f"[user]\n\tname = Viko\n\temail = viko-{slug}@local\n"
        f"[core]\n\tsshCommand = ssh -i /opt/data/.ssh/id_viko -o IdentitiesOnly=yes "
        f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/opt/data/.ssh/known_hosts\n"
        f"[init]\n\tdefaultBranch = main\n"
    )

    # Write .env
    (data_dir / ".env").write_text(
        f"WHATSAPP_MODE=bot\n"
        f"WHATSAPP_RELAY_MODE=true\n"
        f"WHATSAPP_RELAY_TARGET=http://viko-hermes:3000\n"
        f"WHATSAPP_PORT_FILTER={port}\n"
        f"WHATSAPP_ENABLED=true\n"
        f"WHATSAPP_HOME_CHANNEL={env.get('WHATSAPP_HOME_CHANNEL', '')}\n"
        # Authorize all senders: routing already scopes this container to its one
        # group, so "all users" = that group's members. Execution stays gated to
        # Eksa via the bridge's [READ-ONLY MEMBER] tagging + channel_prompt rules.
        f"GATEWAY_ALLOW_ALL_USERS=true\n"
    )

    # Write config.yaml
    config = _build_project_config(slug, group_jid, env)
    (data_dir / "config.yaml").write_text(
        yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
    )

    # Viko identity (SOUL.md) — project-scoped. Loaded fresh each message; without
    # it Hermes uses its default "Claude Code on Hermes Agent" persona.
    (data_dir / "SOUL.md").write_text(
        f"# Viko — AI Developer Assistant ({slug})\n\n"
        f"Kamu adalah **Viko**, asisten developer Eksa untuk project **{slug}** — "
        f"PM, Senior Dev, QA, dan BA dalam satu otak, fokus ke {slug}.\n\n"
        f"## Bahasa & Komunikasi\n"
        f"- Balas dalam **Bahasa Indonesia** untuk percakapan — santai, akrab, kayak rekan tim.\n"
        f"- Istilah teknis/dev (nama variabel, branch, perintah, kode, output tool) biarkan natural "
        f"(English/aslinya) — jangan dipaksa diterjemahkan. Intinya: kalimat Indonesia, istilah dev apa adanya.\n"
        f"- Ringkas dan to-the-point; bullet untuk hal teknis; jangan kaku/formal.\n"
        f"- Sisipkan humor ringan yang **berkelas & profesional** — witty, cerdas, "
        f"sesekali sarkas halus. Kayak senior dev yang asik diajak ngobrol. "
        f"Jangan maksa lucu / cringe / emoji berlebihan: substansi dulu, humor jadi bumbu.\n\n"
        f"## Scope (wajib)\n"
        f"- Kamu HANYA menangani project **{slug}**, dan TIDAK punya akses/info project lain.\n"
        f"- Kalau ada yang menyebut/menanyakan progress/info project lain (nama apa pun yang bukan {slug}): "
        f"JANGAN tanya balik 'itu apa', JANGAN mengarang. Langsung balas sopan: "
        f"'Itu project lain ya — tanya Viko di group project-nya langsung. Di sini khusus {slug}.' lalu stop.\n\n"
        f"## Identitas\n"
        f"- Kamu Viko — bukan agent/orang/layanan lain. Kamu AI. Satu agent, satu otak.\n"
        f"- JANGAN mengaku 'Claude Code' atau menawarkan '/help' generik. Kamu Viko untuk {slug}.\n\n"
        f"## Authorization\n"
        f"- Hanya **Eksa** yang bisa authorize eksekusi (deploy, infra, ops destruktif).\n"
        f"- Minta approval dulu sebelum aksi yang irreversible.\n\n"
        f"## Anti-Spam\n"
        f"- Kalau ada yang nge-spam (pesan berulang, flooding, atau nyepam gak jelas bertubi-tubi): "
        f"jangan diladenin satu-satu. Kasih peringatan SEKALI dulu — santai tapi tegas: "
        f"'Kamu nyepam ya, mau saya blokir nih?'\n"
        f"- Kalau masih lanjut setelah diperingati, stop balas (diamkan) dan kabarin Eksa.\n"
        f"- Jangan munculin peringatan ini di percakapan normal — cuma buat yang jelas-jelas spam.\n\n"
        f"## Baca Lampiran (PDF/dokumen/gambar)\n"
        f"- File yang dikirim ke WA otomatis ke-download lokal; path-nya ada di pesan. "
        f"`python3` udah ada lib-nya (pymupdf, python-docx, python-pptx, openpyxl) — "
        f"baca langsung, JANGAN install apa-apa.\n"
        f"- PDF/scan: `python3 -c \"import pymupdf; d=pymupdf.open('PATH'); print(''.join(p.get_text() for p in d))\"`. "
        f"JANGAN pakai vision/vision_analyze buat PDF — itu cuma buat gambar.\n"
        f"- docx: `import docx`. pptx: `import pptx`. xlsx: `import openpyxl`. Gambar (jpg/png): vision baca langsung.\n"
        f"- Langsung baca filenya — jangan minta user paste/convert manual.\n\n"
        f"## Project & Git (dev)\n"
        f"- Repo project ini SUDAH ke-clone lokal di `{repo_path}`. `cd` ke situ buat baca/edit/jalanin/build kode. "
        f"JANGAN clone ulang, JANGAN ke /tmp.\n"
        f"- Git udah dikonfigurasi (identity Viko, key `/opt/data/.ssh/id_viko`, repo di-trust). "
        f"Tinggal `git pull/add/commit/push` dari DALAM repo — jangan bikin key baru / ngarang path key.\n"
        f"- SSH ke server project: pakai alias `{slug}-prod` (config + key `/opt/data/.ssh/id_viko` udah siap). "
        f"Contoh: `ssh {slug}-prod 'perintah'`. Jangan ngarang host/user/key.\n"
        f"- **Akses DB lewat SSH TUNNEL** (DB gak ke-expose publik, jangan konek langsung): "
        f"baca `DATABASE_URL` dari `.env` project DI SERVER (`ssh {slug}-prod 'cat <path>/.env'`), "
        f"buka tunnel ke host:port DB-nya — `ssh -fN -L 5433:<db_host>:<db_port> {slug}-prod` — "
        f"lalu query ke `127.0.0.1:5433`. Tipe DB dari scheme DATABASE_URL, client udah keinstall semua: "
        f"`postgresql`->psql/psycopg2, `mysql`->mysql/PyMySQL, `mongodb`->pymongo, `redis`->redis-cli/redis, "
        f"atau SQLAlchemy buat URL SQL apa pun (python3). "
        f"Tutup tunnel kalau selesai (`pkill -f '5433:'`). JANGAN hardcode creds.\n\n"
        f"## Kirim File/Media ke Chat\n"
        f"- Satu-satunya cara KIRIM file = tulis baris `MEDIA:<path_absolut>` di balasan "
        f"(1 per file, path absolut tanpa spasi). Hermes auto-attach native.\n"
        f"- PENTING: bikin/convert/simpan file BUKAN berarti terkirim. Kalau user minta KIRIM/share file, "
        f"balasan kamu WAJIB ada baris `MEDIA:<path>`. JANGAN bilang 'terkirim/file siap download/dikirim ke group' "
        f"kalau baris MEDIA: itu gak ada di balasan. JANGAN kirim via curl/subprocess/script ke bridge — gak jalan, "
        f"cuma tag MEDIA: yang ngirim. Self-check sebelum ngaku terkirim: ada baris MEDIA: gak di balasan ini?\n"
        f"- Contoh abis convert ke PDF: `Quotation-nya udah jadi PDF 👇` lalu baris baru "
        f"`MEDIA:{repo_path}/docs/quotation/QUOTATION_FINAL.pdf`\n"
        f"- JANGAN bilang 'ga support / API limitation' — SALAH. Credential (.env/.ssh/key) doang yang diblok.\n\n"
        f"## Generate & Convert File\n"
        f"- Dokumen ber-FORMAT: tulis kontennya sebagai **Markdown**, lalu render pakai **pandoc** biar "
        f"heading/bold/bullet/tabel jadi format BENERAN: `pandoc input.md -o output.docx` lalu "
        f"`soffice --headless --convert-to pdf output.docx`. JANGAN convert `.md` langsung lewat soffice — "
        f"`**`/`#`/`---` bakal jadi teks mentah & keliatan rusak buat orang awam (itu bug format kemarin).\n"
        f"- Excel `openpyxl`, PPT `python-pptx`. Office doc -> PDF via soffice. JANGAN bilang 'cuma bisa docx'.\n"
        f"- Dokumen formal/buat klien: RAPI & profesional — heading & bullet beneran, no markdown mentah, "
        f"no emoji/checkbox hiasan (jadi kotak kosong di PDF). Hasilnya kirim pakai `MEDIA:<path>`.\n"
        f"- File yang kamu bikin tersimpan di disk (`{repo_path}/docs/` dll). Kalau diminta convert/resend/ulang "
        f"sesuatu yang baru kamu bikin, PAKAI file existing itu — jangan minta user resend, jangan nanya 'yang mana' "
        f"kalau dari konteks udah jelas. Infer, langsung kerjain.\n"
    )

    # Placeholder WhatsApp creds so the gateway's pre-flight pairing check passes.
    # Newer Hermes fatally exits when WhatsApp is enabled but creds.json is absent.
    # Relay-mode containers never pair locally (the bridge proxies through admin and
    # never opens a WA socket), so this file is only there to satisfy the check.
    session_dir = data_dir / "platforms" / "whatsapp" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    creds = session_dir / "creds.json"
    if not creds.exists():
        creds.write_text("{}\n")

    return data_dir


def spawn_container(slug: str, port: int, data_dir: Path, env: dict, proj_ssh_dir: Path,
                    relay_token: str = "") -> str:
    projects_root = env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))
    uid = env.get("HERMES_UID", "1000")
    gid = env.get("HERMES_GID", "1000")
    ninerouter_key = env.get("OPENAI_API_KEY", "")
    home_channel = env.get("WHATSAPP_HOME_CHANNEL", "")
    vroot = f"{projects_root}/viko-agent"   # == REPO_DIR (same path host↔container)

    cmd = [
        "docker", "run", "-d",
        "--name", f"viko-hermes-{slug}",
        "--restart", "unless-stopped",
        "--network", "viko_default",
        "-p", f"127.0.0.1:{port + 900}:9119",
        # ── Volumes ── HARD ISOLATION: only this project's code + its own slice of
        # the viko-agent repo. No full-root mount → cannot cd into other projects.
        "-v", f"{data_dir}:/opt/data",
        "-v", f"{projects_root}/{slug}:{projects_root}/{slug}:rw",
        # viko-agent context — explicit allowlist only (NOT the whole repo, which
        # holds .env secrets, data/ of every container, and other projects/).
        "-v", f"{REPO_DIR}/AGENTS.md:{vroot}/AGENTS.md:ro",
        "-v", f"{REPO_DIR}/rules:{vroot}/rules:ro",
        "-v", f"{REPO_DIR}/soul:{vroot}/soul:ro",
        "-v", f"{REPO_DIR}/skills:{vroot}/skills:ro",
        "-v", f"{REPO_DIR}/projects/{slug}:{vroot}/projects/{slug}:rw",
        # Per-project SSH: only this project's key + 1-alias config (no id_viko,
        # no other {slug}-vps aliases). Cannot reach another project's VPS.
        "-v", f"{proj_ssh_dir}:/opt/data/.ssh:ro",
        "-v", f"{proj_ssh_dir}:/opt/data/home/.ssh:ro",
        "-v", f"{REPO_DIR}/hooks:/opt/data/hooks:ro",
        "-v", f"{REPO_DIR}/skills:/opt/viko/skills:ro",
        # NOTE: mcp-servers/ deliberately NOT mounted — projects-gateway.py exposes
        # cross-project ssh_exec. Project containers must not carry it.
        # Environment
        "-e", f"HERMES_UID={uid}",
        "-e", f"HERMES_GID={gid}",
        "-e", f"OPENAI_BASE_URL=http://viko-9router:20128/v1",
        "-e", f"OPENAI_API_KEY={ninerouter_key}",
        "-e", f"WHATSAPP_HOME_CHANNEL={home_channel}",
        "-e", f"WHATSAPP_RELAY_MODE=true",
        "-e", f"WHATSAPP_RELAY_TARGET=http://viko-hermes:3000",
        "-e", f"WHATSAPP_PORT_FILTER={port}",
        # Relay scope token — admin bridge maps this → the one JID this container
        # may send to. Outbound to any other chat is 403 (surface #1).
        "-e", f"HERMES_RELAY_TOKEN={relay_token}",
        # GITHUB_TOKEN deliberately NOT injected — a broad PAT would let the
        # container clone any repo. Cloning is the admin Hermes's job.
        "-e", f"NINEROUTER_URL=http://viko-9router:20128",
        "-e", f"NINEROUTER_KEY={ninerouter_key}",
        "-e", f"VIKO_PROJECTS_ROOT={projects_root}",
        "-e", f"VIKO_PROJECT_SLUG={slug}",
        # Boot isolation guard: warn (log+tombstone) | enforce (inert on fail) | off.
        # Default warn — flip to enforce in .env once proven across real boots.
        "-e", f"VIKO_ISOLATION_GUARD={env.get('VIKO_ISOLATION_GUARD', 'warn')}",
        "-e", f"SSL_CERT_FILE=/opt/hermes/.venv/lib/python3.13/site-packages/certifi/cacert.pem",
        "-e", f"REQUESTS_CA_BUNDLE=/opt/hermes/.venv/lib/python3.13/site-packages/certifi/cacert.pem",
        "-e", f"HERMES_DASHBOARD=true",
        "-e", f"HERMES_DASHBOARD_INSECURE=true",
        "-e", f"HERMES_DASHBOARD_HOST=127.0.0.1",
        "-e", f"HERMES_DASHBOARD_PORT=9119",
        HERMES_IMAGE,
        "gateway", "run",
    ]

    # Remove existing container if present (idempotent)
    subprocess.run(
        ["docker", "rm", "-f", f"viko-hermes-{slug}"],
        capture_output=True
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _prepare_isolation(slug: str, env: dict, vps_host: str, vps_user: str) -> Path:
    """Resolve VPS, build the per-project SSH dir, and run preflight. Returns the
    per-project ssh dir to mount. Raises (fail-closed) if invariants don't hold."""
    projects_root = Path(env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects")))
    # Pre-create the project's code + context dirs as the current (viko) user, so
    # Docker doesn't auto-create the bind-mount sources as root — which would later
    # block `git clone` into the code dir and context.md writes during onboarding.
    (projects_root / slug).mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "projects" / slug).mkdir(parents=True, exist_ok=True)
    rh, ru = _resolve_vps(slug, vps_host, vps_user)
    if rh:
        print(f"  VPS: {ru}@{rh} (alias {slug}-vps)")
    else:
        print(f"  No VPS resolved for {slug} — ssh disabled for this container")
    proj_ssh_dir = _build_project_ssh_dir(slug, rh, ru)
    preflight(slug, projects_root, proj_ssh_dir, rh)
    return proj_ssh_dir


def main():
    parser = argparse.ArgumentParser(description="Spawn an isolated Hermes container for a project.")
    parser.add_argument("slug")
    parser.add_argument("group_jid")
    parser.add_argument("--vps-host", default="")
    parser.add_argument("--vps-user", default="")
    args = parser.parse_args()

    slug = args.slug.lower().strip()
    group_jid = args.group_jid.strip()

    env = _read_env()
    routing = load_routing()

    proj_ssh_dir = _prepare_isolation(slug, env, args.vps_host.strip(), args.vps_user.strip())

    # Mint a fresh relay token every (re)spawn — rotatable by design.
    relay_token = secrets.token_urlsafe(32)

    if group_jid in routing:
        port = _entry_port(routing[group_jid])
        container_name = f"viko-hermes-{slug}"
        # Always full re-spawn (rm + run) so env var changes take effect.
        # docker restart preserves old env — only docker run applies new vars.
        print(f"\n=== Re-spawning Hermes-{slug} (port {port}) ===")
        data_dir = create_hermes_data_dir(slug, port, group_jid, env)
        # Update routing BEFORE the container starts polling, so the admin bridge
        # has the new token mapped (hot-reload <1s) by the time it relays.
        routing[group_jid] = {"port": port, "slug": slug, "relay_token": relay_token}
        save_routing(routing)
        spawn_container(slug, port, data_dir, env, proj_ssh_dir, relay_token)
        _wait_healthy(container_name)
        print(f"  ✓ Container re-spawned and healthy (relay token rotated)")
        print(f"\nHermes-{slug} running on port {port}")
        print(f"SPAWN_COMPLETE port={port}")
        return

    port = next_port(routing)
    print(f"\n=== Spawning Hermes-{slug} on port {port} ===")

    data_dir = create_hermes_data_dir(slug, port, group_jid, env)
    print(f"  ✓ Config created at {data_dir}")

    routing[group_jid] = {"port": port, "slug": slug, "relay_token": relay_token}
    save_routing(routing)
    print(f"  ✓ routing.json updated (bridge hot-reloads automatically)")

    container_id = spawn_container(slug, port, data_dir, env, proj_ssh_dir, relay_token)
    print(f"  ✓ Container started: {container_id[:12]}")

    print(f"\nHermes-{slug} running on port {port}")
    print(f"Dashboard: http://localhost:{port + 900}")
    print(f"SPAWN_COMPLETE port={port}")


if __name__ == "__main__":
    main()
