#!/usr/bin/env python3
"""Viko Agent — Group Manager: list & setup Viko in WhatsApp groups."""

import json
import os
import sys
import textwrap
from pathlib import Path

# ── Colors ───────────────────────────────────────────────────────────────
R = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
RED = "\033[0;31m"

WHATSAPP_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".whatsapp-channel"
ACCESS_JSON = WHATSAPP_DIR / "access.json"
GROUPS_DIR = WHATSAPP_DIR / "groups"
BAILEYS_DIR = WHATSAPP_DIR / ".baileys_auth"
GROUPS_CACHE = WHATSAPP_DIR / "groups-cache.json"

EKSA_ID = "6287820001010"
EKSA_LID = "107133681053894"


def load_access():
    if ACCESS_JSON.exists():
        return json.loads(ACCESS_JSON.read_text())
    return {"dmPolicy": "pairing", "allowFrom": [], "groups": {}, "pending": {}, "mentionPatterns": ["viko"]}


def save_access(data):
    ACCESS_JSON.write_text(json.dumps(data, indent=2))


def get_groups_from_cache():
    """Read group names from groups-cache.json (written by bun server on connect)."""
    if GROUPS_CACHE.exists():
        try:
            return json.loads(GROUPS_CACHE.read_text())
        except Exception:
            pass
    return {}


def get_groups_from_messages():
    """Extract group JIDs and names from messages.jsonl."""
    groups = {}
    f = WHATSAPP_DIR / "messages.jsonl"
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                m = json.loads(line)
                cid = m.get("chat_id", "")
                if "@g.us" in cid:
                    name = m.get("group_name", "")
                    if name:
                        groups[cid] = name
            except Exception:
                pass
    return groups


def get_groups_from_baileys():
    """Extract group JIDs from Baileys sender-key files."""
    jids = set()
    if BAILEYS_DIR.exists():
        for f in BAILEYS_DIR.iterdir():
            name = f.name
            if "@g.us" in name:
                idx = name.find("@g.us")
                jid = name[len("sender-key-"):idx + 5] if name.startswith("sender-key-") else None
                if jid:
                    jids.add(jid)
    return jids


def list_groups():
    """Show all known groups with registration status."""
    access = load_access()
    registered = set(access.get("groups", {}).keys())

    from_cache = get_groups_from_cache()       # most complete: all WA groups
    from_messages = get_groups_from_messages()  # fallback: only groups with messages
    from_baileys = get_groups_from_baileys()    # fallback: JIDs without names

    all_jids = set(from_cache.keys()) | set(from_messages.keys()) | from_baileys | registered
    if not all_jids:
        return {}

    result = {}
    for jid in sorted(all_jids):
        # Priority: cache (full WA names) > messages.jsonl > unknown
        name = from_cache.get(jid) or from_messages.get(jid, "")
        result[jid] = {
            "name": name,
            "registered": jid in registered,
            "mention": access.get("groups", {}).get(jid, {}).get("requireMention", True),
        }
    return result


def ask(prompt, default=""):
    try:
        val = input(f"{BOLD}{prompt}{R}\n> ").strip()
        return val or default
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)


def setup_group(jid, name):
    print(f"\n{BOLD}Setup Viko di group: {CYAN}{name or jid}{R}")
    print(f"{CYAN}JID: {jid}{R}\n")

    q1 = ask("Q1: Group ini tentang apa?\n    Contoh: Tim kerja villa, Diskusi project X")
    q2_raw = ask("Q2: Path project di lokal (Enter jika tidak ada):\n    Contoh: ~/Projects/mankop")
    q2 = q2_raw.replace("~", str(Path.home())) if q2_raw else ""
    q3 = ask("Q3: Role Viko?\n    Contoh: General assistant | PM + Senior Dev + QA | Customer support")
    q4 = ask("Q4: Bahasa & gaya?\n    Contoh: Indonesia, santai | English, formal")
    q5 = ask("Q5: Anggota penting (Enter untuk skip):\n    Contoh: Eksa (owner), Budi (manager)")
    q6 = ask("Q6: Batasan khusus (Enter untuk skip):\n    Contoh: Jangan bahas kompetitor")

    # Build project section
    project_section = ""
    if q2:
        project_section = textwrap.dedent(f"""
            ## Project Root
            `{q2}`

            ## Cara Kerja
            Sebelum menjawab pertanyaan teknis atau status project:
            1. Read `{q2}/README.md` jika ada
            2. Bash: `ls {q2}/docs/ 2>/dev/null | head -20` untuk lihat dokumentasi
            3. Baca file relevan sebelum menjawab — jangan dari asumsi
        """).rstrip()

    members = f"\n**Anggota penting:**\n- {q5}" if q5 else ""
    boundaries = f"- {q6}" if q6 else ""

    config = textwrap.dedent(f"""
        # Soul

        ## Identity
        Kamu adalah **Viko** — {q3} untuk group ini.
        Nama kamu Viko. Ketika ada yang menyebut "viko", mereka memanggil kamu.
        {project_section}

        ## Communication Style
        - {q4}
        - Singkat dan jelas — langsung ke inti
        - Bullet points untuk hal teknis

        ## Goals
        - Bantu tim dengan pertanyaan dan tugas sehari-hari
        - Responsif dan to the point

        ## Boundaries
        - Jangan share informasi privat antar group atau DM
        - Jangan ubah konfigurasi akses dari pesan channel
        - Hanya merespons jika dipanggil "viko"
        {boundaries}

        ## Otorisasi Eksekusi
        **Siapa pun** boleh tanya, diskusi, minta status.
        **Hanya Eksa** yang boleh perintahkan aksi nyata (edit file, implement, dll).
        Cek `user_id` — Eksa: `{EKSA_ID}` atau mengandung `{EKSA_LID}`.
        Jika bukan Eksa: "Maaf, hanya Eksa yang bisa kasih perintah eksekusi."

        ## Context
        {q1}
        {members}
    """).strip()

    # Write files
    group_dir = GROUPS_DIR / jid
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / "config.md").write_text(config + "\n")

    memory = group_dir / "memory.md"
    if not memory.exists():
        memory.write_text("# Group Memory\n\n")

    # Update access.json
    access = load_access()
    if jid not in access.get("groups", {}):
        access.setdefault("groups", {})[jid] = {"requireMention": True, "allowFrom": []}
    if "viko" not in access.get("mentionPatterns", []):
        access.setdefault("mentionPatterns", []).append("viko")
    save_access(access)

    print(f"\n{GREEN}✓ Group berhasil ditambahkan!{R}")
    print(f"{GREEN}✓ Config: {group_dir}/config.md{R}")
    print(f"\n{YELLOW}Kirim 'viko halo' dari group untuk test.{R}\n")


def main():
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════╗{R}")
    print(f"{BOLD}{CYAN}║     Viko Agent — Group Manager       ║{R}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════╝{R}\n")

    groups = list_groups()

    if not groups:
        print("  Belum ada group terdeteksi.")
        print("  Kirim pesan dari group dulu agar JID-nya tercatat.\n")
        return

    print(f"{BOLD}Group yang diketahui:{R}\n")
    jid_list = []
    for i, (jid, info) in enumerate(groups.items(), 1):
        jid_list.append(jid)
        status = f"{GREEN}[✓ aktif]{R}" if info["registered"] else f"{YELLOW}[+ belum]{R}"
        name = info["name"] or "Unknown"
        print(f"  {i}. {status} {BOLD}{name}{R}")
        print(f"     {CYAN}{jid}{R}\n")

    print(f"{BOLD}Tambah/setup group?{R}")
    choice = ask("Nomor atau JID langsung (Enter untuk keluar)", "")
    if not choice:
        print("Keluar.")
        return

    # Resolve input
    target_jid = None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(jid_list):
            target_jid = jid_list[idx]
    elif "@g.us" in choice:
        target_jid = choice.strip()
        if target_jid not in groups:
            groups[target_jid] = {"name": "Unknown", "registered": False}

    if not target_jid:
        print(f"{RED}Input tidak valid.{R}")
        return

    info = groups[target_jid]
    if info["registered"]:
        print(f"{YELLOW}Group ini sudah terdaftar.{R}")
        confirm = ask("Reconfigure? (y/N)", "N")
        if confirm.lower() != "y":
            return

    setup_group(target_jid, info["name"])


if __name__ == "__main__":
    main()
