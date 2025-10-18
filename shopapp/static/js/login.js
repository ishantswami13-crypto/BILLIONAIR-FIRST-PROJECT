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
