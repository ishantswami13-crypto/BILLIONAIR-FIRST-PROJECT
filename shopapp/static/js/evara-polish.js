/* Evara counter animation — attach to any element with [data-count="1234"] */
(function(){
  const els = document.querySelectorAll('[data-count], .count-up[data-value]');
  if(!els.length) return;

  const formatterCache = new Map();

  const getFormat = (decimals)=>{
    const key = decimals || 0;
    if(!formatterCache.has(key)){
      formatterCache.set(key, new Intl.NumberFormat('en-IN', {
        minimumFractionDigits: key,
        maximumFractionDigits: key
      }));
    }
    return formatterCache.get(key);
  };

  const animate = (el)=>{
    const rawTarget = el.hasAttribute('data-count')
      ? el.getAttribute('data-count')
      : el.getAttribute('data-value');
    const target = parseFloat(rawTarget || '0');
    const decimals = parseInt(el.getAttribute('data-decimals') || el.getAttribute('data-precision') || '0', 10);
    const prefix = el.getAttribute('data-prefix') || '';
    const suffix = el.getAttribute('data-suffix') || '';
    const duration = 900;
    const start = performance.now();
    const from = 0;
    const format = getFormat(decimals);

    const step = (t)=>{
      const p = Math.min(1, (t - start)/duration);
      const eased = 1 - Math.pow(1 - p, 3);
      const value = from + (target - from)*eased;
      el.textContent = prefix + format.format(decimals ? value : Math.round(value)) + suffix;
      if(p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  const io = new IntersectionObserver((entries)=>{
    entries.forEach(e => {
      if(e.isIntersecting){
        animate(e.target);
        io.unobserve(e.target);
      }
    });
  }, { threshold: .2 });

  els.forEach(el => io.observe(el));
})();
