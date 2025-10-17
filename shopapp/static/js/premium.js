<script>
window.PremiumUX = (function(){
  const $ = (sel, root=document) => root.querySelector(sel);
  const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

  // time-based greet + sentiment
  function greet(){
    const h = new Date().getHours();
    if(h < 12) return "Good morning";
    if(h < 17) return "Good afternoon";
    return "Good evening";
  }

  // dynamic AI-ish tips (rotate)
  function rotateTips(el, tips, ms=4800){
    if(!el || !tips || !tips.length) return;
    let i=0;
    setInterval(()=>{
      i=(i+1)%tips.length;
      el.style.opacity=.2;
      setTimeout(()=>{ el.textContent=tips[i]; el.style.opacity=1; }, 220);
    }, ms);
  }

  // parallax (mouse) for hero strip
  function parallax(el){
    if(!el) return;
    const onMove = e=>{
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width/2, cy = r.top + r.height/2;
      const dx = (e.clientX - cx)/r.width, dy = (e.clientY - cy)/r.height;
      el.style.transform = `translateY(${dy*4}px) translateX(${dx*4}px)`;
    };
    const onLeave = ()=>{ el.style.transform = `translate(0,0)`; };
    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
  }

  // count-up numbers
  function countUp(el,{money=false,dur=900}={}){
    const t = Number(el.dataset.count||0); let v=0, steps=28, inc=t/steps;
    const fmt = n => money ? '₹'+Math.round(n).toLocaleString('en-IN') : Math.round(n).toLocaleString('en-IN');
    el.textContent = money?'₹0':'0';
    const timer = setInterval(()=>{
      v+=inc; if(v>=t){v=t; clearInterval(timer)}
      el.textContent = fmt(v);
    }, dur/steps);
  }

  // theme toggle (dark default; .theme-light overrides)
  function setupThemeToggle(btn){
    if(!btn) return;
    const root = document.documentElement;
    const KEY='themePref';
    const saved = localStorage.getItem(KEY);
    if(saved==='light') root.classList.add('theme-light');
    btn.addEventListener('click', ()=>{
      root.classList.toggle('theme-light');
      localStorage.setItem(KEY, root.classList.contains('theme-light') ? 'light' : 'dark');
      btn.blur();
    });
  }

  function boot(){
    // greet
    const g = $('#greet'); if(g) g.textContent = greet();

    // tips
    rotateTips($('#tip'), [
      "Tip: Press Alt + / to open Assistant",
      "Add expenses to see true profit",
      "Use Quick Sale to log in 3 taps",
      "Enable WhatsApp reminders for credits"
    ]);

    // parallax strip
    parallax($('.parallax'));

    // count-ups
    $$('.kpiValue[data-count]').forEach(el=>{
      const money = (el.dataset.money === '1') || el.textContent.trim().startsWith('₹');
      countUp(el, {money});
    });

    // theme toggle
    setupThemeToggle($('#themeToggle'));
  }

  return { boot, countUp, rotateTips };
})();
document.addEventListener('DOMContentLoaded', PremiumUX.boot);
</script>
