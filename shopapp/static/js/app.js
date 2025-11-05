// mobile nav (optional – you can expand later)
document.getElementById('navToggle')?.addEventListener('click', () => {
  document.querySelector('.ev-links')?.classList.toggle('is-open');
});

// count-up for KPIs
const ease = t => 1 - Math.pow(1 - t, 3);
document.querySelectorAll('[data-countup]').forEach(el => {
  const target = parseFloat(el.dataset.countup || '0');
  const isMoney = (el.textContent || '').trim().startsWith('₹') || el.closest('.kpi__value');
  const start = performance.now();
  const dur = 900;
  const anim = (now) => {
    const p = Math.min(1, (now - start)/dur);
    const val = Math.round(ease(p) * target);
    el.textContent = isMoney ? `₹${val.toLocaleString('en-IN')}` : val.toLocaleString('en-IN');
    if (p < 1) requestAnimationFrame(anim);
  };
  requestAnimationFrame(anim);
});
