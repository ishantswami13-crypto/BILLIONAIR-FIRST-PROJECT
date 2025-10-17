// load this in layout below
window.ShopFX=(function(){
  // tiny confetti
  function confetti(){
    const c=document.createElement('canvas');c.style.position='fixed';c.style.inset='0';c.style.pointerEvents='none';c.width=innerWidth;c.height=innerHeight;document.body.appendChild(c);
    const ctx=c.getContext('2d');let pieces=[...Array(150)].map(()=>({x:Math.random()*c.width,y:-20-Math.random()*50,s:4+Math.random()*6,vy:2+Math.random()*3,color:`hsl(${Math.random()*360},90%,60%)`,rot:Math.random()*6}));
    let t=0;function tick(){ctx.clearRect(0,0,c.width,c.height);t++;
      pieces.forEach(p=>{p.y+=p.vy;p.x+=Math.sin((p.y+t)/20);p.rot+=.1;ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rot);ctx.fillStyle=p.color;ctx.fillRect(-p.s/2,-p.s/2,p.s,p.s);ctx.restore();});
      if (t<140) requestAnimationFrame(tick); else document.body.removeChild(c);
    } tick();
  }
  // soft sound (WebAudio)
  function ping(freq=880,ms=160){
    try{const a=new (window.AudioContext||window.webkitAudioContext)();const o=a.createOscillator();const g=a.createGain();
      o.type='sine';o.frequency.value=freq;o.connect(g);g.connect(a.destination);g.gain.setValueAtTime(.0001,a.currentTime);g.gain.exponentialRampToValueAtTime(.2,a.currentTime+.02);
      o.start();g.gain.exponentialRampToValueAtTime(.0001,a.currentTime+ms/1000);o.stop(a.currentTime+ms/1000+.01);}catch(e){}
  }
  // count-up
  function countUp(el,{money=false,duration=900}={}){
    const target=Number(el.dataset.count||0);let cur=0,steps=28,tick=duration/steps,inc=target/steps;
    const fmt=n=>money?('₹'+Math.round(n).toLocaleString('en-IN')):Math.round(n).toLocaleString('en-IN');
    el.textContent=money?'₹0':'0';const t=setInterval(()=>{cur+=inc;if(cur>=target){cur=target;clearInterval(t)}el.textContent=fmt(cur)},tick);
  }
  // rotating tip
  function rotateTip(el,tips,ms=4500){
    let i=0;if(!el||!tips||!tips.length)return;setInterval(()=>{i=(i+1)%tips.length;el.style.opacity=.2;setTimeout(()=>{el.textContent=tips[i];el.style.opacity=1;},200)},ms);
  }
  // celebrate via ?celebrate=1
  function celebrateFromQuery(){
    const u=new URL(location.href);if(u.searchParams.get('celebrate')==='1'){setTimeout(confetti,200);ping(988,180);u.searchParams.delete('celebrate');history.replaceState({},'',u.toString());}
  }
  return {confetti,ping,countUp,rotateTip,celebrateFromQuery};
})();
