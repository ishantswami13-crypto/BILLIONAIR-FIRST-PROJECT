// scroll reveal
const onScroll = () => {
  document.querySelectorAll('.reveal').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.top < window.innerHeight - 80) el.classList.add('in');
  });
};
window.addEventListener('scroll', onScroll);
window.addEventListener('load', onScroll);

// modal open/close
document.addEventListener('click', (e) => {
  const openSel = e.target.getAttribute('data-open');
  const closeSel = e.target.getAttribute('data-close');
  if (openSel) document.querySelector(openSel)?.classList.add('show');
  if (closeSel) document.querySelector(closeSel)?.classList.remove('show');
});
// close on backdrop click
document.querySelectorAll('.modal').forEach(m => {
  m.addEventListener('click', (e) => { if (e.target === m) m.classList.remove('show'); });
});

// premium ribbon parallax (very gentle)
(() => {
  const ribbon = document.querySelector('.ribbon--bloom');
  if (!ribbon) return;

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const update = () => {
    const y = window.scrollY || 0;
    // translate a tiny bit + adjust blur subtly to mimic depth
    const offset = Math.min(6, y * 0.03);
    const blur = 0.6 + Math.min(0.8, y * 0.0015);
    ribbon.style.transform = `translateY(${reduce ? 0 : offset}px)`;
    ribbon.style.filter = `saturate(0.92) contrast(0.985) blur(${blur}px)`;
  };

  window.addEventListener('scroll', update, { passive: true });
  window.addEventListener('load', update);
})();
