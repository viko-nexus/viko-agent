#!/usr/bin/env python3
"""
Spawn a new isolated Hermes container for a project.

Run on the deploy VPS:
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

import re
import json
import shutil
import secrets
import argparse
import subprocess
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


def _detect_repos(projects_root: Path, slug: str) -> list[dict]:
    """Single-repo: slug dir is the repo. Multi-repo: subdirs of slug dir that have .git."""
    slug_dir = projects_root / slug
    if not slug_dir.exists() or (slug_dir / ".git").exists():
        return [{"path": str(slug_dir), "name": slug}]
    subdirs = sorted(d for d in slug_dir.iterdir() if d.is_dir() and (d / ".git").exists())
    if subdirs:
        return [{"path": str(d), "name": d.name} for d in subdirs]
    return [{"path": str(slug_dir), "name": slug}]


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
    # routing.json holds per-project relay_token secrets — lock the dir + file down.
    ROUTING_FILE.parent.chmod(0o700)
    tmp = ROUTING_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(routing, indent=2))
    # chmod the tmp BEFORE rename so the secret is never world-readable, not even
    # in the brief window between write and rename (write_text creates it 0644).
    tmp.chmod(0o600)
    tmp.rename(ROUTING_FILE)
    ROUTING_FILE.chmod(0o600)


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


def _restart_count(name: str) -> int:
    """Container's Docker RestartCount (rises when it crash-loops)."""
    r = subprocess.run(
        ["docker", "inspect", "-f", "{{.RestartCount}}", name],
        capture_output=True, text=True
    )
    try:
        return int(r.stdout.strip()) if r.returncode == 0 else 0
    except ValueError:
        return 0


def _dashboard_ok(name: str) -> bool:
    """True if the container's dashboard answers 200. Probed via `docker exec`
    against the container's OWN localhost:9119, so it works whether this script
    runs on the host OR inside the admin container (docker-out-of-docker). A
    host-port probe (127.0.0.1:{port+900}) is WRONG when spawn runs inside admin:
    127.0.0.1 there is the admin's loopback, not the host, so it never answers."""
    r = subprocess.run(
        ["docker", "exec", name, "sh", "-c",
         "curl -fsS -o /dev/null -w '%{http_code}' http://localhost:9119/ 2>/dev/null"],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and r.stdout.strip() == "200"


def _wait_healthy(name: str, port: int = 0, timeout: int = 90) -> bool:
    """Wait until the container is genuinely up: Running across 2 consecutive
    polls, RestartCount not rising (no crash-loop), and — when a port is given —
    the dashboard HTTP port returns 200. Returns True on success.
    Raises RuntimeError on timeout or detected crash-loop."""
    import time
    deadline = time.time() + timeout
    baseline_restarts = _restart_count(name)
    running_streak = 0
    while time.time() < deadline:
        if _restart_count(name) > baseline_restarts:
            raise RuntimeError(f"Container {name} is crash-looping (RestartCount rose)")
        if _container_running(name):
            running_streak += 1
        else:
            running_streak = 0
        if running_streak >= 2 and (port == 0 or _dashboard_ok(name)):
            return True
        time.sleep(2)
    raise RuntimeError(f"Container {name} did not become healthy within {timeout}s")


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
            m = re.match(r"(?i)\s*(hostname|user|port)\s+(\S+)", line)
            if m:
                out.setdefault(m.group(1).lower(), m.group(2))
    return out


def _resolve_vps(slug: str, vps_host: str, vps_user: str, vps_port: str = "22") -> tuple:
    """Resolve (vps_host, vps_user, vps_port) from args, then per-project config, then
    the legacy shared config. Returns ('', '', '') if this project has no VPS."""
    if vps_host:
        return vps_host, (vps_user or "viko-exec"), (vps_port or "22")

    proj_cfg = SSH_PROJECTS_DIR / slug / "config"
    if proj_cfg.exists():
        d = _parse_ssh_host_block(proj_cfg.read_text(), f"{slug}-vps", f"{slug}-prod")
        if d.get("hostname"):
            return d["hostname"], d.get("user", "viko-exec"), d.get("port", "22")

    shared = SSH_DIR / "config"
    if shared.exists():
        d = _parse_ssh_host_block(shared.read_text(), f"{slug}-vps", f"{slug}-prod")
        if d.get("hostname"):
            return d["hostname"], d.get("user", "viko-exec"), d.get("port", "22")

    return "", "", ""


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


def _build_project_ssh_dir(slug: str, vps_host: str, vps_user: str, vps_port: str = "22") -> Path:
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
        # Only emit Port when non-default (22) to keep the config minimal.
        port_line = f"    Port {vps_port}\n" if vps_port and vps_port != "22" else ""
        (proj_dir / "config").write_text(
            f"Host {slug}-vps {slug}-prod\n"
            f"    HostName {vps_host}\n"
            f"    User {vps_user}\n"
            f"{port_line}"
            f"    IdentityFile /opt/data/.ssh/id_viko\n"
            f"    IdentitiesOnly yes\n"
            f"    StrictHostKeyChecking accept-new\n"
            f"    UserKnownHostsFile /opt/data/.ssh/known_hosts\n"
            # Non-interactive + bounded: the agent never sits interactively, so a hung
            # connect (unreachable host, key prompt) must fail fast instead of blocking
            # a terminal tool call for minutes (which stalls the whole agent loop).
            f"    BatchMode yes\n"
            f"    ConnectTimeout 10\n"
            f"    ServerAliveInterval 5\n"
            f"    ServerAliveCountMax 2\n"
        )
    else:
        (proj_dir / "config").write_text("# no VPS configured for this project\n")

    # Pre-seed known_hosts from the shared file so accept-new doesn't need to
    # write into the read-only mount on first connect. Also seed github.com so
    # the container can `git push` over SSH (scoped per-repo deploy key).
    #
    # We write the seed to the real known_hosts file first, then use
    # `ssh-keygen -F <host> -f <file>` to test membership — it does a proper
    # host-key-line lookup (handles hashed entries + the [host]:port form), so it
    # won't false-skip the way a naive `host in text` substring test does when one
    # IP/host is a substring of an already-seeded entry.
    kh_path = proj_dir / "known_hosts"
    shared_kh = SSH_DIR / "known_hosts"
    kh_path.write_text(shared_kh.read_text() if shared_kh.exists() else "")

    def _kh_has(host: str) -> bool:
        return _run(["ssh-keygen", "-F", host, "-f", str(kh_path)]).returncode == 0

    def _kh_append(text: str) -> None:
        if text:
            with kh_path.open("a") as fh:
                fh.write(text)

    if not _kh_has("github.com"):
        try:
            _kh_append(_run(["ssh-keyscan", "-t", "ed25519", "github.com"]).stdout)
        except Exception:
            pass
    # Pre-seed the project VPS host key too. Without it, the first `ssh {slug}-prod`
    # over the read-only known_hosts mount can't accept-new (can't write), so the agent
    # improvises `ssh-keyscan >> known_hosts` — which trips the dangerous-command guard
    # and still fails. Seeding here makes the very first connect trusted and silent.
    # When a non-default port is in play, ssh stores the key under the [host]:port
    # token, so probe with that exact form.
    if vps_host:
        kh_lookup = vps_host
        scan = ["ssh-keyscan"]
        if vps_port and vps_port != "22":
            scan += ["-p", str(vps_port)]
            kh_lookup = f"[{vps_host}]:{vps_port}"
        scan += [vps_host]
        if not _kh_has(kh_lookup):
            try:
                _kh_append(_run(scan).stdout)
            except Exception:
                pass
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
        host_lines = [ln for ln in cfg.read_text().splitlines() if ln.strip().lower().startswith("host ")]
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


def _build_project_config(slug: str, group_jid: str, env: dict, workspace: str = "") -> dict:
    ninerouter_url = env.get("OPENAI_BASE_URL", "http://viko-9router:20128/v1")
    ninerouter_key = env.get("OPENAI_API_KEY", "")
    projects_root = env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))
    # Scope the terminal to THIS project's workspace, never the projects ROOT
    # (whose siblings are other projects) — defense-in-depth against cd-ing out.
    terminal_cwd = workspace or f"{projects_root}/{slug}"

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
        # Auto-record every browser session to browser_recordings/*.webm. The
        # viko-media-autosend hook converts the freshest recording to mp4 and
        # sends it when a reply signals a video/recording was produced — so
        # "record a browser test and send the video" works without the model
        # having to drive recording or know its own chat id.
        "browser": {"record_sessions": True},
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
            "cwd": terminal_cwd
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

    # Agent git config (HOME=/opt/data/home). Trust all mounted repos, set the Viko
    # identity, and pin the per-project SSH key so git pull/commit/push just works.
    projects_root = env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects"))
    projects_root_path = Path(projects_root)
    workspace = f"{projects_root}/{slug}"
    repos = _detect_repos(projects_root_path, slug)
    safe_dirs = "\n".join(f"\tdirectory = {r['path']}" for r in repos)
    (home_dir / ".gitconfig").write_text(
        f"[safe]\n{safe_dirs}\n"
        f"[user]\n\tname = Viko\n\temail = viko-{slug}@local\n"
        f"[core]\n\tsshCommand = ssh -i /opt/data/.ssh/id_viko -o IdentitiesOnly=yes "
        f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/opt/data/.ssh/known_hosts\n"
        f"[init]\n\tdefaultBranch = main\n"
    )
    if len(repos) == 1 and repos[0]["path"] == workspace:
        git_section = (
            f"- Repo project ini SUDAH ke-clone lokal di `{workspace}`. `cd` ke situ buat baca/edit/jalanin/build kode. "
            f"JANGAN clone ulang, JANGAN ke /tmp.\n"
            f"- Git udah dikonfigurasi (identity Viko, key `/opt/data/.ssh/id_viko`, repo di-trust). "
            f"Tinggal `git pull/add/commit/push` dari DALAM repo — jangan bikin key baru / ngarang path key.\n"
        )
    else:
        repo_list = "\n".join(f"  - `{r['path']}/` — **{r['name']}**" for r in repos)
        git_section = (
            f"- Workspace project di `{workspace}/` berisi beberapa repo:\n{repo_list}\n"
            f"  Tentukan repo yang relevan dari konteks task; kalau ambigu, tanya dulu sebelum eksekusi.\n"
            f"  JANGAN clone ulang, JANGAN ke /tmp.\n"
            f"- Git dikonfigurasi untuk semua repo (identity Viko, key `/opt/data/.ssh/id_viko`, semua repo di-trust). "
            f"Tinggal `git pull/add/commit/push` dari DALAM repo masing-masing — jangan bikin key baru / ngarang path key.\n"
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

    # Write config.yaml. JSON is a strict subset of YAML, so emitting JSON keeps this
    # script pure-stdlib (no PyYAML import) — it then runs under any python3, including
    # the container's system interpreter which lacks pyyaml. Hermes loads it via a YAML
    # parser, which reads the JSON form identically.
    config = _build_project_config(slug, group_jid, env, workspace)
    (data_dir / "config.yaml").write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n"
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
        f"- **Ramah & hangat** ke siapa pun — tapi **baca situasi**: pas santai boleh witty, "
        f"pas ada insiden/bug/hal serius fokus dan to-the-point, tahan dulu bercandanya.\n"
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
        f"## Sikap Kerja — Teliti & Kritis terhadap Bug\n"
        f"- **Teliti**: cek detail, baca kode/error/output beneran sebelum nyimpulin. "
        f"Jangan asal 'kayaknya udah jalan' — verifikasi dulu, baru ngomong selesai.\n"
        f"- **Kritis terhadap bug**: curigai edge case, asumsi yang belum diuji, dan happy-path semu. "
        f"Kalau ada yang janggal di kode/PR/permintaan, angkat — jangan diem demi enak.\n"
        f"- Lebih baik nemu masalah sekarang daripada meledak di prod. "
        f"Tapi sampaikan dengan cara membangun, bukan nge-judge.\n\n"
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
        f"## Konteks Project\n"
        f"- Detail project (repo, server, members) ada di "
        f"`{projects_root}/viko-agent/projects/{slug}/context.md`. Baca file itu di AWAL "
        f"biar langsung paham setup-nya — jangan nanya hal yang udah ada di situ.\n\n"
        f"## Project & Git (dev)\n"
        f"{git_section}"
        f"- SSH ke server project: pakai alias `{slug}-prod` (config + key `/opt/data/.ssh/id_viko` udah siap). "
        f"Contoh: `ssh {slug}-prod 'perintah'`. Jangan ngarang host/user/key.\n"
        f"- **Akses DB lewat SSH TUNNEL** (DB gak ke-expose publik, jangan konek langsung): "
        f"baca `DATABASE_URL` dari file `.env` project DI SERVER (`ssh {slug}-prod 'grep DATABASE_URL <path>/.env'`), "
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
        f"`MEDIA:{workspace}/docs/quotation/QUOTATION_FINAL.pdf`\n"
        f"- Kirim SCREENSHOT halaman web: kamu HARUS beneran panggil tool `browser_screenshot` "
        f"(dia balikin `screenshot_path`), lalu tulis `MEDIA:<screenshot_path>`. Snapshot teks/accessibility itu "
        f"buat ANALISIS kamu doang — JANGAN ngaku/jelasin screenshot yang gak kamu capture.\n"
        f"- JANGAN bilang 'ga support / API limitation' — SALAH. Credential (.env/.ssh/key) doang yang diblok.\n\n"
        f"## Generate & Convert File\n"
        f"- Dokumen ber-FORMAT: tulis kontennya sebagai **Markdown**, lalu render pakai **pandoc** biar "
        f"heading/bold/bullet/tabel jadi format BENERAN: `pandoc input.md -o output.docx` lalu "
        f"`soffice --headless --convert-to pdf output.docx`. JANGAN convert `.md` langsung lewat soffice — "
        f"`**`/`#`/`---` bakal jadi teks mentah & keliatan rusak buat orang awam (itu bug format kemarin).\n"
        f"- Excel `openpyxl`, PPT `python-pptx`. Office doc -> PDF via soffice. JANGAN bilang 'cuma bisa docx'.\n"
        f"- Dokumen formal/buat klien: RAPI & profesional — heading & bullet beneran, no markdown mentah, "
        f"no emoji/checkbox hiasan (jadi kotak kosong di PDF). Hasilnya kirim pakai `MEDIA:<path>`.\n"
        f"- File yang kamu bikin tersimpan di disk (`{workspace}/docs/` dll). Kalau diminta convert/resend/ulang "
        f"sesuatu yang baru kamu bikin, PAKAI file existing itu — jangan minta user resend, jangan nanya 'yang mana' "
        f"kalau dari konteks udah jelas. Infer, langsung kerjain.\n\n"
        f"## Record Video (browser/playwright)\n"
        f"- Kamu BISA record sesi browser/playwright + kirim sebagai video. Sesi browser kamu "
        f"**OTOMATIS terekam** (`record_sessions` aktif) ke `browser_recordings/*.webm` — kamu gak perlu "
        f"start/stop record manual.\n"
        f"- Alur: jalanin test/navigasi pakai tool browser seperti biasa -> **`browser close`** "
        f"(ini nyimpen rekaman) -> di balasan sebut hasilnya + kata **'video'/'rekaman'**. Sistem otomatis "
        f"convert webm->mp4 + kirim ke chat. Gak perlu kirim `MEDIA:` manual buat video.\n"
        f"- Kalau mau kirim eksplisit/sekarang juga: jalanin `viko-send-video <chatId> \"<caption>\"` "
        f"(dia ambil rekaman terbaru, convert mp4, kirim).\n"
        f"- JANGAN kirim `.webm` mentah (WA kadang gak render — sistem udah convert ke mp4). "
        f"JANGAN bilang 'gak bisa record'.\n"
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

    # proj_ssh_dir is a HERMES_HOME-relative path (/opt/data/home/.viko/ssh/...) when this
    # script runs INSIDE the hermes container. `docker run` resolves -v SOURCES on the HOST,
    # where /opt/data is bind-mounted from {REPO_DIR}/data/hermes (see docker-compose.yml).
    # Translate so the SSH mount source is a real host path (docker-out-of-docker). On a host
    # without that prefix (script run directly on a VPS), the replace is a harmless no-op.
    proj_ssh_src = str(proj_ssh_dir).replace("/opt/data", f"{REPO_DIR}/data/hermes", 1)

    cmd = [
        "docker", "run", "-d",
        "--name", f"viko-hermes-{slug}",
        "--restart", "unless-stopped",
        # Cap per-project container logs so they can't grow unbounded on the host.
        "--log-opt", "max-size=10m",
        "--log-opt", "max-file=3",
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
        "-v", f"{proj_ssh_src}:/opt/data/.ssh:ro",
        "-v", f"{proj_ssh_src}:/opt/data/home/.ssh:ro",
        "-v", f"{REPO_DIR}/hooks:/opt/data/hooks:ro",
        "-v", f"{REPO_DIR}/skills:/opt/viko/skills:ro",
        # WhatsApp bridge — bind-mount the repo's relay-aware bridge over the image's
        # baked copy, same as the admin's docker-compose.override.yml. Project containers
        # then always run the CURRENT bridge (relay mode, mention gate, LID resolution)
        # without needing an image rebuild on every bridge edit. The baked copy is only
        # a fallback. Host-identical path → valid as a docker-run source on host + VPS.
        "-v", f"{REPO_DIR}/patches/whatsapp-bridge.js:/opt/hermes/scripts/whatsapp-bridge/bridge.js:ro",
        # NOTE: mcp-servers/ deliberately NOT mounted — projects-gateway.py exposes
        # cross-project ssh_exec. Project containers must not carry it.
        # Environment
        "-e", f"HERMES_UID={uid}",
        "-e", f"HERMES_GID={gid}",
        "-e", "OPENAI_BASE_URL=http://viko-9router:20128/v1",
        "-e", f"OPENAI_API_KEY={ninerouter_key}",
        "-e", f"WHATSAPP_HOME_CHANNEL={home_channel}",
        "-e", "WHATSAPP_RELAY_MODE=true",
        "-e", "WHATSAPP_RELAY_TARGET=http://viko-hermes:3000",
        "-e", f"WHATSAPP_PORT_FILTER={port}",
        # Relay scope token — admin bridge maps this → the one JID this container
        # may send to. Outbound to any other chat is 403 (surface #1).
        "-e", f"HERMES_RELAY_TOKEN={relay_token}",
        # GITHUB_TOKEN deliberately NOT injected — a broad PAT would let the
        # container clone any repo. Cloning is the admin Hermes's job.
        "-e", "NINEROUTER_URL=http://viko-9router:20128",
        "-e", f"NINEROUTER_KEY={ninerouter_key}",
        "-e", f"VIKO_PROJECTS_ROOT={projects_root}",
        "-e", f"VIKO_PROJECT_SLUG={slug}",
        # Boot isolation guard: warn (log+tombstone) | enforce (inert on fail) | off.
        # Default enforce — fail-closed; override to warn/off in .env if ever needed.
        "-e", f"VIKO_ISOLATION_GUARD={env.get('VIKO_ISOLATION_GUARD', 'enforce')}",
        "-e", "SSL_CERT_FILE=/opt/hermes/.venv/lib/python3.13/site-packages/certifi/cacert.pem",
        "-e", "REQUESTS_CA_BUNDLE=/opt/hermes/.venv/lib/python3.13/site-packages/certifi/cacert.pem",
        "-e", "HERMES_DASHBOARD=true",
        "-e", "HERMES_DASHBOARD_INSECURE=true",
        "-e", "HERMES_DASHBOARD_HOST=127.0.0.1",
        "-e", "HERMES_DASHBOARD_PORT=9119",
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


def _prepare_isolation(
    slug: str, env: dict, vps_host: str, vps_user: str, vps_port: str = "22"
) -> Path:
    """Resolve VPS, build the per-project SSH dir, and run preflight. Returns the
    per-project ssh dir to mount. Raises (fail-closed) if invariants don't hold."""
    projects_root = Path(env.get("VIKO_PROJECTS_ROOT", str(Path.home() / "Projects")))
    # Pre-create the project's code + context dirs as the current (viko) user, so
    # Docker doesn't auto-create the bind-mount sources as root — which would later
    # block `git clone` into the code dir and context.md writes during onboarding.
    (projects_root / slug).mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "projects" / slug).mkdir(parents=True, exist_ok=True)
    rh, ru, rp = _resolve_vps(slug, vps_host, vps_user, vps_port)
    if rh:
        print(f"  VPS: {ru}@{rh}:{rp} (alias {slug}-vps)")
    else:
        print(f"  No VPS resolved for {slug} — ssh disabled for this container")
    proj_ssh_dir = _build_project_ssh_dir(slug, rh, ru, rp)
    preflight(slug, projects_root, proj_ssh_dir, rh)
    return proj_ssh_dir


def main():
    parser = argparse.ArgumentParser(description="Spawn an isolated Hermes container for a project.")
    parser.add_argument("slug")
    parser.add_argument("group_jid")
    parser.add_argument("--vps-host", default="")
    parser.add_argument("--vps-user", default="")
    parser.add_argument("--vps-port", default="22")
    args = parser.parse_args()

    slug = args.slug.lower().strip()
    group_jid = args.group_jid.strip()

    env = _read_env()
    routing = load_routing()

    proj_ssh_dir = _prepare_isolation(
        slug, env, args.vps_host.strip(), args.vps_user.strip(), args.vps_port.strip()
    )

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
        _wait_healthy(container_name, port)
        print("  ✓ Container re-spawned and healthy (relay token rotated)")
        print(f"\nHermes-{slug} running on port {port}")
        print(f"SPAWN_COMPLETE port={port}")
        return

    port = next_port(routing)
    print(f"\n=== Spawning Hermes-{slug} on port {port} ===")

    data_dir = create_hermes_data_dir(slug, port, group_jid, env)
    print(f"  ✓ Config created at {data_dir}")

    routing[group_jid] = {"port": port, "slug": slug, "relay_token": relay_token}
    save_routing(routing)
    print("  ✓ routing.json updated (bridge hot-reloads automatically)")

    container_id = spawn_container(slug, port, data_dir, env, proj_ssh_dir, relay_token)
    print(f"  ✓ Container started: {container_id[:12]}")

    # Wait for genuine health before declaring success. routing.json was already
    # written for this group_jid, so a dead container would otherwise leave an
    # orphan route pointing at nothing — roll it back before re-raising.
    try:
        _wait_healthy(f"viko-hermes-{slug}", port)
    except Exception:
        routing.pop(group_jid, None)
        save_routing(routing)
        raise
    print("  ✓ Container healthy")

    print(f"\nHermes-{slug} running on port {port}")
    print(f"Dashboard: http://localhost:{port + 900}")
    print(f"SPAWN_COMPLETE port={port}")


if __name__ == "__main__":
    main()
