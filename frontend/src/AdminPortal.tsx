import { useEffect, useState } from "react";
import { AdminCycleManager } from "./AdminCycleManager";
import { AdminOverview } from "./AdminOverview";
import { AdminUsersRoles } from "./AdminUsersRoles";
import { AdminSupervisorCapacity } from "./AdminSupervisorCapacity";
import { AdminReminderRules } from "./AdminReminderRules";
import { AdminDeadlines } from "./AdminDeadlines";
import { ArchiveManagement } from "./portals/admin/modules/archive/ArchiveManagement";
import { AdminDocumentRequirementManagerClean as AdminDocumentRequirementManager } from "./AdminDocumentRequirementManagerClean";
import { AdminProposalTemplates } from "./modules/module-3/AdminProposalTemplates";
import { AdminSidebar } from "./portals/shared/AdminSidebar";
import "./AdminSidebar.css";
type User={full_name:string;email:string;role:string};
type Page="overview"|"users"|"cycles"|"templates"|"capacity"|"deadlines"|"reminders"|"archive"|"documentRequirements";
type NavItem={label:string;page:Page}; type NavGroup={id:string;label:string;items:NavItem[]};
const groups:NavGroup[]=[
 {id:"workspace",label:"Workspace",items:[{label:"Overview",page:"overview"},{label:"FYP Archive",page:"archive"}]},
 {id:"people",label:"People & Access",items:[{label:"Users & Roles",page:"users"},{label:"Supervisor Capacity",page:"capacity"}]},
 {id:"academic",label:"Academic Setup",items:[{label:"Academic Cycles & Policies",page:"cycles"},{label:"Proposal Templates",page:"templates"}]},
 {id:"requirements",label:"Requirements & Review",items:[{label:"Required Documents",page:"documentRequirements"}]},
];
const fromPath=():Page=>window.location.pathname==="/admin/document-requirements"?"documentRequirements":window.location.pathname==="/admin/templates"?"templates":"overview";
const pagePath=(page:Page)=>page==="documentRequirements"?"/admin/document-requirements":page==="templates"?"/admin/templates":"/admin";
const groupId=(page:Page)=>groups.find(g=>g.items.some(i=>i.page===page))?.id??"workspace";

export function AdminPortal({api,user,onLogout}:{api:string;user:User;onLogout:()=>void}){
 const [page,setPage]=useState<Page>(fromPath),[menu,setMenu]=useState(false),[collapsed,setCollapsed]=useState(false),[revision,setRevision]=useState(0),[demoWarning,setDemoWarning]=useState("");
 const [expanded,setExpanded]=useState<Record<string,boolean>>(()=>Object.fromEntries(groups.map(g=>[g.id,g.id===groupId(fromPath())])));
 const permitted=["ADMIN","COORDINATOR"].includes(user.role.trim().toUpperCase());
 const initials=user.full_name.trim().split(/\s+/).filter(Boolean).slice(0,2).map(p=>Array.from(p)[0]).join("").toUpperCase()||"A";
 const changed=()=>setRevision(value=>value+1);
 useEffect(()=>{let cancelled=false;void fetch(`${api}/api/v1/admin/registration-mode`,{credentials:"include"}).then(r=>r.ok?r.json() as Promise<{demo_warning?:string|null}>:null).then(body=>{if(!cancelled&&body?.demo_warning)setDemoWarning(body.demo_warning)}).catch(()=>undefined);return()=>{cancelled=true}},[api]);
 useEffect(()=>{const pop=()=>{const next=fromPath();setPage(next);setExpanded(value=>({...value,[groupId(next)]:true}))};addEventListener("popstate",pop);return()=>removeEventListener("popstate",pop)},[]);
 const navigate=(target:Page)=>{if(target==="documentRequirements"&&!permitted)return;const path=pagePath(target);if(window.location.pathname!==path)window.history.pushState({adminPage:target},"",path);setPage(target);setExpanded(value=>({...value,[groupId(target)]:true}));setMenu(false)};
 const content=page==="documentRequirements"?<AdminDocumentRequirementManager api={api}/>:page==="users"?<AdminUsersRoles api={api}/>:page==="cycles"?<AdminCycleManager api={api} onChanged={changed}/>:page==="templates"?<AdminProposalTemplates api={api}/>:page==="capacity"?<AdminSupervisorCapacity api={api}/>:page==="archive"?<ArchiveManagement api={api}/>:page==="deadlines"?<AdminDeadlines api={api}/>:page==="reminders"?<AdminReminderRules api={api}/>:<AdminOverview key={revision} api={api}/>;
 return <main className={`admin-shell min-h-screen overflow-x-hidden bg-[#f7f5ef] text-[#243746] ${collapsed ? "admin-sidebar-collapsed" : ""}`}><header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[#dce4de] bg-white/95 px-4 sm:px-6"><div className="flex items-center gap-3"><button type="button" aria-label={menu ? "Close navigation" : "Open navigation"} aria-expanded={menu} onClick={() => setMenu(!menu)} className="rounded-lg p-2 md:hidden">☰</button><strong>FYPHub</strong><span className="admin-role hidden sm:inline-flex">Administrator</span></div><div className="admin-account flex gap-3"><span className="admin-avatar">{initials}</span><span className="admin-account-name hidden text-sm font-semibold md:inline">{user.full_name}</span><button type="button" onClick={onLogout} className="admin-logout rounded-lg border px-3 py-1.5 text-sm font-semibold">Logout</button></div></header><div className="flex"><AdminSidebar groups={groups} active={page} collapsed={collapsed} mobileOpen={menu} permitted={permitted} expanded={expanded} onSelect={(target) => navigate(target as Page)} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMenu(false)} onToggleSection={(section) => { const group = groups.find((item) => item.label === section); if (group) setExpanded((value) => ({ ...value, [group.id]: !value[group.id] })); }} /><section className="min-w-0 flex-1 p-6 sm:p-8"><div className="mx-auto max-w-5xl admin-enter">{demoWarning && <p role="status">{demoWarning}</p>}{content}</div></section></div></main>;
}
