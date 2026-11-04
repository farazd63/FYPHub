import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import fs from 'node:fs/promises';
import path from 'node:path';

globalThis.window = {location:{pathname:'/admin'},localStorage:{getItem:()=>null}};
const server = await createServer({server:{middlewareMode:true},appType:'custom'});
const dir = path.resolve('.audit-working');
const assets = await fs.readdir(path.join(dir,'build/assets'));
const css = await fs.readFile(path.join(dir,'build/assets',assets.find(p=>p.endsWith('.css'))),'utf8');
const user = {id:1,full_name:'Audit Example User',email:'audit@example.invalid',role:'ADMIN',is_active:true,registration_number:'AUDIT'};
const entries = [
 ['admin','/src/AdminPortal.tsx','AdminPortal'],
 ['student','/src/portals/student/StudentPortal.tsx','StudentPortal'],
 ['coordinator','/src/portals/coordinator/CoordinatorPortal.tsx','CoordinatorPortal'],
 ['supervisor','/src/portals/supervisor/SupervisorPortal.tsx','SupervisorPortal'],
 ['evaluator','/src/portals/student/modules/StudentEvaluatorPortal.tsx','StudentEvaluatorPortal'],
 ['auth','/src/App.tsx','default']
];
try {
 for(const [role,url,name] of entries){
  try {
   const mod=await server.ssrLoadModule(url);
   const markup=renderToStaticMarkup(React.createElement(mod[name],{api:'http://127.0.0.1:9',user,onLogout:()=>{}}));
   await fs.writeFile(path.join(dir,role+'.html'),`<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>${css}</style></head><body><div id="root">${markup}</div></body></html>`);
   console.log(role+': rendered');
  } catch(error){console.log(role+': '+error.stack);}
 }
} finally {await server.close();}
