import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const dir=path.resolve('.audit-working');
const profile=path.join(dir,'browser-profile-'+process.pid);
await fs.mkdir(profile,{recursive:true});
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-allow-origins=*','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
browser.stderr.on('data',chunk=>{if(String(chunk).includes('websocket')||String(chunk).includes('WebSocket'))console.log(String(chunk))});
let socket;
try {
 let port;
 for(let i=0;i<60;i++){try{port=(await fs.readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;}catch{await new Promise(r=>setTimeout(r,100));}}
 if(!port)throw new Error('Browser did not start');
 const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
 let id=0;const pending=new Map();const events=new Map();
 socket.addEventListener('close',event=>console.log('CDP closed',event.code,event.reason));
 socket.addEventListener('error',event=>console.log('CDP error',event.message));
 socket.addEventListener('message',event=>{const msg=JSON.parse(event.data);if(msg.id){const p=pending.get(msg.id);pending.delete(msg.id);if(p)msg.error?p.reject(msg.error):p.resolve(msg.result);}else{for(const f of events.get(msg.method)||[])f(msg.params);events.delete(msg.method);}});
 const call=(method,params={})=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Timed out: '+method)),15000);pending.set(++id,{resolve:v=>{clearTimeout(timer);resolve(v)},reject:e=>{clearTimeout(timer);reject(e)}});socket.send(JSON.stringify({id,method,params}));});
 const on=method=>new Promise(resolve=>events.set(method,[...(events.get(method)||[]),resolve]));
 await call('Page.enable');
 const measure=`(()=>{
  const r=e=>{if(!e)return null;const b=e.getBoundingClientRect(),s=getComputedStyle(e);return {text:e.innerText?.trim().slice(0,80),x:b.x,y:b.y,width:b.width,height:b.height,bottom:b.bottom,right:b.right,padding:s.padding,margin:s.margin,gap:s.gap,display:s.display,overflow:s.overflow,alignContent:s.alignContent,rows:s.gridTemplateRows,background:s.background,color:s.color,fontSize:s.fontSize,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,clientWidth:e.clientWidth,scrollWidth:e.scrollWidth}};
  return {viewport:[innerWidth,innerHeight],document:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],header:r(document.querySelector('header')),headerChildren:[...document.querySelector('header')?.children||[]].map(r),sidebar:r(document.querySelector('.student-sidebar')),nav:r(document.querySelector('.student-sidebar__nav')),sections:[...document.querySelectorAll('.role-sidebar__section')].map(r),items:[...document.querySelectorAll('.student-sidebar__item')].map(r),content:r(document.querySelector('.portal-content,.student-content,main>header+div>section')),inner:r(document.querySelector('.portal-content__inner,.student-content__inner,.admin-enter')),overview:r(document.querySelector('.cycle-overview')),hero:r(document.querySelector('.cycle-overview__hero')),heroTitle:r(document.querySelector('.cycle-overview__hero h1')),authCard:r(document.querySelector('.auth-card')),overlay:r(document.querySelector('.student-sidebar__overlay')),overflowing:[...document.querySelectorAll('main *')].filter(e=>{const b=e.getBoundingClientRect();return b.width&&b.right>innerWidth+1&&getComputedStyle(e).position!=='fixed'&&!e.closest('aside')}).slice(0,8).map(r)};
 })()`;
 const results=[];
 for(const role of ['admin','coordinator','supervisor','student','evaluator','auth']){
  for(const [width,height] of [[1440,900],[1920,1080],[1024,768],[850,700],[768,1024],[390,844],[320,568],[667,375]]){
   await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
   const loaded=on('Page.loadEventFired');await call('Page.navigate',{url:pathToFileURL(path.join(dir,role+'.html')).href});await loaded;
   if(width<768&&role!=='auth')await call('Runtime.evaluate',{expression:`document.querySelector('aside').classList.add('student-sidebar--open');document.querySelector('.student-sidebar__overlay')?.classList.add('student-sidebar__overlay--open')`});
   await new Promise(r=>setTimeout(r,400));
   const result=await call('Runtime.evaluate',{expression:measure,returnByValue:true});
   results.push({role,width,height,state:width<768?'mobile-open':'expanded',...result.result.value});
   if((width===1440||width===390||width===320||width===667)&&['admin','coordinator','supervisor'].includes(role)){
    const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(path.join(dir,`${role}-${width}.png`),Buffer.from(shot.data,'base64'));
   }
   if(width===1440&&role!=='auth'){
    await call('Runtime.evaluate',{expression:`document.querySelector('aside').classList.add('student-sidebar--collapsed');document.querySelector('main').classList.add('admin-sidebar-collapsed');document.querySelector('main').dataset.sidebar='collapsed'`});
    await new Promise(r=>setTimeout(r,260));
    const collapsed=await call('Runtime.evaluate',{expression:measure,returnByValue:true});results.push({role,width,height,state:'collapsed',...collapsed.result.value});
   }
  }
 }
 await fs.writeFile(path.join(dir,'layout-results.json'),JSON.stringify(results,null,2));
 for(const v of results)console.log(JSON.stringify({role:v.role,size:[v.width,v.height],state:v.state,sidebar:v.sidebar&&[v.sidebar.width,v.sidebar.y,v.sidebar.height],nav:v.nav&&[v.nav.height,v.nav.scrollHeight,v.nav.rows,v.nav.overflow],items:v.items.map(i=>[i.text,Math.round(i.y),Math.round(i.height)]),content:v.content&&[v.content.padding,v.inner?.width],overflow:v.overflowing.map(i=>i.text)}));
 await call('Browser.close');
}finally{socket?.close();browser.kill();}
