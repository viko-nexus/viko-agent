/* viko-agent landing page — i18n (EN / ID) */

const TRANSLATIONS = {
  en: {
    'nav.features':    'Features',
    'nav.architecture':'Architecture',
    'nav.github':      'GitHub',
    'nav.contribute':  'Contribute',
    'nav.cta':         'VIEW ON GITHUB →',

    'hero.eyebrow': '▶ Self-Hosted AI Agent Infrastructure',
    'hero.tagline': 'One number. Many projects. Full isolation.',
    'hero.desc':    'Deploy an AI developer agent for every project — each one fully isolated, communicating via WhatsApp, powered by Claude and Groq. Self-hosted. Open architecture.',
    'hero.cta1':    'VIEW ON GITHUB →',
    'hero.cta2':    'EXPLORE FEATURES ↓',

    'story.label': 'Why viko-agent',
    'story.title': 'An AI agent for every project — all from a single <em>WhatsApp number</em>.',
    'story.p1':    'Most AI developer tools are cloud-locked, single-project, or require switching between UIs. viko-agent was built to solve a real problem: coordinating multiple active software projects from one place, with zero vendor lock-in.',
    'story.p2':    'One WhatsApp number. One admin container. Dozens of isolated project agents — each one knowing only its own codebase, deploy VPS, and team members.',
    'story.p3':    'When you onboard a new project, the system generates an SSH keypair, clones the repo, spawns an isolated container, and hands control over to that project\'s agent. Admin never interferes again.',
    'story.stat1.label': 'WhatsApp number for all projects — admin routes everything',
    'story.stat2.label': 'Isolated containers — one per project group, no cross-talk',
    'story.stat3.label': 'Hardcoded values — fully self-hostable, configure via env',

    'features.label': 'Capabilities',
    'features.title': 'What viko-agent does',
    'features.sub':   'Infrastructure, isolation, and LLM routing — production-grade from day one.',
    'feature1.name':  'WHATSAPP NATIVE',
    'feature1.desc':  'Standalone Node.js/Baileys bridge. Admin mode holds the session; project containers relay through it with token-scoped security.',
    'feature2.name':  'FULL ISOLATION',
    'feature2.desc':  'Each project container has its own memory DB, SSH keypair, config, and relay token. A compromised project cannot reach others.',
    'feature3.name':  '9ROUTER GATEWAY',
    'feature3.desc':  'LLM gateway with combo routing. viko-chat → Claude Haiku; viko-code → Claude Sonnet. Auto-selected per message. Groq fallback.',
    'feature4.name':  'AUTO ONBOARDING',
    'feature4.desc':  'Send one command in a new WA group. Admin generates SSH key, clones repo, spawns container, updates routing — hands off in seconds.',
    'feature5.name':  'SECURITY FIRST',
    'feature5.desc':  'OWNER_WA always from env — never hardcoded. Boot-time isolation guard (fail-closed). Relay token scope check in bridge code, not LLM.',
    'feature6.name':  'CI/CD BUILT IN',
    'feature6.desc':  '3-job GitHub Actions workflow: quality check → Docker build → VPS deploy. Registry layer cache for fast incremental image rebuilds.',
    'feature7.name':  'HERMES POWERED',
    'feature7.desc':  'Built on NousResearch Hermes — full agent runtime with tools, memory, hooks, MCP servers, and a WhatsApp-native messaging platform.',
    'feature8.name':  'SELF-HOSTABLE',
    'feature8.desc':  'No cloud account required beyond API keys. Runs on any VPS with Docker. Configure once, deploy anywhere. PolyForm NC license.',

    'arch.label': 'Architecture',
    'arch.title': 'How it works',
    'arch.sub':   'The admin routes, the agents deliver. Each project stays in its own lane.',
    'arch1.title': 'OWNER SENDS COMMAND',
    'arch1.desc':  'In a new WA group: <code>viko onboard project &lt;name&gt; slug &lt;slug&gt; github &lt;url&gt; vps &lt;host&gt; &lt;user&gt;</code>',
    'arch2.title': 'ADMIN ONBOARDS',
    'arch2.desc':  'Generates SSH keypair → verifies VPS access → clones repo → generates config → spawns container',
    'arch3.title': 'ROUTING UPDATED',
    'arch3.desc':  'Group JID registered in routing.json. Admin is now permanently blind to that group. Project agent takes over.',
    'arch4.title': 'FULLY ISOLATED',
    'arch4.desc':  'Project agent has its own memory, SSH key, and config. Relay token ensures it can only message its own group.',

    'contribute.label':       'Open Source',
    'contribute.title':       'Welcome, Contributors',
    'contribute.sub':         'viko-agent is community-built. Whether you\'re fixing a typo or designing a new feature, you\'re welcome here.',
    'contribute.card1.title': 'CODE',
    'contribute.card1.desc':  'Pick an open issue, fork the repo, and send a PR. All skill levels welcome.',
    'contribute.card1.link':  'Browse Issues →',
    'contribute.card2.title': 'DOCUMENTATION',
    'contribute.card2.desc':  'Help improve setup guides, architecture docs, or translate content.',
    'contribute.card2.link':  'View Docs →',
    'contribute.card3.title': 'REPORT ISSUES',
    'contribute.card3.desc':  'Found a bug or security concern? Open an issue or follow the responsible disclosure process.',
    'contribute.card3.link':  'Open Issue →',
    'contribute.cta':         'CONTRIBUTING GUIDE →',

    'cta.label': 'Open Source',
    'cta.title': 'Deploy your own<br><span>AI agent fleet →</span>',
    'cta.sub':   'Full source code, setup guide, architecture docs, and security model. Everything you need to run viko-agent on your own infrastructure.',
    'cta.btn':   'VIEW ON GITHUB →',

    'footer.github':  'GitHub',
    'footer.license': 'License',
    'footer.docs':    'Docs',
  },

  id: {
    'nav.features':    'Fitur',
    'nav.architecture':'Arsitektur',
    'nav.github':      'GitHub',
    'nav.contribute':  'Kontribusi',
    'nav.cta':         'LIHAT DI GITHUB →',

    'hero.eyebrow': '▶ Infrastruktur AI Agent yang Dihosting Sendiri',
    'hero.tagline': 'Satu nomor. Banyak proyek. Isolasi penuh.',
    'hero.desc':    'Deploy AI developer agent untuk setiap proyek — masing-masing terisolasi penuh, berkomunikasi via WhatsApp, didukung Claude dan Groq. Self-hosted. Arsitektur terbuka.',
    'hero.cta1':    'LIHAT DI GITHUB →',
    'hero.cta2':    'JELAJAHI FITUR ↓',

    'story.label': 'Mengapa viko-agent',
    'story.title': 'AI agent untuk setiap proyek — semua dari satu <em>nomor WhatsApp</em>.',
    'story.p1':    'Kebanyakan tools AI developer terikat cloud, hanya satu proyek, atau membutuhkan berpindah-pindah UI. viko-agent dibangun untuk memecahkan masalah nyata: mengkoordinasikan banyak proyek software aktif dari satu tempat, tanpa vendor lock-in.',
    'story.p2':    'Satu nomor WhatsApp. Satu admin container. Puluhan project agent yang terisolasi — masing-masing hanya mengetahui codebase, VPS deploy, dan anggota timnya sendiri.',
    'story.p3':    'Saat kamu onboard proyek baru, sistem otomatis membuat SSH keypair, clone repo, spawn container terisolasi, lalu menyerahkan kendali ke agent proyek tersebut. Admin tidak pernah ikut campur lagi.',
    'story.stat1.label': 'Nomor WhatsApp untuk semua proyek — admin yang mengatur segalanya',
    'story.stat2.label': 'Container terisolasi — satu per grup proyek, tanpa cross-talk',
    'story.stat3.label': 'Nilai hardcoded — sepenuhnya self-hostable, konfigurasi via env',

    'features.label': 'Kemampuan',
    'features.title': 'Apa yang dilakukan viko-agent',
    'features.sub':   'Infrastruktur, isolasi, dan routing LLM — siap produksi sejak hari pertama.',
    'feature1.name':  'NATIVE WHATSAPP',
    'feature1.desc':  'Bridge Node.js/Baileys mandiri. Mode admin menyimpan sesi; container proyek relay melaluinya dengan keamanan berbasis token.',
    'feature2.name':  'ISOLASI PENUH',
    'feature2.desc':  'Setiap container proyek memiliki memory DB, SSH keypair, config, dan relay token sendiri. Proyek yang dikompromikan tidak dapat menjangkau yang lain.',
    'feature3.name':  'GATEWAY 9ROUTER',
    'feature3.desc':  'LLM gateway dengan combo routing. viko-chat → Claude Haiku; viko-code → Claude Sonnet. Dipilih otomatis per pesan. Fallback ke Groq.',
    'feature4.name':  'ONBOARDING OTOMATIS',
    'feature4.desc':  'Kirim satu perintah di grup WA baru. Admin membuat SSH key, clone repo, spawn container, update routing — selesai dalam hitungan detik.',
    'feature5.name':  'KEAMANAN UTAMA',
    'feature5.desc':  'OWNER_WA selalu dari env — tidak pernah hardcoded. Pemeriksaan isolasi saat boot (fail-closed). Cek scope relay token di kode bridge, bukan LLM.',
    'feature6.name':  'CI/CD BAWAAN',
    'feature6.desc':  'Workflow GitHub Actions 3 job: quality check → Docker build → VPS deploy. Registry layer cache untuk rebuild image inkremental yang cepat.',
    'feature7.name':  'BERBASIS HERMES',
    'feature7.desc':  'Dibangun di atas NousResearch Hermes — runtime agent lengkap dengan tools, memori, hooks, MCP server, dan platform pesan berbasis WhatsApp.',
    'feature8.name':  'SELF-HOSTABLE',
    'feature8.desc':  'Tidak memerlukan akun cloud selain API key. Berjalan di VPS manapun dengan Docker. Konfigurasi sekali, deploy di mana saja. Lisensi PolyForm NC.',

    'arch.label': 'Arsitektur',
    'arch.title': 'Cara kerjanya',
    'arch.sub':   'Admin yang mengarahkan, agent yang menyelesaikan. Setiap proyek tetap di jalurnya sendiri.',
    'arch1.title': 'OWNER KIRIM PERINTAH',
    'arch1.desc':  'Di grup WA baru: <code>viko onboard project &lt;name&gt; slug &lt;slug&gt; github &lt;url&gt; vps &lt;host&gt; &lt;user&gt;</code>',
    'arch2.title': 'ADMIN ONBOARDING',
    'arch2.desc':  'Buat SSH keypair → verifikasi akses VPS → clone repo → buat config → spawn container',
    'arch3.title': 'ROUTING DIPERBARUI',
    'arch3.desc':  'Group JID didaftarkan di routing.json. Admin sekarang permanen tidak tahu grup itu. Project agent mengambil alih.',
    'arch4.title': 'TERISOLASI PENUH',
    'arch4.desc':  'Project agent memiliki memori, SSH key, dan config sendiri. Relay token memastikan hanya bisa mengirim pesan ke grupnya sendiri.',

    'contribute.label':       'Open Source',
    'contribute.title':       'Selamat Datang, Kontributor',
    'contribute.sub':         'viko-agent dibangun bersama komunitas. Baik memperbaiki typo atau merancang fitur baru, kamu disambut di sini.',
    'contribute.card1.title': 'KODE',
    'contribute.card1.desc':  'Pilih issue yang tersedia, fork repo, dan kirim PR. Semua level skill diterima.',
    'contribute.card1.link':  'Lihat Issues →',
    'contribute.card2.title': 'DOKUMENTASI',
    'contribute.card2.desc':  'Bantu perbaiki panduan setup, dokumentasi arsitektur, atau terjemahkan konten.',
    'contribute.card2.link':  'Lihat Docs →',
    'contribute.card3.title': 'LAPORKAN MASALAH',
    'contribute.card3.desc':  'Menemukan bug atau masalah keamanan? Buka issue atau ikuti proses responsible disclosure.',
    'contribute.card3.link':  'Buka Issue →',
    'contribute.cta':         'PANDUAN KONTRIBUSI →',

    'cta.label': 'Open Source',
    'cta.title': 'Deploy armada AI agent<br><span>kamu sendiri →</span>',
    'cta.sub':   'Source code lengkap, panduan setup, dokumentasi arsitektur, dan model keamanan. Semua yang kamu butuhkan untuk menjalankan viko-agent di infrastrukturmu sendiri.',
    'cta.btn':   'LIHAT DI GITHUB →',

    'footer.github':  'GitHub',
    'footer.license': 'Lisensi',
    'footer.docs':    'Docs',
  },
};

function applyLang(lang) {
  if (!TRANSLATIONS[lang]) return;
  document.documentElement.lang = lang;

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (TRANSLATIONS[lang][key] !== undefined) {
      el.textContent = TRANSLATIONS[lang][key];
    }
  });

  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const key = el.getAttribute('data-i18n-html');
    if (TRANSLATIONS[lang][key] !== undefined) {
      el.innerHTML = TRANSLATIONS[lang][key];
    }
  });

  document.querySelectorAll('.lang-btn').forEach(btn => {
    const active = btn.getAttribute('data-lang') === lang;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
  });

  try { localStorage.setItem('lang', lang); } catch (_) {}
}

document.querySelectorAll('.lang-btn').forEach(btn => {
  btn.addEventListener('click', () => applyLang(btn.getAttribute('data-lang')));
});

const savedLang = (() => {
  try { return localStorage.getItem('lang') || 'en'; } catch (_) { return 'en'; }
})();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => applyLang(savedLang));
} else {
  applyLang(savedLang);
}
