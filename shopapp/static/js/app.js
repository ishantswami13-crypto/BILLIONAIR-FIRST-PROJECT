// theme toggle (remembers choice)
(() => {
  const btn = document.getElementById('themeToggle');
  if(!btn) return;
  const saved = localStorage.getItem('evara-theme');
  if(saved){ document.body.classList.toggle('is-dark', saved==='dark'); }
  btn.addEventListener('click', () => {
    const isDark = document.body.classList.toggle('is-dark');
    localStorage.setItem('evara-theme', isDark ? 'dark' : 'light');
  });
})();
