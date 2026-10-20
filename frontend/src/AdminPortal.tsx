import { useEffect, useState, type ReactNode } from "react";
import { AdminCycleManager } from "./AdminCycleManager";
import { AdminOverview } from "./AdminOverview";
import { AdminTemplateReferences } from "./AdminTemplateReferences";
import { AdminUsersRoles } from "./AdminUsersRoles";
import { AdminSupervisorCapacity } from "./AdminSupervisorCapacity";
import { AdminEvaluationRubrics } from "./AdminEvaluationRubrics";
import { AdminDeadlines } from "./AdminDeadlines";

type User={full_name:string;email:string;role:string};
type Page="overview"|"users"|"cycles"|"templates"|"capacity"|"rubrics"|"deadlines";
type IconName="dashboard"|"users"|"calendarCheck"|"document"|"capacity"|"rubric"|"deadline"|"reminder"|"audit";
const items:[string,Page|null,IconName][]=[
 ["Overview","overview","dashboard"],["Users & Roles","users","users"],["Academic Cycles & Policies","cycles","calendarCheck"],["Proposal Templates","templates","document"],["Supervisor Capacity","capacity","capacity"],["Evaluation Rubrics","rubrics","rubric"],["Deadlines","deadlines","deadline"],["Reminders & Escalations",null,"reminder"],["Audit History",null,"audit"]
];
function SidebarIcon({name}:{name:IconName}){const paths:Record<IconName,ReactNode>={
 dashboard:<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
 users:<><circle cx="9" cy="8" r="3"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0M17 11l3 1.3v3.2c0 2-1.3 3.8-3 4.5-1.7-.7-3-2.5-3-4.5v-3.2L17 11Z"/><path d="m15.8 15.5.8.8 1.7-1.9"/></>,
 calendarCheck:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18m-10 6 2 2 4-4"/></>,
 document:<><path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h5M9 12h6m-6 4h6m-6 4h4"/></>,
 capacity:<><circle cx="8" cy="8" r="3"/><path d="M2.5 20a5.5 5.5 0 0 1 11 0M17 7a2.5 2.5 0 1 1 0 5m2 8a4 4 0 0 0-3.5-3.9M17 16v4m-2-2h4"/></>,
 rubric:<><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 3.5h6v3H9zM9 11l1.5 1.5L13 10m2 1h1m-7 5 1.5 1.5L13 15m2 1h1"/></>,
 deadline:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/><circle cx="16" cy="16" r="3"/><path d="M16 14.5V16l1.2.8"/></>,
 reminder:<><path d="M18 16v-5a6 6 0 0 0-12 0v5l-2 2h16l-2-2ZM10 21h4"/><path d="M17 4v5m0-5-2 2m2-2 2 2"/></>,
 audit:<><path d="M6 3h9l3 3v15H6V3Z"/><path d="M15 3v4h4M9 11h5m-5 4h4"/><circle cx="17" cy="18" r="3"/><path d="M17 16.5V18l1.2.8"/></>
};return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5 shrink-0 stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>}
function Brand(){return <div className="flex items-center gap-2.5"><svg aria-hidden="true" viewBox="0 0 56 40" fill="none" className="h-8 w-9 text-[#176b66]"><path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor"/><path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg><span className="text-[17px] font-bold tracking-tight">FYPHub</span></div>}
export function AdminPortal({api,user,onLogout}:{api:string;user:User;onLogout:()=>void}){
 const [page,setPage]=useState<Page>("overview"),[menu,setMenu]=useState(false),[revision,setRevision]=useState(0);
 useEffect(()=>{const close=(e:KeyboardEvent)=>e.key==="Escape"&&setMenu(false);addEventListener("keydown",close);return()=>removeEventListener("keydown",close)},[]);
 const changed=()=>setRevision(v=>v+1);
 const content=page==="users"?<AdminUsersRoles api={api}/>:page==="cycles"?<AdminCycleManager api={api} onChanged={changed}/>:page==="templates"?<AdminTemplateReferences api={api}/>:page==="capacity"?<AdminSupervisorCapacity api={api}/>:page==="rubrics"?<AdminEvaluationRubrics api={api}/>:page==="deadlines"?<AdminDeadlines api={api}/>:<AdminOverview key={revision} api={api}/>;
 return <main className="min-h-screen overflow-x-hidden bg-[#f7f5ef] text-[#243746]"><header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[#dce4de] bg-white/95 px-4 backdrop-blur-sm sm:px-6"><div className="flex items-center gap-3"><button type="button" aria-label={menu?"Close navigation":"Open navigation"} aria-expanded={menu} onClick={()=>setMenu(!menu)} className="rounded-lg p-2 text-[#176b66] transition-colors duration-200 hover:bg-[#e4eee7] active:scale-95 md:hidden">☰</button><Brand/><span className="hidden rounded-full bg-[#e4eee7] px-2 py-1 text-xs font-bold text-[#176b66] sm:inline">Administrator</span></div><div className="flex gap-3"><span className="hidden text-sm font-semibold md:inline">{user.full_name}</span><button type="button" onClick={onLogout} className="rounded-lg border border-[#b8cdc1] px-3 py-1.5 text-sm font-semibold text-[#176b66] transition duration-200 hover:bg-[#e4eee7] active:scale-[.98]">Logout</button></div></header><div className="flex"><aside className={(menu?"translate-x-0":"-translate-x-full")+" admin-sidebar fixed inset-y-16 left-0 z-30 w-60 border-r border-[#dce4de] bg-white p-4 shadow-lg transition-transform duration-[250ms] md:static md:min-h-[calc(100vh-64px)] md:translate-x-0 md:shadow-none"}><nav aria-label="Admin navigation" className="grid gap-1.5">{items.map(([label,target,icon])=>target?<button key={label} type="button" onClick={()=>{setPage(target);setMenu(false)}} aria-current={page===target?"page":undefined} className={(page===target?"bg-[#e4eee7] font-bold text-[#176b66]":"text-[#60716b] hover:bg-[#f4f8f5]")+" flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors duration-200"}><SidebarIcon name={icon}/><span>{label}</span></button>:<span key={label} aria-disabled="true" className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[#84918c]"><SidebarIcon name={icon}/><span>{label}</span></span>)}</nav></aside><button type="button" aria-label="Close navigation" onClick={()=>setMenu(false)} className={(menu?"opacity-100":"pointer-events-none opacity-0")+" fixed inset-0 z-20 bg-[#243746]/25 transition-opacity duration-[250ms] md:hidden"}/><section className="min-w-0 flex-1 p-6 sm:p-8"><div className="mx-auto max-w-5xl admin-enter">{content}</div></section></div></main>
}
