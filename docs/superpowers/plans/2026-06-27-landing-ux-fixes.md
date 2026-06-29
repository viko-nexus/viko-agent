# Landing Page UX Fixes + Animated Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix text contrast and nav usability, then replace the static ASCII architecture diagram with a fully animated HTML/CSS workflow visualization that accurately represents viko-agent's runtime architecture.

**Architecture:** Pure static HTML/CSS/JS — no build step, no framework. Animation uses CSS `@keyframes` only (no JS). Layout uses flexbox with CSS connector elements.

**Tech Stack:** HTML5, CSS3 animations, vanilla JS (ES2020), existing CSS custom properties

## Global Constraints

- No build tools, bundlers, or npm packages
- No inline scripts or event handlers in `index.html`  
- All JS changes go in `assets/landing/main.js`
- All CSS changes go in `assets/landing/style.css`
- Respect existing CSS custom properties: `--bg`, `--surface`, `--card`, `--txt`, `--body`, `--dim`, `--pri` (#5B35D5), `--amb` (#C96E10), `--red`, `--blu` (#1878B4), `--border`
- Courier New preserved for `.af-name`, `.af-rkey`, `.af-peer-label`, all existing monospace elements
- Inter used for `.af-meta`, `.af-rval`, descriptive text
- `data-i18n-html="hero.desc"` (NOT `data-i18n`) because the hero desc will contain `<a>` tags
- Testing: `python3 -m http.server 8080` from repo root; visually verify at `http://localhost:8080`
- Commit branch: create `fix/landing-ux` from `main` before starting Task 1

---

### Task 1: Hero text + font contrast fixes

**Files:**
- Modify: `index.html` — hero desc attribute change + text content
- Modify: `assets/landing/i18n.js` — update `hero.desc` in EN and ID translations
- Modify: `assets/landing/style.css` — nav link color, body contrast, hero desc link styles

**Interfaces:**
- Produces: hero desc with linked tech names; `.nav-link` darker color; `.hero-desc a` link style

- [x] **Step 1: Create branch**

```bash
cd /Users/eksa/Projects/viko-nexus/viko-agent
git checkout main && git pull origin main
git checkout -b fix/landing-ux
```

- [x] **Step 2: Change hero desc to use `data-i18n-html`**

In `index.html`, find:
```html
        <div class="hero-desc" data-i18n="hero.desc">
```
Replace with:
```html
        <div class="hero-desc" data-i18n-html="hero.desc">
```

(The text content of this div will be set by i18n.js via innerHTML, so the static fallback text should also be updated to include the links, for pre-JS rendering.)

Also update the static text content inside the div from:
```
Deploy an AI developer agent for every project — each one fully isolated,
        communicating via WhatsApp, powered by Claude and Groq.
        Self-hosted. Open architecture.
```
To (keep the same indentation/newlines, just change the powered-by part):
```
Deploy an AI developer agent for every project — each one fully isolated,
        communicating via WhatsApp, powered by <a href="https://github.com/NousResearch/hermes-agent" target="_blank" rel="noopener">Hermes-Agent</a> and <a href="https://github.com/viko-nexus/viko-agent#9router" target="_blank" rel="noopener">9Router</a>.
        Self-hosted. Open architecture.
```

- [x] **Step 3: Update i18n.js EN translation for `hero.desc`**

In `assets/landing/i18n.js`, find the EN block and update:
```js
    'hero.desc':    'Deploy an AI developer agent for every project — each one fully isolated, communicating via WhatsApp, powered by <a href="https://github.com/NousResearch/hermes-agent" target="_blank" rel="noopener">Hermes-Agent</a> and <a href="https://github.com/viko-nexus/viko-agent#9router" target="_blank" rel="noopener">9Router</a>. Self-hosted. Open architecture.',
```

- [x] **Step 4: Update i18n.js ID translation for `hero.desc`**

In `assets/landing/i18n.js`, find the ID block and update:
```js
    'hero.desc':    'Deploy AI developer agent untuk setiap proyek — masing-masing terisolasi penuh, berkomunikasi via WhatsApp, didukung <a href="https://github.com/NousResearch/hermes-agent" target="_blank" rel="noopener">Hermes-Agent</a> dan <a href="https://github.com/viko-nexus/viko-agent#9router" target="_blank" rel="noopener">9Router</a>. Self-hosted. Arsitektur terbuka.',
```

- [x] **Step 5: Fix nav link color contrast**

In `assets/landing/style.css`, find the `.nav-link` rule:
```css
.nav-link {
  font-size: 12px; color: var(--dim); letter-spacing: 2px;
  text-decoration: none; text-transform: uppercase; transition: color 0.2s;
}
```
Change `color: var(--dim)` to `color: var(--body)`:
```css
.nav-link {
  font-size: 12px; color: var(--body); letter-spacing: 2px;
  text-decoration: none; text-transform: uppercase; transition: color 0.2s;
}
```

- [x] **Step 6: Add hero desc link styles**

In `assets/landing/style.css`, add after the `.hero-desc` rule:
```css
.hero-desc a {
  color: var(--pri);
  text-decoration: underline;
  text-underline-offset: 3px;
  font-weight: 500;
  transition: color 0.2s;
}
.hero-desc a:hover { color: #7B52E8; }
```

- [x] **Step 7: Verify**

```bash
python3 -c "from html.parser import HTMLParser; p=HTMLParser(); p.feed(open('index.html').read()); print('HTML OK')"
python3 -c "open('assets/landing/i18n.js').read(); print('i18n.js OK')"
grep 'Hermes-Agent' assets/landing/i18n.js | head -3
grep 'color: var(--body)' assets/landing/style.css
```

Expected: all 4 checks produce output.

- [x] **Step 8: Commit**

```bash
git add index.html assets/landing/i18n.js assets/landing/style.css
git commit -m "fix(landing): hero links for Hermes-Agent/9Router; darken nav links to --body"
```

---

### Task 2: Active nav scroll state

**Files:**
- Modify: `assets/landing/main.js` — add IntersectionObserver for section tracking
- Modify: `assets/landing/style.css` — `.nav-link.active` styles

**Interfaces:**
- Consumes: existing nav `<a class="nav-link" href="#features">` etc. targeting section ids `features`, `architecture`, `contribute`, `github`
- Produces: `.nav-link.active` class toggled on scroll; active link has underline accent

- [x] **Step 1: Add active nav CSS**

In `assets/landing/style.css`, add after the `.nav-link:hover` rule:
```css
.nav-link.active {
  color: var(--pri);
  position: relative;
}
.nav-link.active::after {
  content: '';
  position: absolute;
  bottom: -4px; left: 0; right: 0;
  height: 2px;
  background: var(--pri);
  border-radius: 1px;
}
```

- [x] **Step 2: Add scroll-tracking IntersectionObserver to `main.js`**

In `assets/landing/main.js`, append at the end:
```js
/* ── Active nav on scroll ── */
(function trackActiveSection() {
  const navLinks = document.querySelectorAll('.nav-link[href^="#"]');
  if (!navLinks.length) return;

  const sectionIds = Array.from(navLinks).map(a => a.getAttribute('href').slice(1));
  const sections   = sectionIds.map(id => document.getElementById(id)).filter(Boolean);

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        const link = document.querySelector(`.nav-link[href="#${entry.target.id}"]`);
        if (link) link.classList.toggle('active', entry.isIntersecting);
      });
    },
    { rootMargin: '-20% 0px -70% 0px', threshold: 0 }
  );

  sections.forEach(s => observer.observe(s));
})();
```

- [x] **Step 3: Verify**

```bash
python3 -c "open('assets/landing/main.js').read(); print('main.js OK')"
grep -c 'trackActiveSection' assets/landing/main.js
```

Expected: `main.js OK` and count `1`.

- [x] **Step 4: Commit**

```bash
git add assets/landing/main.js assets/landing/style.css
git commit -m "feat(landing): active nav link highlight on scroll (IntersectionObserver)"
```

---

### Task 3: Animated architecture workflow diagram

**Files:**
- Modify: `index.html` — replace `.arch-diagram` contents with `.arch-flow` animated HTML
- Modify: `assets/landing/style.css` — add all `.af-*` styles + `@keyframes`

**Interfaces:**
- Consumes: existing `.architecture` section structure; CSS custom properties from Task 1 context
- Produces: `.arch-flow` div replacing the `<div class="arch-diagram"><pre class="arch-code">...</pre></div>` block; fully CSS-animated flow diagram with 4 layers: WhatsApp → Admin Bridge → [Project Agent | Admin AI] → 9Router

> **Architecture accuracy (from source code analysis):**
> - `bridge/whatsapp-bridge.js`: reads `routing.json` (JID→port map); known JID → stamps `[CTX project=slug]` → routes to project container port; unknown/owner → Admin Hermes queue
> - Project containers: git+deploy key, SSH exec via MCP, own memory DB, token-scoped relay
> - `init-9router.py`: 3 combos — `viko-chat` (Sonnet 4.6 → Opus 4.8 fallback), `viko-code` (Opus 4.8 → Sonnet 4.6 fallback), `viko-combo`
> - `patch-model-router.py`: auto-routes by keyword (debug/fix/code → viko-code, else viko-chat)

- [x] **Step 1: Replace `.arch-diagram` block in `index.html`**

Find this entire block in `index.html`:
```html
    <div class="arch-diagram reveal">
      <pre class="arch-code">WhatsApp message
       │
       ▼
 ┌─────────────────────────────────────────┐
 │  viko-hermes (Admin container)          │
 │                                         │
 │  bridge: routing.json check             │
 │    known JID   → relay to project ─────►│─── viko-{slug}
 │    unknown JID → Admin LLM              │
 └─────────────────────────────────────────┘
                   │
                   │ OpenAI-compat API
                   ▼
          ┌─────────────────┐
          │  viko-9router   │
          │                 │
          │  viko-chat      │ → Claude Haiku
          │  viko-code      │ → Claude Sonnet
          │  (fallback)     │ → Groq Llama
          └─────────────────┘</pre>
    </div>
```

Replace with:
```html
    <div class="arch-diagram reveal">
      <div class="arch-flow">

        <!-- Layer 1: WhatsApp input -->
        <div class="af-node af-wa">
          <span class="af-icon">◉</span>
          <span class="af-name">WHATSAPP</span>
          <span class="af-meta">standalone Baileys bridge · one number</span>
        </div>

        <!-- Vertical connector: WA → Bridge -->
        <div class="af-vline">
          <span class="af-dot" style="animation-delay:0s"></span>
          <span class="af-dot" style="animation-delay:.9s"></span>
          <span class="af-dot" style="animation-delay:1.8s"></span>
        </div>

        <!-- Layer 2: Admin Bridge hub -->
        <div class="af-node af-hub">
          <span class="af-icon">⚡</span>
          <span class="af-name">ADMIN BRIDGE</span>
          <span class="af-meta">routing.json lookup · relay token auth · [CTX] stamping</span>
        </div>

        <!-- Fork connector: Bridge → two branches -->
        <div class="af-fork">
          <div class="af-fork-stem"></div>
          <div class="af-fork-bar">
            <span class="af-dot af-dot-slide-left"  style="animation-delay:0s"></span>
            <span class="af-dot af-dot-slide-right af-dot-amb" style="animation-delay:1.35s"></span>
          </div>
          <div class="af-fork-legs">
            <div class="af-leg af-leg-left"></div>
            <div class="af-leg af-leg-right"></div>
          </div>
        </div>

        <!-- Layer 3: Project Agent | Admin AI -->
        <div class="af-peers">
          <div class="af-peer">
            <div class="af-peer-label">known group JID</div>
            <div class="af-node af-project">
              <span class="af-icon">◈</span>
              <span class="af-name">PROJECT AGENT</span>
              <span class="af-meta">viko-{slug} · fully isolated</span>
              <div class="af-caps">
                <span>git + deploy key</span>
                <span>SSH exec · MCP</span>
                <span>own memory DB</span>
                <span>token-scoped relay</span>
              </div>
            </div>
          </div>
          <div class="af-peer">
            <div class="af-peer-label">owner · DM · unregistered</div>
            <div class="af-node af-admin-node">
              <span class="af-icon">◎</span>
              <span class="af-name">ADMIN AI</span>
              <span class="af-meta">onboarding · management · DMs</span>
            </div>
          </div>
        </div>

        <!-- Merge connector: two branches → 9Router -->
        <div class="af-merge">
          <div class="af-merge-legs">
            <div class="af-leg af-leg-left"></div>
            <div class="af-leg af-leg-right"></div>
          </div>
          <div class="af-merge-bar">
            <span class="af-dot af-dot-slide-center" style="animation-delay:.4s"></span>
          </div>
          <div class="af-merge-stem"></div>
        </div>

        <!-- Layer 4: 9Router -->
        <div class="af-node af-router">
          <span class="af-icon">◆</span>
          <span class="af-name">9ROUTER GATEWAY</span>
          <div class="af-routes">
            <div class="af-route af-route-chat">
              <span class="af-rkey">viko-chat</span>
              <span class="af-rarr">→</span>
              <span class="af-rval">Claude Sonnet 4.6 · Opus 4.8 fallback</span>
            </div>
            <div class="af-route af-route-code">
              <span class="af-rkey">viko-code</span>
              <span class="af-rarr">→</span>
              <span class="af-rval">Claude Opus 4.8 · Sonnet 4.6 fallback</span>
            </div>
          </div>
          <span class="af-meta">keyword auto-routing · /model override supported</span>
        </div>

      </div>
    </div>
```

- [x] **Step 2: Add all `.af-*` CSS and `@keyframes` to `style.css`**

Add before the `/* ════ ARCHITECTURE ════ */` block comment (or immediately after it, before `.architecture {`). Add this entire block:

```css
/* ════ ARCH FLOW DIAGRAM ════ */
.arch-flow {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 16px 40px;
  gap: 0;
}

/* ── Base node ── */
.af-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  text-align: center;
  padding: 18px 28px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(91,53,213,0.06);
  min-width: 220px;
  max-width: 380px;
  width: 100%;
  position: relative;
  transition: box-shadow 0.3s;
}
.af-node:hover {
  box-shadow: 0 4px 20px rgba(91,53,213,0.11);
}
.af-icon {
  font-size: 18px;
  color: var(--pri);
  line-height: 1;
}
.af-name {
  font-family: 'Courier New', Courier, monospace;
  font-size: 11px;
  font-weight: bold;
  letter-spacing: 2px;
  color: var(--txt);
}
.af-meta {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-size: 12px;
  color: var(--dim);
  max-width: 280px;
  line-height: 1.5;
}

/* Hub: Admin Bridge — enlarged, branded */
.af-hub {
  min-width: 300px;
  max-width: 460px;
  border-color: rgba(91,53,213,0.35);
  background: linear-gradient(135deg, rgba(91,53,213,0.04) 0%, rgba(24,120,180,0.03) 100%);
  box-shadow: 0 0 0 3px rgba(91,53,213,0.07), 0 4px 20px rgba(91,53,213,0.10);
}
.af-hub .af-icon { color: var(--pri); font-size: 20px; }

/* WA node */
.af-wa { border-color: rgba(24,120,180,0.3); }
.af-wa .af-icon { color: var(--blu); }

/* Project node */
.af-project { border-color: rgba(24,120,180,0.3); }
.af-project .af-icon { color: var(--blu); }

/* Admin AI node */
.af-admin-node { border-color: rgba(201,110,16,0.3); }
.af-admin-node .af-icon { color: var(--amb); }

/* 9Router node */
.af-router {
  min-width: 300px;
  max-width: 460px;
  border-color: rgba(91,53,213,0.3);
}
.af-router .af-icon { color: var(--pri); }

/* ── Capability tags on project node ── */
.af-caps {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
  margin-top: 6px;
}
.af-caps span {
  font-family: 'Courier New', Courier, monospace;
  font-size: 10px;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 99px;
  color: var(--dim);
  background: rgba(24,120,180,0.04);
}

/* ── 9Router combo rows ── */
.af-routes {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 100%;
  margin-top: 8px;
}
.af-route {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 5px;
  font-size: 12px;
}
.af-route-chat { background: rgba(91,53,213,0.06); }
.af-route-code { background: rgba(201,110,16,0.06); }
.af-rkey {
  font-family: 'Courier New', Courier, monospace;
  font-weight: bold;
  font-size: 11px;
  letter-spacing: 0.5px;
  color: var(--txt);
  min-width: 76px;
}
.af-rarr { color: var(--dim); flex-shrink: 0; }
.af-route-chat .af-rval { color: var(--pri); }
.af-route-code .af-rval { color: var(--amb); }
.af-rval {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-size: 11px;
}

/* ── Vertical connector line ── */
.af-vline {
  width: 2px;
  height: 44px;
  background: linear-gradient(to bottom, rgba(91,53,213,0.3), rgba(24,120,180,0.25));
  position: relative;
  flex-shrink: 0;
}

/* ── Animated dots (vertical) ── */
.af-dot {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--pri);
  left: -3px;
  top: 0;
  box-shadow: 0 0 6px rgba(91,53,213,0.55);
  animation: afDotV 2.7s ease-in-out infinite;
}
.af-dot-amb {
  background: var(--amb);
  box-shadow: 0 0 6px rgba(201,110,16,0.55);
}

@keyframes afDotV {
  0%   { top: 0;    opacity: 0;   transform: scale(0.5); }
  12%  { opacity: 1; transform: scale(1); }
  88%  { opacity: 1; transform: scale(1); }
  100% { top: 100%; opacity: 0;   transform: scale(0.5); }
}

/* Horizontal dot sliding left (toward project arm) */
.af-dot-slide-left {
  left: 50%;
  top: -3px;
  animation: afDotLeft 2.7s ease-in-out infinite;
}
@keyframes afDotLeft {
  0%   { left: 50%; opacity: 0;   transform: scale(0.5); }
  10%  { opacity: 1; transform: scale(1); }
  90%  { opacity: 1; transform: scale(1); }
  100% { left: 0%;  opacity: 0;   transform: scale(0.5); }
}

/* Horizontal dot sliding right (toward admin arm) */
.af-dot-slide-right {
  left: 50%;
  top: -3px;
  animation: afDotRight 2.7s ease-in-out infinite;
}
@keyframes afDotRight {
  0%   { left: 50%; opacity: 0;   transform: scale(0.5); }
  10%  { opacity: 1; transform: scale(1); }
  90%  { opacity: 1; transform: scale(1); }
  100% { left: 100%; opacity: 0;  transform: scale(0.5); }
}

/* Horizontal dot sliding center (merge → 9router) */
.af-dot-slide-center {
  left: 0%;
  top: -3px;
  animation: afDotCenter 2.7s ease-in-out infinite;
}
@keyframes afDotCenter {
  0%   { left: 0%;   opacity: 0;   transform: scale(0.5); }
  5%   { opacity: 1; transform: scale(1); }
  45%  { left: 50%;  opacity: 1; }
  55%  { left: 50%;  opacity: 1; }
  95%  { opacity: 1; transform: scale(1); }
  100% { left: 100%; opacity: 0;   transform: scale(0.5); }
}

/* ── Fork connector (Bridge → Project | Admin) ── */
.af-fork {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 480px;
}
.af-fork-stem {
  width: 2px;
  height: 20px;
  background: linear-gradient(to bottom, rgba(91,53,213,0.3), rgba(91,53,213,0.25));
}
.af-fork-bar {
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, var(--pri), var(--blu));
  position: relative;
  overflow: visible;
}
.af-fork-legs {
  width: 100%;
  display: flex;
  justify-content: space-between;
}

/* ── Merge connector (Project | Admin → 9Router) ── */
.af-merge {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 480px;
}
.af-merge-legs {
  width: 100%;
  display: flex;
  justify-content: space-between;
}
.af-merge-bar {
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, var(--pri), var(--blu));
  position: relative;
  overflow: visible;
}
.af-merge-stem {
  width: 2px;
  height: 20px;
  background: linear-gradient(to bottom, rgba(91,53,213,0.25), rgba(91,53,213,0.3));
}

/* Shared leg (vertical drop/rise on fork and merge) */
.af-leg {
  width: 2px;
  height: 24px;
}
.af-leg-left  { background: var(--pri); }
.af-leg-right { background: var(--blu); }

/* ── Peer row (Project + Admin side by side) ── */
.af-peers {
  display: flex;
  gap: 24px;
  width: 100%;
  max-width: 480px;
  justify-content: center;
}
.af-peer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.af-peer-label {
  font-family: 'Courier New', Courier, monospace;
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.5px;
  padding: 2px 8px;
  background: rgba(91,53,213,0.04);
  border: 1px solid var(--border);
  border-radius: 3px;
  white-space: nowrap;
  text-align: center;
}
.af-peer .af-node {
  width: 100%;
  min-width: 0;
  max-width: none;
}

/* ── Responsive ── */
@media (max-width: 700px) {
  .af-peers     { flex-direction: column; align-items: center; gap: 12px; }
  .af-fork-bar,
  .af-merge-bar { width: 80%; align-self: center; }
  .af-fork-legs,
  .af-merge-legs { width: 80%; }
  .af-hub, .af-router { min-width: 260px; }
  .af-peer      { width: 100%; max-width: 320px; }
  .af-peer-label { white-space: normal; }
}
@media (max-width: 500px) {
  .af-routes { gap: 3px; }
  .af-route  { flex-wrap: wrap; gap: 4px; }
  .af-rval   { font-size: 10px; }
}
```

- [x] **Step 3: Verify HTML and CSS**

```bash
python3 -c "from html.parser import HTMLParser; p=HTMLParser(); p.feed(open('index.html').read()); print('HTML OK')"
python3 -c "open('assets/landing/style.css').read(); print('CSS OK')"
grep -c 'af-node' index.html
grep -c '@keyframes afDot' assets/landing/style.css
```

Expected: HTML OK, CSS OK, `af-node` count ≥ 4, `@keyframes afDot` count ≥ 3.

- [x] **Step 4: Commit**

```bash
git add index.html assets/landing/style.css
git commit -m "feat(landing): animated architecture flow diagram replacing ASCII art"
```

---

## Post-Implementation

After all 3 tasks pass review:

```bash
git push origin fix/landing-ux
gh pr create --title "fix(landing): text contrast, active nav, animated workflow diagram" \
  --body "Fixes text visibility (nav links darker), adds scroll-aware active nav state, and replaces the static ASCII art with a fully animated HTML/CSS architecture flow diagram based on the actual viko-agent runtime (bridge routing, project isolation, 9router combos)." \
  --base main
```
