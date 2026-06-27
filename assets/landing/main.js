/* viko-agent landing page — interactive effects */

/* ── Scroll reveal ── */
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        revealObserver.unobserve(e.target);
      }
    });
  },
  { threshold: 0.1, rootMargin: '0px 0px -48px 0px' }
);
document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

/* ── Hero dot grid ── */
(function buildGrid() {
  const canvas = document.createElement('canvas');
  const container = document.getElementById('heroGrid');
  if (!container) return;
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  let width = 0, height = 0;
  const DOT_SPACING = 32;
  const DOT_R = 1.2;
  const COLOR_VIOLET = [124, 77, 255];
  const COLOR_BLUE   = [79, 195, 247];

  function resize() {
    width = container.offsetWidth;
    height = container.offsetHeight;
    canvas.width  = width;
    canvas.height = height;
    canvas.style.width  = width + 'px';
    canvas.style.height = height + 'px';
    draw();
  }

  function lerp(a, b, t) { return a + (b - a) * t; }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    const cols = Math.ceil(width  / DOT_SPACING);
    const rows = Math.ceil(height / DOT_SPACING);
    for (let r = 0; r <= rows; r++) {
      for (let c = 0; c <= cols; c++) {
        const x = c * DOT_SPACING;
        const y = r * DOT_SPACING;
        const t = c / cols;
        const [R, G, B] = [
          Math.round(lerp(COLOR_VIOLET[0], COLOR_BLUE[0], t)),
          Math.round(lerp(COLOR_VIOLET[1], COLOR_BLUE[1], t)),
          Math.round(lerp(COLOR_VIOLET[2], COLOR_BLUE[2], t)),
        ];
        ctx.beginPath();
        ctx.arc(x, y, DOT_R, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${R},${G},${B},0.25)`;
        ctx.fill();
      }
    }
  }

  window.addEventListener('resize', resize);
  resize();
})();

/* ── Smooth nav link scroll ── */
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', e => {
    const id = link.getAttribute('href').slice(1);
    const target = document.getElementById(id);
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});
