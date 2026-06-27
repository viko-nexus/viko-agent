# Landing Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the GitHub Pages landing page (`index.html`) with a bright light theme, hero logo, human-crafted typography, contributor section, and EN/ID i18n — all without a build step (pure HTML/CSS/JS).

**Architecture:** Static GitHub Pages site: single `index.html` + `assets/landing/style.css` + `assets/landing/main.js`. A new `assets/landing/i18n.js` handles translations. No framework, no bundler, no Jekyll. Changes go live on merge to `main` via GitHub Pages automatic deploy. Logo assets live in `docs/assets/`.

**Tech Stack:** HTML5, CSS custom properties, vanilla JS (ES2020), Google Fonts (Inter), GitHub Pages

## Global Constraints

- No build tools, bundlers, or npm packages — pure static files
- No `--depth=1` or fetch over network in CI (GitHub Pages serves directly from repo)
- All JS in `assets/landing/*.js` — no inline scripts in `index.html`
- Google Fonts loaded via `<link>` in `<head>` (not @import in CSS — avoids FOUC)
- Logo source: `docs/assets/logo.png` (for small uses) or `docs/assets/logo-1024.png` (for hero display, 1024×796 PNG)
- Language switcher: two-button toggle (EN | ID) in header nav — not a `<select>` dropdown (too cramped in nav for 2 languages)
- Store language preference in `localStorage` key `'lang'`; default to `'en'`
- Testing: `python3 -m http.server 8080` from repo root, open `http://localhost:8080`
- Commit branch: create `feat/landing-redesign` from `main` before starting Task 1

---

### Task 1: Light theme — replace dark navy with bright color system

**Files:**
- Modify: `assets/landing/style.css`

**Interfaces:**
- Produces: CSS custom properties (`--bg`, `--surface`, `--card`, `--txt`, `--body`, `--dim`, `--pri`, `--amb`, `--red`, `--blu`, `--border`) used by all subsequent tasks

> NOTE: Rename `--black` → `--bg` and `--card` → keep `--card` but update its value. Add `--surface` for pure-white elevated elements.

- [ ] **Step 1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/landing-redesign
```

- [ ] **Step 2: Replace `:root` custom properties**

In `assets/landing/style.css`, replace the entire `:root { ... }` block (lines 4–15) with:

```css
:root {
  --bg:      #F7F9FF;   /* page background — soft blue-tinted white */
  --surface: #FFFFFF;   /* pure white for elevated surfaces */
  --card:    #FFFFFF;   /* card background */
  --txt:     #0D1729;   /* near-black headings */
  --body:    #3B4C72;   /* mid-navy body text */
  --dim:     #7A8AAD;   /* muted/secondary text */
  --pri:     #5B35D5;   /* electric violet — contrast-safe on white */
  --amb:     #C96E10;   /* amber — darkened for white bg */
  --red:     #C41E50;   /* crimson — darkened for white bg */
  --blu:     #1878B4;   /* blue — darkened for white bg */
  --border:  #E0E8F5;   /* light blue-tinted border */
}
```

- [ ] **Step 3: Update body background and dot grid**

Replace the body rule (currently starting at line ~21):

```css
body {
  background-color: var(--bg);
  background-image: radial-gradient(circle, rgba(91,53,213,0.06) 1px, transparent 1px);
  background-size: 40px 40px;
  color: var(--txt);
  font-family: 'Courier New', Courier, monospace;
  font-size: 17px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
  position: relative;
}
```

- [ ] **Step 4: Update ambient glows for light bg**

Replace the `body::before` block:

```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 70% 55% at 0% 0%,   rgba(91,53,213,0.05) 0%, transparent 65%),
    radial-gradient(ellipse 55% 45% at 100% 100%, rgba(24,120,180,0.04) 0%, transparent 65%);
  pointer-events: none;
  z-index: 0;
}
```

- [ ] **Step 5: Fix hardcoded dark colors**

Find and replace these 5 hardcoded values in `style.css`:

| Find | Replace with |
|------|-------------|
| `background: rgba(10,22,40,0.88)` (header) | `background: rgba(247,249,255,0.92)` |
| `background: linear-gradient(to bottom, #0A1628, transparent)` (hero-fade-top) | `background: linear-gradient(to bottom, var(--bg), transparent)` |
| `background: linear-gradient(to bottom, transparent, #0A1628)` (hero-fade-bottom) | `background: linear-gradient(to bottom, transparent, var(--bg))` |
| `background: #162444` (feature-card:hover) | `background: #EEF1FF` |

Leave `.arch-code { background: rgba(13,30,56,0.85) }` unchanged — code blocks stay dark (intentional contrast island).

- [ ] **Step 6: Update hero grid opacity in CSS**

In `.hero-grid`, change `opacity: 0.2` to `opacity: 0.12`.

- [ ] **Step 7: Update feature grid background**

Replace:
```css
.features-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 1px; background: var(--border);
  border: 1px solid var(--border);
}
```
With:
```css
.features-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
```

And update `.feature-card`:
```css
.feature-card {
  background: var(--card); padding: 28px 24px;
  display: flex; flex-direction: column; gap: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(91,53,213,0.05);
  transition: box-shadow 0.2s, transform 0.2s;
}
.feature-card:hover {
  box-shadow: 0 4px 24px rgba(91,53,213,0.12);
  transform: translateY(-2px);
}
```

- [ ] **Step 8: Update nav dim text color for light header**

In `.nav-link`, `.nav-name`, `.nav-cta`, `.nav-sub` — the CSS variable references will auto-update. But verify that `.nav-link:hover { color: var(--pri); }` still works (it will).

Also add a subtle bottom border on header: add `border-bottom: 1px solid var(--border);` to the `header` rule if not already present.

- [ ] **Step 9: Update stat-block and arch-card for light bg**

```css
.stat-block {
  padding: 28px 32px; background: var(--surface);
  border: 1px solid var(--border); border-left: 3px solid var(--pri);
  border-radius: 4px;
}
.arch-card {
  padding: 24px 20px; background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex; flex-direction: column; gap: 10px;
}
```

- [ ] **Step 10: Reduce hero canvas dot opacity**

In `assets/landing/main.js`, find `ctx.fillStyle = \`rgba(${R},${G},${B},0.6)\`` and change to `rgba(${R},${G},${B},0.25)`.

- [ ] **Step 11: Visual check**

```bash
cd /Users/eksa/Projects/viko-nexus/viko-agent
python3 -m http.server 8080
```
Open `http://localhost:8080` and verify:
- Background is soft blue-white (not dark navy)
- All text is readable dark-on-light
- Header is semi-transparent light with subtle border
- Feature cards have rounded corners and box shadow
- ASCII art code block is still dark
- Hero dot grid is visible but subtle

- [ ] **Step 12: Commit**

```bash
git add assets/landing/style.css assets/landing/main.js
git commit -m "feat(landing): switch to light theme with bright blue-white color system"
```

---

### Task 2: Hero section — add logo and two-column layout

**Files:**
- Modify: `index.html`
- Modify: `assets/landing/style.css`

**Interfaces:**
- Consumes: `--bg`, `--pri`, `--txt` from Task 1
- Produces: `.hero-logo` image class; hero section becomes 2-column (text left, logo right)

- [ ] **Step 1: Add logo to hero section**

In `index.html`, inside `<section class="hero">`, change the hero structure to add a logo column. Replace:

```html
  <section class="hero">
    <div class="hero-fade-top"></div>
    <div class="hero-fade-bottom"></div>
    <div class="hero-grid" id="heroGrid"></div>
    <div class="hero-content">
      <div class="hero-eyebrow">▶ Self-Hosted AI Agent Infrastructure</div>
      <div class="hero-title">VIKO<br><span>AGENT</span></div>
      <div class="hero-tagline">One number. Many projects. Full isolation.</div>
      <div class="hero-desc">
        Deploy an AI developer agent for every project — each one fully isolated,
        communicating via WhatsApp, powered by Claude and Groq.
        Self-hosted. Open architecture.
      </div>
      <div class="hero-cta">
        <a class="btn-primary" href="https://github.com/viko-nexus/viko-agent">VIEW ON GITHUB →</a>
        <a class="btn-outline" href="#features">EXPLORE FEATURES ↓</a>
      </div>
    </div>
  </section>
```

With:

```html
  <section class="hero">
    <div class="hero-fade-top"></div>
    <div class="hero-fade-bottom"></div>
    <div class="hero-grid" id="heroGrid"></div>
    <div class="hero-inner">
      <div class="hero-content">
        <div class="hero-eyebrow">▶ Self-Hosted AI Agent Infrastructure</div>
        <div class="hero-title">VIKO<br><span>AGENT</span></div>
        <div class="hero-tagline">One number. Many projects. Full isolation.</div>
        <div class="hero-desc">
          Deploy an AI developer agent for every project — each one fully isolated,
          communicating via WhatsApp, powered by Claude and Groq.
          Self-hosted. Open architecture.
        </div>
        <div class="hero-cta">
          <a class="btn-primary" href="https://github.com/viko-nexus/viko-agent">VIEW ON GITHUB →</a>
          <a class="btn-outline" href="#features">EXPLORE FEATURES ↓</a>
        </div>
      </div>
      <div class="hero-visual">
        <img class="hero-logo-img" src="docs/assets/logo-1024.png" alt="viko-agent logo">
      </div>
    </div>
  </section>
```

- [ ] **Step 2: Add hero-inner and hero-visual CSS**

Add to `assets/landing/style.css`, inside the `/* ════ HERO ════ */` section, after `.hero-content`:

```css
.hero-inner {
  position: relative; z-index: 5;
  width: 100%;
  padding: 0 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 48px;
}

.hero-content {
  position: relative; z-index: 5;
  max-width: 560px;
  display: flex; flex-direction: column; gap: 16px;
  /* remove old padding: 0 64px — now handled by hero-inner */
  padding: 0;
}

.hero-visual {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-logo-img {
  width: 320px;
  height: auto;
  opacity: 0.9;
  filter: drop-shadow(0 8px 32px rgba(91,53,213,0.18));
  animation: heroLogoFloat 6s ease-in-out infinite;
}

@keyframes heroLogoFloat {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-10px); }
}
```

Also remove `padding: 0 64px; max-width: 640px;` from the old `.hero-content` rule (now `hero-inner` handles padding).

- [ ] **Step 3: Update responsive breakpoints for hero**

In the `@media (max-width: 900px)` block, add:

```css
  .hero-inner { padding: 0 40px; gap: 32px; }
  .hero-logo-img { width: 220px; }
```

In the `@media (max-width: 600px)` block, add:

```css
  .hero-inner { padding: 0 24px; flex-direction: column-reverse; gap: 24px; }
  .hero-logo-img { width: 160px; }
```

Also in `@media (max-width: 600px)`, remove `.hero-content { padding: 0 24px; }` if it still refers to the old rule (the `hero-inner` handles padding now).

- [ ] **Step 4: Visual check**

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080` and verify:
- Desktop: hero text on left, logo on right, same vertical center
- Logo has a subtle floating animation
- Logo visible and not clipped
- Mobile (resize to 480px): logo appears above text, full width

- [ ] **Step 5: Commit**

```bash
git add index.html assets/landing/style.css
git commit -m "feat(landing): add hero logo with float animation and two-column layout"
```

---

### Task 3: Typography and design polish

**Files:**
- Modify: `index.html` (add Google Fonts `<link>`)
- Modify: `assets/landing/style.css`

**Interfaces:**
- Consumes: `--txt`, `--body`, `--dim`, `--border` from Task 1
- Produces: Inter font loaded; body uses sans-serif; Courier New kept only for brand/code elements; improved button and card design

- [ ] **Step 1: Add Google Fonts to `<head>`**

In `index.html`, inside `<head>`, after the `<meta name="description">` line but before `<title>`, add:

```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;1,14..32,400&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Switch body font to Inter**

In `assets/landing/style.css`, in the `body` rule, change:

```css
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
```

(was `'Courier New', Courier, monospace`)

- [ ] **Step 3: Keep Courier New for brand and code elements**

Add a block immediately after the body rule to re-apply monospace where it belongs:

```css
/* Monospace reserved for brand identity, code, and UI labels */
.hero-title,
.hero-eyebrow,
.label,
.nav-name, .nav-sub, .nav-link, .nav-cta,
.btn-primary, .btn-outline,
.feature-name,
.arch-card-icon, .arch-card-title,
.arch-code,
.tech-pill,
.footer-name, .footer-sub,
code {
  font-family: 'Courier New', Courier, monospace;
}
```

- [ ] **Step 4: Improve body text readability**

Update typography sizes in `assets/landing/style.css`:

```css
.story-body    { font-size: 17px; color: var(--body); line-height: 2.0; }
.section-sub   { font-size: 17px; color: var(--body); max-width: 580px; line-height: 1.9; }
.hero-desc     { font-size: 17px; color: var(--body); line-height: 1.9; max-width: 440px; }
.hero-tagline  { font-size: 21px; color: var(--txt); line-height: 1.5; font-weight: 600; }
.feature-desc  { font-size: 14px; color: var(--body); line-height: 1.8; flex: 1; font-family: 'Inter', system-ui, sans-serif; }
.arch-card-desc { font-size: 14px; color: var(--body); line-height: 1.8; font-family: 'Inter', system-ui, sans-serif; }
```

- [ ] **Step 5: Improve button design**

Replace the button rules:

```css
.btn-primary {
  padding: 13px 30px;
  background: var(--pri); color: #fff;
  font-family: 'Courier New', monospace;
  font-size: 12px; font-weight: bold; letter-spacing: 2px;
  border: none; border-radius: 6px; cursor: pointer;
  text-decoration: none; display: inline-block;
  box-shadow: 0 2px 8px rgba(91,53,213,0.25);
  transition: background 0.2s, box-shadow 0.2s, transform 0.15s;
}
.btn-primary:hover {
  background: #7B52E8;
  box-shadow: 0 4px 16px rgba(91,53,213,0.35);
  transform: translateY(-1px);
}
.btn-outline {
  padding: 13px 30px;
  background: transparent; color: var(--pri);
  font-family: 'Courier New', monospace;
  font-size: 12px; letter-spacing: 2px;
  border: 1.5px solid rgba(91,53,213,0.35); border-radius: 6px;
  cursor: pointer; text-decoration: none; display: inline-block;
  transition: border-color 0.2s, background 0.2s, transform 0.15s;
}
.btn-outline:hover {
  border-color: var(--pri);
  background: rgba(91,53,213,0.06);
  transform: translateY(-1px);
}
```

- [ ] **Step 6: Improve section header typography**

```css
.section-title {
  font-size: 34px; font-weight: 700; color: var(--txt);
  letter-spacing: -0.5px; line-height: 1.2; margin-bottom: 12px;
  font-family: 'Inter', system-ui, sans-serif;
}
.story-title {
  font-size: 38px; font-weight: 700; color: var(--txt);
  letter-spacing: -0.5px; line-height: 1.3; margin-bottom: 24px;
  font-family: 'Inter', system-ui, sans-serif;
}
.github-cta-title {
  font-size: 38px; font-weight: 700; color: var(--txt);
  letter-spacing: -0.5px; line-height: 1.3;
  font-family: 'Inter', system-ui, sans-serif;
}
```

- [ ] **Step 7: Update `.github-cta-sub` and tech pills**

```css
.github-cta-sub { font-size: 17px; color: var(--body); max-width: 500px; line-height: 1.9; font-family: 'Inter', system-ui, sans-serif; }
.tech-pill {
  padding: 6px 16px; background: var(--surface); border: 1px solid var(--border);
  font-size: 12px; color: var(--dim); letter-spacing: 1px; border-radius: 999px;
}
.tech-pill.violet { border-color: rgba(91,53,213,0.3); color: var(--pri); background: rgba(91,53,213,0.05); }
.tech-pill.amber  { border-color: rgba(201,110,16,0.3); color: var(--amb); background: rgba(201,110,16,0.05); }
```

- [ ] **Step 8: Visual check**

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080` and verify:
- Body text uses Inter (clean, human-readable)
- Nav brand, hero title, labels, buttons still use Courier New (monospace)
- Tech pills are pill-shaped (border-radius 999px)
- Buttons have subtle shadow + lift on hover
- Section titles are heavier and have tight letter-spacing (-0.5px)
- Text is comfortable to read (no harsh contrast, good line-height)

- [ ] **Step 9: Commit**

```bash
git add index.html assets/landing/style.css
git commit -m "feat(landing): add Inter font, preserve Courier New for brand elements, polish buttons and cards"
```

---

### Task 4: Contributor section and README update

**Files:**
- Modify: `index.html`
- Modify: `assets/landing/style.css`
- Modify: `README.md`

**Interfaces:**
- Consumes: `--bg`, `--surface`, `--card`, `--txt`, `--body`, `--pri`, `--border`, Inter font — all from Tasks 1 and 3
- Produces: `<section class="contribute" id="contribute">` in `index.html`; "Contribute" nav link in header

- [ ] **Step 1: Add Contribute nav link**

In `index.html`, inside `<nav class="nav-links">`, add before the `<a class="nav-cta"...>` line:

```html
      <a class="nav-link" href="#contribute">Contribute</a>
```

- [ ] **Step 2: Add contributor section HTML**

In `index.html`, replace:

```html
  <section class="github-cta" id="github">
```

With (insert the new contribute section BEFORE the github-cta section):

```html
  <section class="contribute" id="contribute">
    <div class="contribute-inner reveal">
      <div class="label">Open Source</div>
      <div class="sep"></div>
      <div class="section-title">Welcome, Contributors</div>
      <div class="contribute-sub">viko-agent is community-built. Whether you're fixing a typo or designing a new feature, you're welcome here.</div>
      <div class="contribute-cards">
        <div class="contribute-card">
          <div class="contribute-card-icon">⌥</div>
          <div class="contribute-card-title">CODE</div>
          <div class="contribute-card-desc">Pick an open issue, fork the repo, and send a PR. All skill levels welcome.</div>
          <a href="https://github.com/viko-nexus/viko-agent/issues" class="contribute-link">Browse Issues →</a>
        </div>
        <div class="contribute-card">
          <div class="contribute-card-icon">◧</div>
          <div class="contribute-card-title">DOCUMENTATION</div>
          <div class="contribute-card-desc">Help improve setup guides, architecture docs, or translate content.</div>
          <a href="https://github.com/viko-nexus/viko-agent/tree/main/docs" class="contribute-link">View Docs →</a>
        </div>
        <div class="contribute-card">
          <div class="contribute-card-icon">◌</div>
          <div class="contribute-card-title">REPORT ISSUES</div>
          <div class="contribute-card-desc">Found a bug or security concern? Open an issue or follow the responsible disclosure process.</div>
          <a href="https://github.com/viko-nexus/viko-agent/issues/new" class="contribute-link">Open Issue →</a>
        </div>
      </div>
      <a class="btn-primary" href="https://github.com/viko-nexus/viko-agent/blob/main/docs/overview/CONTRIBUTING.md" style="margin-top:8px">
        CONTRIBUTING GUIDE →
      </a>
    </div>
  </section>

  <section class="github-cta" id="github">
```

- [ ] **Step 3: Add contributor section CSS**

Add to `assets/landing/style.css` before the `/* ════ GITHUB CTA ════ */` block:

```css
/* ════ CONTRIBUTE ════ */
.contribute {
  padding: 96px 64px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.contribute-inner {
  max-width: 860px;
  margin: 0 auto;
  display: flex; flex-direction: column; align-items: center;
  text-align: center; gap: 0;
}
.contribute-inner .sep { margin: 0 auto 20px; }
.contribute-sub {
  font-size: 17px; color: var(--body); max-width: 540px;
  line-height: 1.9; margin-bottom: 40px;
  font-family: 'Inter', system-ui, sans-serif;
}
.contribute-cards {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 20px; width: 100%; margin-bottom: 32px;
}
.contribute-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 28px 24px;
  display: flex; flex-direction: column; gap: 10px;
  text-align: left;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: box-shadow 0.2s, transform 0.2s;
}
.contribute-card:hover {
  box-shadow: 0 4px 20px rgba(91,53,213,0.10);
  transform: translateY(-2px);
}
.contribute-card-icon {
  font-size: 22px; color: var(--pri); line-height: 1;
}
.contribute-card-title {
  font-size: 13px; font-weight: bold; color: var(--txt);
  letter-spacing: 1.5px; font-family: 'Courier New', monospace;
}
.contribute-card-desc {
  font-size: 14px; color: var(--body); line-height: 1.8; flex: 1;
  font-family: 'Inter', system-ui, sans-serif;
}
.contribute-link {
  font-size: 12px; color: var(--pri); letter-spacing: 1px;
  text-decoration: none; font-family: 'Courier New', monospace;
  font-weight: bold;
  transition: color 0.2s;
}
.contribute-link:hover { color: #7B52E8; }

@media (max-width: 900px) {
  .contribute { padding: 64px 40px; }
  .contribute-cards { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 600px) {
  .contribute { padding: 56px 24px; }
  .contribute-cards { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: Update README.md**

In `README.md`, find the line that starts the `## Docs` section. Insert BEFORE it:

```markdown
---

## Contributing

Contributions are welcome — viko-agent is built in the open.

- **Code:** Pick an [open issue](https://github.com/viko-nexus/viko-agent/issues), fork the repo, and send a PR
- **Docs:** Help improve setup guides, architecture docs, or translate content  
- **Bugs:** [Open an issue](https://github.com/viko-nexus/viko-agent/issues/new) with reproduction steps

See [CONTRIBUTING.md](docs/overview/CONTRIBUTING.md) for full guidelines.

```

- [ ] **Step 5: Visual check**

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080` and verify:
- "Contribute" appears in the nav and scrolls to the section
- 3 cards visible (Code, Documentation, Report Issues)
- Cards lift on hover
- "CONTRIBUTING GUIDE →" button opens the correct GitHub URL (check in browser)
- Section has white background (distinct from `--bg` dot-grid body)

- [ ] **Step 6: Commit**

```bash
git add index.html assets/landing/style.css README.md
git commit -m "feat(landing): add contributor section with 3 cards; add Contributing to README"
```

---

### Task 5: i18n — EN/ID language switcher

**Files:**
- Create: `assets/landing/i18n.js`
- Modify: `index.html` (add `data-i18n` attributes to all translatable text; add language switcher to nav)
- Modify: `assets/landing/style.css` (language switcher styles)
- Modify: `assets/landing/main.js` (load i18n.js after DOM ready)

**Interfaces:**
- Consumes: existing DOM structure from Tasks 1–4
- Produces: `window.applyLang(lang: 'en'|'id')` function; `.lang-switcher` in nav header; `data-i18n` / `data-i18n-html` attributes on all user-visible text nodes

> **Key design:** `data-i18n="key"` sets `el.textContent`. `data-i18n-html="key"` sets `el.innerHTML` (use only for elements that contain HTML like `<em>` or `<code>`). Language is saved in `localStorage('lang')` and applied on `DOMContentLoaded`.

- [ ] **Step 1: Add `<script>` for i18n in `index.html`**

In `index.html`, find the line `<script src="assets/landing/main.js"></script>` and replace with:

```html
  <script src="assets/landing/i18n.js"></script>
  <script src="assets/landing/main.js"></script>
```

- [ ] **Step 2: Add language switcher to nav in `index.html`**

In `index.html`, inside `<header>`, add the language switcher inside `<nav class="nav-links">`, BEFORE the `<a class="nav-cta"...>` button:

```html
      <div class="lang-switcher" role="group" aria-label="Language">
        <button class="lang-btn" data-lang="en" aria-pressed="true">EN</button>
        <span class="lang-sep" aria-hidden="true">|</span>
        <button class="lang-btn" data-lang="id" aria-pressed="false">ID</button>
      </div>
```

- [ ] **Step 3: Add `data-i18n` attributes to all translatable elements in `index.html`**

Apply attributes throughout the file. Show each element change:

**Header nav links:**
```html
<a class="nav-link" href="#features" data-i18n="nav.features">Features</a>
<a class="nav-link" href="#architecture" data-i18n="nav.architecture">Architecture</a>
<a class="nav-link" href="#github" data-i18n="nav.github">GitHub</a>
<a class="nav-link" href="#contribute" data-i18n="nav.contribute">Contribute</a>
<a class="nav-cta" href="https://github.com/viko-nexus/viko-agent" data-i18n="nav.cta">VIEW ON GITHUB →</a>
```

**Hero section:**
```html
<div class="hero-eyebrow" data-i18n="hero.eyebrow">▶ Self-Hosted AI Agent Infrastructure</div>
<!-- hero-title: VIKO/AGENT stays untranslated — it's the product name -->
<div class="hero-tagline" data-i18n="hero.tagline">One number. Many projects. Full isolation.</div>
<div class="hero-desc" data-i18n="hero.desc">Deploy an AI developer agent...</div>
<a class="btn-primary" href="..." data-i18n="hero.cta1">VIEW ON GITHUB →</a>
<a class="btn-outline" href="#features" data-i18n="hero.cta2">EXPLORE FEATURES ↓</a>
```

**Story section:**
```html
<div class="label" data-i18n="story.label">Why viko-agent</div>
<div class="story-title" data-i18n-html="story.title">An AI agent for every project — all from a single <em>WhatsApp number</em>.</div>
<p data-i18n="story.p1">Most AI developer tools are cloud-locked...</p>
<p data-i18n="story.p2">One WhatsApp number. One admin container...</p>
<p data-i18n="story.p3">When you onboard a new project...</p>
<div class="stat-label" data-i18n="story.stat1.label">WhatsApp number for all projects...</div>
<div class="stat-label" data-i18n="story.stat2.label">Isolated containers...</div>
<div class="stat-label" data-i18n="story.stat3.label">Hardcoded values...</div>
```

**Features section:**
```html
<div class="label" data-i18n="features.label">Capabilities</div>
<div class="section-title" data-i18n="features.title">What viko-agent does</div>
<div class="section-sub" data-i18n="features.sub">Infrastructure, isolation...</div>
<!-- Each feature card name and desc gets data-i18n -->
<div class="feature-name" data-i18n="feature1.name">WHATSAPP NATIVE</div>
<div class="feature-desc" data-i18n="feature1.desc">Standalone Node.js/Baileys...</div>
<!-- repeat for feature2 through feature8 -->
```

**Architecture section:**
```html
<div class="label" data-i18n="arch.label">Architecture</div>
<div class="section-title" data-i18n="arch.title">How it works</div>
<div class="section-sub" data-i18n="arch.sub">The admin routes...</div>
<div class="arch-card-title" data-i18n="arch1.title">OWNER SENDS COMMAND</div>
<div class="arch-card-desc" data-i18n-html="arch1.desc">In a new WA group: <code>...</code></div>
<div class="arch-card-title" data-i18n="arch2.title">ADMIN ONBOARDS</div>
<div class="arch-card-desc" data-i18n="arch2.desc">Generates SSH keypair → ...</div>
<div class="arch-card-title" data-i18n="arch3.title">ROUTING UPDATED</div>
<div class="arch-card-desc" data-i18n="arch3.desc">Group JID registered...</div>
<div class="arch-card-title" data-i18n="arch4.title">FULLY ISOLATED</div>
<div class="arch-card-desc" data-i18n="arch4.desc">Project agent has its own...</div>
```

**Contribute section:**
```html
<div class="label" data-i18n="contribute.label">Open Source</div>
<div class="section-title" data-i18n="contribute.title">Welcome, Contributors</div>
<div class="contribute-sub" data-i18n="contribute.sub">viko-agent is community-built...</div>
<div class="contribute-card-title" data-i18n="contribute.card1.title">CODE</div>
<div class="contribute-card-desc" data-i18n="contribute.card1.desc">Pick an open issue...</div>
<a ... data-i18n="contribute.card1.link">Browse Issues →</a>
<div class="contribute-card-title" data-i18n="contribute.card2.title">DOCUMENTATION</div>
<div class="contribute-card-desc" data-i18n="contribute.card2.desc">Help improve setup guides...</div>
<a ... data-i18n="contribute.card2.link">View Docs →</a>
<div class="contribute-card-title" data-i18n="contribute.card3.title">REPORT ISSUES</div>
<div class="contribute-card-desc" data-i18n="contribute.card3.desc">Found a bug or security concern...</div>
<a ... data-i18n="contribute.card3.link">Open Issue →</a>
<a class="btn-primary" ... data-i18n="contribute.cta">CONTRIBUTING GUIDE →</a>
```

**GitHub CTA section:**
```html
<div class="label" data-i18n="cta.label">Open Source</div>
<div class="github-cta-title" data-i18n-html="cta.title">Deploy your own<br><span>AI agent fleet →</span></div>
<div class="github-cta-sub" data-i18n="cta.sub">Full source code...</div>
<a class="btn-primary" ... data-i18n="cta.btn">VIEW ON GITHUB →</a>
```

**Footer:**
```html
<a class="footer-link" href="..." data-i18n="footer.github">GitHub</a>
<a class="footer-link" href="..." data-i18n="footer.license">License</a>
<a class="footer-link" href="..." data-i18n="footer.docs">Docs</a>
```

- [ ] **Step 4: Create `assets/landing/i18n.js`**

Create the file with the full translation dictionary and `applyLang`:

```js
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
```

- [ ] **Step 5: Add language switcher CSS to `assets/landing/style.css`**

Add inside the `/* ════ HEADER ════ */` block:

```css
.lang-switcher {
  display: flex; align-items: center; gap: 4px;
}
.lang-btn {
  background: none; border: none; cursor: pointer;
  font-family: 'Courier New', monospace;
  font-size: 11px; font-weight: bold; letter-spacing: 1.5px;
  color: var(--dim); padding: 4px 6px; border-radius: 3px;
  transition: color 0.2s, background 0.15s;
}
.lang-btn:hover  { color: var(--pri); background: rgba(91,53,213,0.07); }
.lang-btn.active { color: var(--pri); }
.lang-sep { font-size: 11px; color: var(--dim); user-select: none; }
```

Also add in `@media (max-width: 600px)`:
```css
  .lang-switcher { display: none; }
```
(On mobile the nav is already cramped; users can reload in their browser-preferred language.)

- [ ] **Step 6: Visual + functional check**

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080` and verify:
- EN | ID buttons visible in header (between "Contribute" nav link and "VIEW ON GITHUB" button)
- Clicking ID: all text switches to Indonesian; active button becomes `var(--pri)` color
- Clicking EN: switches back to English
- Reload page → language preference restored from `localStorage`
- Feature names, hero description, architecture cards all update
- `document.documentElement.lang` shows `id` when ID is active (check via DevTools)
- ASCII art diagram and logo are NOT translated (correct)

- [ ] **Step 7: Commit**

```bash
git add index.html assets/landing/i18n.js assets/landing/style.css assets/landing/main.js
git commit -m "feat(landing): add EN/ID i18n with two-button language switcher; all text translated"
```

---

## Post-Implementation

After all 5 tasks complete:

```bash
# Push and open PR
git push origin feat/landing-redesign
gh pr create --title "feat(landing): light theme, hero logo, Inter font, contributor section, EN/ID i18n" \
  --body "Complete redesign of the GitHub Pages landing page. See plan in docs/superpowers/plans/2026-06-27-landing-page-redesign.md" \
  --base main
```

GitHub Pages auto-deploys from `main` after merge — live at `https://viko-nexus.github.io/viko-agent/` within ~60 seconds.
