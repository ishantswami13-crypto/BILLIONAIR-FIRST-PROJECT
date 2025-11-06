// subtle entrance animations
document.addEventListener('DOMContentLoaded', () => {
  const animatedCards = document.querySelectorAll('[data-animate="card"], .ev-card, .card[data-animate]');
  animatedCards.forEach((card, index) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(12px)';
    setTimeout(() => {
      card.style.transition = 'opacity .45s ease, transform .45s ease, box-shadow .3s ease';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, 160 + index * 70);
  });

  const fadeSections = document.querySelectorAll('[data-animate="fade-up"]');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('fade-in-up');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.25 });
  fadeSections.forEach(section => observer.observe(section));

  const heartbeatDot = document.querySelector('[data-heartbeat-dot]');
  if (heartbeatDot) {
    heartbeatDot.setAttribute('data-state', 'hidden');
    fetch('/api/heartbeat', { cache: 'no-store' })
      .then(res => {
        if (res.ok) {
          heartbeatDot.setAttribute('data-state', 'active');
        }
      })
      .catch(() => {});
  }
});
