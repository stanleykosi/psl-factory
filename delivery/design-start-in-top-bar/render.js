const {chromium}=require('/Users/Hunchoo/psl-factory/frontend/node_modules/playwright');
const fs=require('fs'),cp=require('child_process');
const W='/Users/Hunchoo/psl-factory-worktrees/design-start/design/canvas/';
const changed=JSON.parse(fs.readFileSync('/private/tmp/claude-501/design-start/changed.json'));
const shots=['SCR-03-mobile','SCR-10-mobile','J04-mobile','SCR-02-mobile-evidence-asked','SCR-26-mobile-accepted','SCR-16-mobile-validation'];
(async()=>{
 const b=await chromium.launch(); const out=[];
 for(const [cv,name] of changed){
  const dir=W+(cv=='main'?'project/':'finance/project/');
  const base=name.replace('.dc.html','');
  const pg=await b.newPage({viewport:{width:390,height:844}});
  await pg.goto('file://'+dir+name); await pg.waitForTimeout(600);
  const r=await pg.evaluate(()=>{
   const s=document.querySelector('[data-cmp="CMP-23"]'); if(!s) return {err:'no start'};
   const bar=s.closest('div'); const br=bar.getBoundingClientRect(), sr=s.getBoundingClientRect();
   const kids=[...bar.querySelectorAll('a,span')].filter(e=>!s.contains(e)&&e.textContent.trim()&&!e.querySelector('span,a')).map(e=>e.getBoundingClientRect());
   const overlap=kids.some(k=>k.right>sr.left+0.5&&k.left<sr.right&&k.bottom>sr.top&&k.top<sr.bottom);
   return {barH:br.height,barW:br.width,sl:sr.left,sr:sr.right,sh:sr.height,overlap,overflow:bar.scrollWidth>bar.clientWidth+0.5,wrapRows:new Set([...bar.querySelectorAll('a,span')].filter(e=>e.textContent.trim()).map(e=>Math.round(e.getBoundingClientRect().top))).size,
    sw:document.documentElement.scrollWidth};
  });
  r.board=cv+'/'+name; r.ok=!r.err&&!r.overlap&&!r.overflow&&r.barH<=56.5&&r.sr<=390-15&&r.sw<=390;
  out.push(r);
  if(shots.includes(base)&&(cv=='main'||base.includes('evidence'))){
    const tag=(cv=='main'?'main-':'fin-')+base;
    await pg.screenshot({path:'/Users/Hunchoo/psl-factory/delivery/design-start-in-top-bar/shots/'+tag+'-after.png',clip:{x:0,y:0,width:390,height:300}});
    const old=cp.execSync(`git -C /Users/Hunchoo/psl-factory-worktrees/design-start show HEAD:design/canvas/${cv=='main'?'project':'finance/project'}/${name}`,{maxBuffer:1e8}).toString();
    const tmp=dir+'__before_'+name; fs.writeFileSync(tmp,old);
    const p2=await b.newPage({viewport:{width:390,height:844}}); await p2.goto('file://'+tmp); await p2.waitForTimeout(600);
    await p2.screenshot({path:'/Users/Hunchoo/psl-factory/delivery/design-start-in-top-bar/shots/'+tag+'-before.png',clip:{x:0,y:0,width:390,height:300}});
    const bt=await p2.evaluate(()=>{const d=document.querySelector('h1');return d?d.getBoundingClientRect().top:null}); const at=await pg.evaluate(()=>{const d=document.querySelector('h1');return d?d.getBoundingClientRect().top:null});
    r.h1before=bt; r.h1after=at;
    await p2.close(); fs.unlinkSync(tmp);
  }
  await pg.close();
 }
 fs.writeFileSync('/private/tmp/claude-501/design-start/render.json',JSON.stringify(out,null,1));
 const bad=out.filter(r=>!r.ok); console.log('checked',out.length,'bad',bad.length); console.log(JSON.stringify(bad.slice(0,15)));
 console.log(JSON.stringify(out.filter(r=>r.h1before!==undefined)));
 await b.close();
})();
