// subtle entrance animations
document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.ev-card');
  cards.forEach((c,i)=>{
    c.style.opacity = 0; c.style.transform = 'translateY(6px)';
    setTimeout(()=>{
      c.style.transition = 'opacity .4s ease, transform .4s ease';
      c.style.opacity = 1; c.style.transform = 'translateY(0)';
    }, 120 + i*60);
  });
});
