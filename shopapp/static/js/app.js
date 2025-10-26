// load this in layout below
window.ShopFX = (function () {
  // tiny confetti
  function confetti() {
    const c = document.createElement('canvas');
    c.style.position = 'fixed';
    c.style.inset = '0';
    c.style.pointerEvents = 'none';
    c.width = innerWidth;
    c.height = innerHeight;
    document.body.appendChild(c);
    const ctx = c.getContext('2d');
    const pieces = [...Array(150)].map(() => ({
      x: Math.random() * c.width,
      y: -20 - Math.random() * 50,
      s: 4 + Math.random() * 6,
      vy: 2 + Math.random() * 3,
      color: `hsl(${Math.random() * 360},90%,60%)`,
      rot: Math.random() * 6,
    }));
    let t = 0;
    function tick() {
      ctx.clearRect(0, 0, c.width, c.height);
      t++;
      pieces.forEach((p) => {
        p.y += p.vy;
        p.x += Math.sin((p.y + t) / 20);
        p.rot += 0.1;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.s / 2, -p.s / 2, p.s, p.s);
        ctx.restore();
      });
      if (t < 140) requestAnimationFrame(tick);
      else document.body.removeChild(c);
    }
    tick();
  }

  // soft sound (WebAudio)
  function ping(freq = 880, ms = 160) {
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      const a = new Audio();
      const o = a.createOscillator();
      const g = a.createGain();
      o.type = 'sine';
      o.frequency.value = freq;
      o.connect(g);
      g.connect(a.destination);
      g.gain.setValueAtTime(0.0001, a.currentTime);
      g.gain.exponentialRampToValueAtTime(0.2, a.currentTime + 0.02);
      o.start();
      g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + ms / 1000);
      o.stop(a.currentTime + ms / 1000 + 0.01);
    } catch (_) {
      // ignore
    }
  }

  // count-up
  function countUp(el, { money = false, duration = 900 } = {}) {
    const target = Number(el.dataset.count || 0);
    const rupee = '\u20B9';
    const format = (value) =>
      money
        ? `${rupee}${Math.round(value).toLocaleString('en-IN')}`
        : Math.round(value).toLocaleString('en-IN');
    el.textContent = money ? `${rupee}0` : '0';
    const start = performance.now();
    function tick(now) {
      const progress = Math.min(1, (now - start) / duration);
      const next = target * progress;
      el.textContent = format(next);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // rotating tip
  function rotateTip(el, tips, ms = 4500) {
    let i = 0;
    if (!el || !tips || !tips.length) return;
    setInterval(() => {
      i = (i + 1) % tips.length;
      el.style.opacity = 0.2;
      setTimeout(() => {
        el.textContent = tips[i];
        el.style.opacity = 1;
      }, 200);
    }, ms);
  }

  // celebrate via ?celebrate=1
  function celebrateFromQuery() {
    const u = new URL(location.href);
    if (u.searchParams.get('celebrate') === '1') {
      setTimeout(confetti, 200);
      ping(988, 180);
      u.searchParams.delete('celebrate');
      history.replaceState({}, '', u.toString());
    }
  }

  function animateMetricEntry(node) {
    if (!node || node.dataset.counted === '1') return;
    node.dataset.counted = '1';
    countUp(node, { money: node.dataset.format === 'money' });
  }

  function staggerCards(cards, delay = 90) {
    if (!cards || !cards.length) return;
    const apply = (card) => {
      card.style.setProperty('--stagger-delay', `${card.dataset.staggerDelay || 0}ms`);
      card.classList.add('card-stagger');
    };
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              apply(entry.target);
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.2 }
      );
      cards.forEach((card, index) => {
        if (!card.dataset.staggerDelay) {
          card.dataset.staggerDelay = index * delay;
        }
        observer.observe(card);
      });
    } else {
      cards.forEach((card, index) => {
        if (!card.dataset.staggerDelay) {
          card.dataset.staggerDelay = index * delay;
        }
        apply(card);
      });
    }
  }

  function initDashboard() {
    const shell = document.querySelector('.dashboard-shell');
    if (!shell) return;

    const metricNodes = [...shell.querySelectorAll('.metric-value[data-count]')];
    const cards = [...shell.querySelectorAll('.card')];

    if (metricNodes.length) {
      if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver(
          (entries, obs) => {
            entries.forEach((entry) => {
              if (entry.isIntersecting) {
                animateMetricEntry(entry.target);
                obs.unobserve(entry.target);
              }
            });
          },
          { threshold: 0.75, rootMargin: '0px 0px -40px' }
        );
        metricNodes.forEach((node) => observer.observe(node));
      } else {
        metricNodes.forEach((node) => animateMetricEntry(node));
      }
    }

    staggerCards(cards);
  }

  function initNav() {
    const nav = document.querySelector('.nav');
    const toggle = document.querySelector('[data-nav-toggle]');
    if (!nav || !toggle) return;

    const collapse = () => {
      nav.classList.add('is-collapsed');
      nav.classList.remove('is-expanded');
      toggle.setAttribute('aria-expanded', 'false');
    };

    const expand = () => {
      nav.classList.remove('is-collapsed');
      nav.classList.add('is-expanded');
      toggle.setAttribute('aria-expanded', 'true');
    };

    const sync = () => {
      if (window.innerWidth <= 720) {
        if (!nav.classList.contains('is-collapsed')) collapse();
      } else {
        expand();
      }
    };

    sync();
    window.addEventListener('resize', () => window.requestAnimationFrame(sync));
    toggle.addEventListener('click', () => {
      if (nav.classList.contains('is-collapsed')) {
        expand();
      } else {
        collapse();
      }
    });
  }

  return {
    confetti,
    ping,
    countUp,
    rotateTip,
    celebrateFromQuery,
    initDashboard,
    initNav,
    staggerCards,
  };
})();

document.addEventListener('DOMContentLoaded', () => {
  if (!window.ShopFX) return;
  window.ShopFX.celebrateFromQuery();
  window.ShopFX.initDashboard();
  window.ShopFX.initNav();
});
