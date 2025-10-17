// minimalist Apple-like sheet + confetti helpers
export function openSheet(id) {
  document.getElementById(id)?.classList.remove('hidden');
  document.body.classList.add('no-scroll');
}

export function closeSheet(id) {
  document.getElementById(id)?.classList.add('hidden');
  document.body.classList.remove('no-scroll');
}

window.openSheet = openSheet;
window.closeSheet = closeSheet;

window.launchConfetti = function() {
  const canvas = document.createElement('canvas');
  canvas.style.position = 'fixed';
  canvas.style.inset = '0';
  canvas.style.pointerEvents = 'none';
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  const pieces = Array.from({length: 60}, ()=>({
    x: Math.random()*innerWidth,
    y: Math.random()*innerHeight - innerHeight,
    size: 6+Math.random()*6,
    speed: 2+Math.random()*3,
    color: `hsl(${Math.random()*360},100%,70%)`
  }));
  function frame(){
    ctx.clearRect(0,0,canvas.width=innerWidth,canvas.height=innerHeight);
    for(const p of pieces){
      p.y += p.speed;
      if(p.y > innerHeight) p.y = -20;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x,p.y,p.size/2,0,2*Math.PI);
      ctx.fill();
    }
    requestAnimationFrame(frame);
  }
  frame();
  setTimeout(()=>canvas.remove(), 1500);
};
