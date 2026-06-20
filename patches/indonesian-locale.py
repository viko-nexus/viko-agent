#!/usr/bin/env python3
"""
Patch: Add Indonesian locale and translate hardcoded system messages.
Applied at Docker build time.
"""
import sys
from pathlib import Path

HERMES_DIR = Path("/opt/hermes")

# ── 1. Create id.yaml locale file ─────────────────────────────────────────────

ID_YAML = """\
# Hermes static-message catalog -- Indonesian (id)
# Translated from en.yaml for Viko agent

approval:
  dangerous_header: "⚠️  PERINTAH BERBAHAYA: {description}"
  choose_long:     "      [o]nce  |  [s]ession  |  [a]lways  |  [d]eny"
  choose_short:    "      [o]nce  |  [s]ession  |  [d]eny"
  prompt_long:     "      Pilihan [o/s/a/D]: "
  prompt_short:    "      Pilihan [o/s/D]: "
  timeout:         "      ⏱ Timeout - perintah ditolak"
  allowed_once:    "      ✓ Diizinkan sekali"
  allowed_session: "      ✓ Diizinkan untuk sesi ini"
  allowed_always:  "      ✓ Ditambahkan ke daftar izin permanen"
  denied:          "      ✗ Ditolak"
  cancelled:       "      ✗ Dibatalkan"
  blocklist_message: "Perintah ini ada di daftar blokir dan tidak bisa diizinkan."

gateway:
  approval_expired: "⚠️ Persetujuan kedaluwarsa (agen tidak lagi menunggu). Minta agen untuk mencoba lagi."
  draining:         "⏳ Menunggu {count} agen aktif selesai sebelum restart..."
  goal_cleared:     "✓ Goal dihapus."
  no_active_goal:   "Tidak ada goal aktif."
  config_read_failed: "⚠️ Tidak bisa membaca config.yaml: {error}"
  config_save_failed: "⚠️ Tidak bisa menyimpan config: {error}"

  model:
    error_prefix:           "Error: {error}"
    switched:               "Model diganti ke `{model}`"
    provider_label:         "Provider: {provider}"
    context_label:          "Context: {tokens} tokens"
    max_output_label:       "Max output: {tokens} tokens"
    cost_label:             "Biaya: {cost}"
    capabilities_label:     "Kemampuan: {capabilities}"
    prompt_caching_enabled: "Prompt caching: aktif"
    warning_prefix:         "Peringatan: {warning}"
    saved_global:           "Disimpan ke config.yaml (`--global`)"
    session_only_hint:      "_(sesi ini saja — tambah `--global` untuk menyimpan permanen)_"
    current_label:          "Saat ini: `{model}` pada {provider}"
    current_tag:            " (saat ini)"
    more_models_suffix:     " (+{count} lagi)"
    usage_switch_model:     "`/model <nama>` — ganti model"
    usage_switch_provider:  "`/model <nama> --provider <slug>` — ganti provider"
    usage_persist:          "`/model <nama> --global` — simpan permanen"

  agents:
    header:                "🤖 **Agen & Tugas Aktif**"
    active_agents:         "**Agen aktif:** {count}"
    this_chat:             " · chat ini"
    more:                  "... dan {count} lagi"
    running_processes:     "**Proses background berjalan:** {count}"
    async_jobs:            "**Gateway async jobs:** {count}"
    none:                  "Tidak ada agen aktif atau tugas berjalan."
    state_starting:        "memulai"
    state_running:         "berjalan"

  approve:
    no_pending:            "Tidak ada perintah menunggu persetujuan."
    once_singular:         "✅ Perintah disetujui. Agen melanjutkan..."
    once_plural:           "✅ Perintah disetujui ({count} perintah). Agen melanjutkan..."
    session_singular:      "✅ Perintah disetujui (pola disetujui untuk sesi ini). Agen melanjutkan..."
    session_plural:        "✅ Perintah disetujui (pola disetujui untuk sesi ini) ({count} perintah). Agen melanjutkan..."
    always_singular:       "✅ Perintah disetujui (pola disetujui permanen). Agen melanjutkan..."
    always_plural:         "✅ Perintah disetujui (pola disetujui permanen) ({count} perintah). Agen melanjutkan..."

  background:
    usage:                 "Penggunaan: /background <prompt>\\nContoh: /background Rangkum berita HN hari ini\\n\\nMenjalankan prompt di sesi terpisah. Kamu bisa terus chat — hasilnya akan muncul di sini saat selesai."
    started:               "🔄 Tugas background dimulai: \\"{preview}\\"\\nTask ID: {task_id}\\nKamu bisa terus chat — hasil akan muncul saat selesai."

  branch:
    db_unavailable:        "Database sesi tidak tersedia."
    no_conversation:       "Tidak ada percakapan untuk di-branch — kirim pesan dulu."
    create_failed:         "Gagal membuat branch: {error}"
    switch_failed:         "Branch dibuat tapi gagal berpindah ke sana."
    branched_one:          "⑂ Branch ke **{title}** ({count} pesan disalin)\\nAsli: `{parent}`\\nBranch: `{new}`\\nGunakan `/resume` untuk kembali ke yang asli."
    branched_many:         "⑂ Branch ke **{title}** ({count} pesan disalin)\\nAsli: `{parent}`\\nBranch: `{new}`\\nGunakan `/resume` untuk kembali ke yang asli."

  commands:
    usage:                 "Penggunaan: `/commands [halaman]`"
    skill_header:          "⚡ **Perintah Skill:**"
    default_desc:          "Perintah skill"
    none:                  "Tidak ada perintah tersedia."
    header:                "📚 **Perintah** ({total} total, halaman {page}/{total_pages})"
    nav_prev:              "`/commands {page}` ← sebelumnya"
    nav_next:              "berikutnya → `/commands {page}`"
    out_of_range:          "_(Halaman {requested} tidak ada, menampilkan halaman {page}.)_"

  compress:
    not_enough:            "Percakapan terlalu pendek untuk dikompresi (butuh minimal 4 pesan)."
    no_provider:           "Tidak ada provider — tidak bisa mengompresi."
    nothing_to_do:         "Belum ada yang perlu dikompresi."
    focus_line:            "Fokus: \\"{topic}\\""
    summary_failed:        "⚠️ Gagal membuat ringkasan ({error}). {count} pesan lama dihapus dan diganti placeholder."
    aborted:               "⚠️ Kompresi dibatalkan ({error}). Tidak ada pesan yang dihapus."
    aux_failed:            "ℹ️ Model kompresi `{model}` gagal ({error}). Menggunakan model utama sebagai gantinya."
    failed:                "Kompresi gagal: {error}"

  deny:
    stale:                 "❌ Perintah ditolak (persetujuan sudah kedaluwarsa)."
    no_pending:            "Tidak ada perintah yang menunggu untuk ditolak."
    denied_singular:       "❌ Perintah ditolak."
    denied_plural:         "❌ Perintah ditolak ({count} perintah)."

  goal:
    unavailable:           "Goal tidak tersedia di sesi ini."
    no_goal_set:           "Tidak ada goal yang diset."
    paused:                "⏸ Goal dijeda: {goal}"
    no_resume:             "Tidak ada goal untuk dilanjutkan."
    resumed:               "▶ Goal dilanjutkan: {goal}\\nKirim pesan untuk melanjutkan."
    invalid:               "Goal tidak valid: {error}"
    set:                   "⊙ Goal diset (budget {budget} giliran): {goal}\\nSaya akan terus bekerja sampai goal selesai atau budget habis.\\nKontrol: /goal status · /goal pause · /goal resume · /goal clear"

  help:
    header:                "📖 **Perintah Viko**\\n"
    skill_header:          "\\n⚡ **Perintah Skill** ({count} aktif):"
    more_use_commands:     "\\n... dan {count} lagi. Gunakan `/commands` untuk daftar lengkap."

  reset:
    header_default:        "✨ Sesi direset! Mulai dari awal."
    header_new:            "✨ Sesi baru dimulai!"
    header_titled:         "✨ Sesi baru dimulai: {title}"
    title_rejected:        "\\n⚠️ Judul ditolak: {error}"
    title_error_untitled:  "\\n⚠️ {error} — sesi dimulai tanpa judul."
    title_empty_untitled:  "\\n⚠️ Judul kosong setelah dibersihkan — sesi dimulai tanpa judul."
    tip:                   "\\n✦ Tips: {tip}"

  restart:
    in_progress:           "⏳ Gateway sedang restart..."
    restarting:            "♻ Merestart gateway. Jika tidak ada notifikasi dalam 60 detik, restart manual dengan `hermes gateway restart`."

  resume:
    db_unavailable:        "Database sesi tidak tersedia."
    parse_error:           "⚠️ Tidak bisa memproses argumen `/resume`: {error}."
    no_named_sessions:     "Tidak ada sesi bernama.\\nGunakan `/title Nama Sesi` untuk memberi nama sesi, lalu `/resume Nama Sesi` untuk kembali ke sana nanti."
    list_header:           "📋 **Sesi Bernama**\\n"
    list_item:             "• **{title}**{preview_part}"
    list_item_numbered:    "{index}. **{title}**{preview_part}"
    list_preview_suffix:   " — _{preview}_"
    list_footer:           "\\nPenggunaan: `/resume <nama sesi>`"
    list_footer_numbered:  "\\nPenggunaan: `/resume <nama sesi>` atau `/resume <nomor>`"
    list_failed:           "Tidak bisa mendaftar sesi: {error}"
    out_of_range:          "Indeks resume {index} di luar jangkauan."
    not_found:             "Tidak ada sesi yang cocok dengan '**{name}**'."
    already_on:            "📌 Sudah di sesi **{name}**."
    switch_failed:         "Gagal berpindah sesi."
    resumed_one:           "↻ Melanjutkan sesi **{title}** ({count} pesan). Percakapan dipulihkan."
    resumed_many:          "↻ Melanjutkan sesi **{title}** ({count} pesan). Percakapan dipulihkan."
    resumed_no_count:      "↻ Melanjutkan sesi **{title}**. Percakapan dipulihkan."

  retry:
    no_previous:           "Tidak ada pesan sebelumnya untuk dicoba ulang."

  set_home:
    save_failed:           "Gagal menyimpan home channel: {error}"
    success:               "✅ Home channel diset ke **{name}** (ID: {chat_id}).\\nHasil cron dan pesan lintas-platform akan dikirim ke sini."

  stop:
    stopped_pending:       "⚡ Dihentikan. Agen belum mulai — kamu bisa melanjutkan sesi ini."
    stopped:               "⚡ Dihentikan. Kamu bisa melanjutkan sesi ini."
    no_active:             "Tidak ada tugas aktif untuk dihentikan."

  title:
    db_unavailable:        "Database sesi tidak tersedia."
    warn_prefix:           "⚠️ {error}"
    empty_after_clean:     "⚠️ Judul kosong setelah dibersihkan. Gunakan karakter yang bisa dicetak."
    set_to:                "✏️ Judul sesi diset: **{title}**"
    not_found:             "Sesi tidak ditemukan di database."
    current_with_title:    "📌 Sesi: `{session_id}`\\nJudul: **{title}**"
    current_no_title:      "📌 Sesi: `{session_id}`\\nBelum ada judul. Penggunaan: `/title Nama Sesi Saya`"

  undo:
    nothing:               "Tidak ada yang bisa di-undo."
    removed:               "↩️ Undo {turns} giliran ({count} pesan).\\nKembali ke: \\"{preview}\\""
    invalid_count:         "Jumlah tidak valid \\"{arg}\\" — gunakan /undo atau /undo N."

  update:
    platform_not_messaging:  "✗ /update hanya tersedia dari platform messaging. Jalankan `hermes update` dari terminal."
    not_git_repo:            "✗ Bukan git repository — tidak bisa update."
    start_failed:            "✗ Gagal memulai update: {error}"
    starting:                "⚕ Memulai update Hermes… Progress akan ditampilkan di sini."

  usage:
    header_session:           "📊 **Penggunaan Token Sesi**"
    label_model:              "Model: `{model}`"
    label_input_tokens:       "Token input: {count}"
    label_cache_read:         "Token cache read: {count}"
    label_cache_write:        "Token cache write: {count}"
    label_output_tokens:      "Token output: {count}"
    label_total:              "Total: {count}"
    label_api_calls:          "Panggilan API: {count}"
    label_cost:               "Biaya: {prefix}${amount}"
    label_cost_included:      "Biaya: sudah termasuk"
    label_context:            "Context: {used} / {total} ({pct}%)"
    label_compressions:       "Kompresi: {count}"
    header_session_info:      "📊 **Info Sesi**"
    label_messages:           "Pesan: {count}"
    label_estimated_context:  "Estimasi context: ~{count} tokens"
    detailed_after_first:     "_(Detail penggunaan tersedia setelah respons agen pertama)_"
    no_data:                  "Tidak ada data penggunaan untuk sesi ini."

  yolo:
    disabled:                   "⚠️ Mode YOLO **OFF** untuk sesi ini — perintah berbahaya memerlukan persetujuan."
    enabled:                    "⚡ Mode YOLO **ON** untuk sesi ini — semua perintah disetujui otomatis. Gunakan dengan hati-hati."

  shared:
    session_db_unavailable:      "Database sesi tidak tersedia."
    session_db_unavailable_prefix: "Database sesi tidak tersedia"
    session_not_found:           "Sesi tidak ditemukan di database."
    warn_passthrough:            "⚠️ {error}"
"""

# ── 2. Write id.yaml ───────────────────────────────────────────────────────────

locale_path = HERMES_DIR / "locales" / "id.yaml"
locale_path.write_text(ID_YAML, encoding="utf-8")
print(f"✓ Created {locale_path}")

# ── 3. Patch run.py: translate hardcoded "No home channel" message ─────────────

run_py = HERMES_DIR / "gateway" / "run.py"
original = run_py.read_text(encoding="utf-8")

OLD_NOTICE = (
    '                    f"📬 No home channel is set for {platform_name.title()}. "\n'
    '                    f"A home channel is where Hermes delivers cron job results "\n'
    '                    f"and cross-platform messages.\\n\\n"\n'
    '                    f"Type {sethome_cmd} to make this chat your home channel, "\n'
    '                    f"or ignore to skip."'
)

NEW_NOTICE = (
    '                    f"📬 Belum ada home channel untuk {platform_name.title()}. "\n'
    '                    f"Home channel adalah tempat Viko mengirim hasil cron job "\n'
    '                    f"dan pesan lintas-platform.\\n\\n"\n'
    '                    f"Ketik {sethome_cmd} untuk menjadikan chat ini home channel, "\n'
    '                    f"atau abaikan untuk melewati."'
)

if OLD_NOTICE in original:
    patched = original.replace(OLD_NOTICE, NEW_NOTICE)
    run_py.write_text(patched, encoding="utf-8")
    print("✓ Patched run.py: No home channel message → Indonesian")
else:
    print("⚠ run.py: 'No home channel' string not found — may have changed upstream", file=sys.stderr)

# ── 4. Patch run.py: translate /reset confirm prompt ──────────────────────────

OLD_RESET = (
    '            "This starts a fresh session and discards the current "\n'
    '                    "conversation history."'
)
NEW_RESET = (
    '            "Ini akan memulai sesi baru dan menghapus riwayat "\n'
    '                    "percakapan saat ini."'
)

if OLD_RESET in original:
    patched2 = run_py.read_text(encoding="utf-8").replace(OLD_RESET, NEW_RESET)
    run_py.write_text(patched2, encoding="utf-8")
    print("✓ Patched run.py: /reset confirm message → Indonesian")
else:
    print("⚠ run.py: reset confirm string not found", file=sys.stderr)

print("✓ Indonesian locale patch complete")
