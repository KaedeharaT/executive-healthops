() => {
  const rgb = s => {
    if(s.startsWith('#')) { const h=s.slice(1);return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16),1]; }
    const m = s.match(/[\d.]+/g);
    return m ? [Number(m[0]),Number(m[1]),Number(m[2]),m[3]===undefined?1:Number(m[3])] : [0,0,0,0];
  };
  const blend = (a,b) => a.slice(0,3).map((v,i)=>v*a[3]+b[i]*(1-a[3]));
  const lum = c => c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;})
    .reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
  const ratio = (a,b) => (Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
  const findings=[];
  let checked=0;
  for(const e of document.querySelectorAll('[data-testid="stMain"] :is(p,span,small,strong,b,h1,h2,h3,h4,td,th,label,button,a)')) {
    const text=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();
    if(!text || !e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) || e.closest('details:not([open])')) continue;
    const style=getComputedStyle(e);
    if(style.fontFamily.includes('Material') || e.closest('[aria-hidden="true"]')) continue;
    const ancestors=[];
    let opacity=1;
    for(let a=e;a;a=a.parentElement){ancestors.push(a);opacity*=Number(getComputedStyle(a).opacity);}
    let bg=[255,255,255];
    for(const a of ancestors.reverse()) bg=blend(rgb(getComputedStyle(a).backgroundColor),bg);
    const fg=rgb(style.color);fg[3]*=opacity;
    const contrast=ratio(blend(fg,bg),bg);
    const threshold=parseFloat(style.fontSize)>=24 || parseFloat(style.fontSize)>=18.66&&Number(style.fontWeight)>=700 ? 3:4.5;
    checked++;
    if(contrast+0.01<threshold) findings.push({text:text.slice(0,90),contrast:Number(contrast.toFixed(2)),threshold,color:style.color,background:bg,opacity,selector:e.className});
  }
  for(const e of document.querySelectorAll('[style*="--gdg-text-header:"]')) {
    if(!e.checkVisibility({checkVisibilityCSS:true}))continue;
    const s=getComputedStyle(e),bg=blend(rgb(s.getPropertyValue('--gdg-bg-header').trim()),[255,255,255]);
    const fg=rgb(s.getPropertyValue('--gdg-text-header').trim());
    const contrast=ratio(blend(fg,bg),bg);checked++;
    if(contrast<4.5)findings.push({text:'Native canvas table header',contrast:Number(contrast.toFixed(2)),threshold:4.5});
  }
  return {checked,findings};
}
