#!/usr/bin/env python3
"""Patch Hermes gateway to auto-route messages to viko-chat or viko-code combo.

Chat / casual messages → cc/claude-haiku (viko-chat combo)
Code / debug / analysis → cc/claude-sonnet (viko-code combo)
Both combos fall back to Groq if Claude is unavailable.

Manual /model switches are preserved — this patch only fires when no
user-initiated override is active.
"""
import sys
from pathlib import Path

HERMES_HOME = Path("/opt/hermes")
TARGET = HERMES_HOME / "gateway" / "run.py"

# Injected right after session_key is resolved, before agent is created.
# Classifies the message content and sets _session_model_overrides accordingly.
INJECT_AFTER = (
    'session_entry = self.session_store.get_or_create_session(source)\n'
    '        session_key = session_entry.session_key\n'
    '        self._cache_session_source(session_key, source)'
)

INJECT_CODE = (
    'session_entry = self.session_store.get_or_create_session(source)\n'
    '        session_key = session_entry.session_key\n'
    '        self._cache_session_source(session_key, source)\n'
    '        # VIKO PATCH: task-based model routing\n'
    '        _vr_existing = self._session_model_overrides.get(session_key, {})\n'
    '        if not _vr_existing or _vr_existing.get("_viko_auto"):\n'
    '            _vr_text = (event.text or "").lower()\n'
    '            _vr_code_kws = [\n'
    '                "debug","fix","bug","error","exception","code","function","class",\n'
    '                "implement","develop","analyze","analyse","review","refactor",\n'
    '                "optimize","performance","architecture","algorithm","logic",\n'
    '                "backend","frontend","database","query","sql","api","endpoint",\n'
    '                "test","script","parse","migration","schema","component","type",\n'
    '                "interface","deploy","dockerfile","yaml","json","config",\n'
    '                "perbaiki","kode","fungsi","kelas","implementasi","analisa",\n'
    '                "analisis","cek data","cek kode","deploy","database","kueri",\n'
    '                "tes","skrip","optimasi","performa","arsitektur","desain",\n'
    '                "algoritma","logika","migrasi","skema","komponen","endpoint",\n'
    '                "tiket","kanban","approve","kerjakan","selesaikan","tutup tiket",\n'
    '                "browser","screenshot","rekam","rekaman","video","capture","record",\n'
    '            ]\n'
    '            import re as _vr_re\n'
    '            _vr_code_re = _vr_re.compile(\n'
    '                r"\\b(" + "|".join(_vr_re.escape(_k) for _k in _vr_code_kws) + r")\\b"\n'
    '            )\n'
    '            _vr_is_code = bool(_vr_code_re.search(_vr_text))\n'
    '            _vr_model = "viko-code" if _vr_is_code else "viko-chat"\n'
    '            self._session_model_overrides[session_key] = {\n'
    '                "model": _vr_model,\n'
    '                "provider": "openai",\n'
    '                "api_key": os.environ.get("OPENAI_API_KEY", ""),\n'
    '                "base_url": os.environ.get("OPENAI_BASE_URL", "http://viko-9router:20128/v1"),\n'
    '                "api_mode": None,\n'
    '                "_viko_auto": True,\n'
    '            }\n'
    '        # END VIKO PATCH'
)


def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")

    if INJECT_AFTER not in content:
        if INJECT_CODE in content:
            print("✓ patch-model-router: already applied")
            return
        print("WARNING: injection point not found (Hermes may have updated upstream)")
        sys.exit(0)

    content = content.replace(INJECT_AFTER, INJECT_CODE, 1)
    TARGET.write_text(content, encoding="utf-8")
    print("✓ patch-model-router: applied (chat→haiku, code→sonnet routing)")


if __name__ == "__main__":
    main()
