import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const dir=path.resolve('.audit-working');
const source=await fs.readFile(path.join(dir,'measure-layout.mjs'),'utf8');
const measure=source.split('const measure=`')[1].split('`;')[0];
const cases=[];
for(const role of ['admin','coordinator','supervisor','student','evaluator'])for(const [width,height] of [[1440,900],[1920,1080],[1024,768],[850,700],[768,1024],[390,844],[320,568],[667,375]]){
 cases.push({role,width,height,state:width<768?'mobile-open':'expanded'});
 if(width===1440)cases.push({role,width,height,state:'collapsed'});
}
const html=`<!doctype html><html><body><pre id="results"></pre><script>
const cases=${JSON.stringify(cases)},measure=${JSON.stringify(measure)},results=[];
for(const c of cases){const f=document.createElement('iframe');f.width=c.width;f.height=c.height;f.style.cssText='border:0;display:block';f.src=c.role+'.html';f.onload=()=>{const w=f.contentWindow,d=w.document;
 if(c.state==='mobile-open'){d.querySelector('aside').classList.add('student-sidebar--open');d.querySelector('.student-sidebar__overlay')?.classList.add('student-sidebar__overlay--open');}
 if(c.state==='collapsed'){d.querySelector('aside').classList.add('student-sidebar--collapsed');d.querySelector('main').classList.add('admin-sidebar-collapsed');d.querySelector('main').dataset.sidebar='collapsed';}
 setTimeout(()=>{results.push({...c,...w.eval(measure)});if(results.length===cases.length)document.getElementById('results').textContent='AUDIT_START'+JSON.stringify(results)+'AUDIT_END';},600);
 };document.body.append(f);}
</script></body></html>`;
await fs.writeFile(path.join(dir,'matrix.html'),html);
const result=spawnSync('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--allow-file-access-from-files','--user-data-dir='+path.join(dir,'dump-profile-'+process.pid),'--dump-dom','--virtual-time-budget=5000',pathToFileURL(path.join(dir,'matrix.html')).href],{windowsHide:true,encoding:'utf8',maxBuffer:30*1024*1024,timeout:30000});
await fs.writeFile(path.join(dir,'dump.txt'),result.stdout||'');
const match=result.stdout?.match(/<pre id="results">AUDIT_START(.*?)AUDIT_END<\/pre>/s);
if(!match){console.log(result.error,result.status,result.stderr?.slice(-2000));throw new Error('No layout output');}
const parsed=JSON.parse(match[1].replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>'));
await fs.writeFile(path.join(dir,'layout-results.json'),JSON.stringify(parsed,null,2));
for(const v of parsed)console.log(JSON.stringify({role:v.role,size:[v.width,v.height],state:v.state,sidebar:v.sidebar&&[v.sidebar.width,v.sidebar.y,v.sidebar.height],nav:v.nav&&[v.nav.height,v.nav.scrollHeight,v.nav.rows,v.nav.overflow],items:v.items.map(i=>[i.text,Math.round(i.y),Math.round(i.height)]),content:v.content&&[v.content.padding,v.inner?.width],overflow:v.overflowing.map(i=>i.text)}));
