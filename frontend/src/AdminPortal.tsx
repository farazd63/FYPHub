import { useEffect, useState } from "react";
import { AdminWorkflowPolicies } from "./AdminWorkflowPolicies";
import { AdminCycleManager } from "./AdminCycleManager";
import { AdminOverview } from "./AdminOverview";
import { AdminTemplateReferences } from "./AdminTemplateReferences";
import { AdminUsersRoles } from "./AdminUsersRoles";
import { AdminSupervisorCapacity } from "./AdminSupervisorCapacity";
import { AdminEvaluationRubrics } from "./AdminEvaluationRubrics";
import { AdminReminderRules } from "./AdminReminderRules";
import { AdminAuditHistory } from "./AdminAuditHistory";
import { AdminStudentRoster } from "./AdminStudentRoster";
import { AdminDeadlines } from "./AdminDeadlines";
import { AdminSupervisorRequests } from "./portals/admin/modules/supervisor-requests/AdminSupervisorRequests";
import { ArchiveManagement } from "./portals/admin/modules/archive/ArchiveManagement";
import { AdminTemplateUploadModal } from "./modules/module_03_proposal/components/AdminTemplateUploadModal";
import { AdminFypRegistry } from "./portals/admin/modules/fyp-registry/AdminFypRegistry";
import { AdminDocumentRequirementManagerClean as AdminDocumentRequirementManager } from "./AdminDocumentRequirementManagerClean";
import "./AdminSidebar.css";
import "./modules/module_03_proposal/module03.css";

type User={full_name:string;email:string;role:string};
type Page="overview"|"users"|"cycles"|"templates"|"capacity"|"rubrics"|"deadlines"|"reminders"|"audit"|"eligibility"|"workflow"|"supervisorRequests"|"archive"|"module03"|"registry"|"documentRequirements";
type NavItem={label:string;page:Page}; type NavGroup={id:string;label:string;items:NavItem[]};
const groups:NavGroup[]=[
 {id:"workspace",label:"Workspace",items:[{label:"Overview",page:"overview"},{label:"FYP Registry & Project Monitoring",page:"registry"},{label:"FYP Archive",page:"archive"}]},
 {id:"people",label:"People & Access",items:[{label:"Users & Roles",page:"users"},{label:"Student Eligibility",page:"eligibility"},{label:"Supervisor Capacity",page:"capacity"},{label:"Supervisor Requests",page:"supervisorRequests"}]},
 {id:"academic",label:"Academic Setup",items:[{label:"Academic Cycles & Policies",page:"cycles"},{label:"Workflow Policies",page:"workflow"},{label:"Proposal Templates",page:"templates"},{label:"Module 03 Compliance",page:"module03"}]},
 {id:"requirements",label:"Requirements & Review",items:[{label:"Required Documents",page:"documentRequirements"},{label:"Evaluation Criteria",page:"rubrics"},{label:"Deadlines",page:"deadlines"},{label:"Reminders & Escalations",page:"reminders"}]},
 {id:"governance",label:"Governance",items:[{label:"Audit History",page:"audit"}]},
];
const fromPath=():Page=>window.location.pathname==="/admin/document-requirements"?"documentRequirements":"overview";
const pagePath=(page:Page)=>page==="documentRequirements"?"/admin/document-requirements":"/admin";
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
 const content=page==="documentRequirements"?<AdminDocumentRequirementManager api={api}/>:page==="workflow"?<AdminWorkflowPolicies api={api}/>:page==="users"?<AdminUsersRoles api={api}/>:page==="cycles"?<AdminCycleManager api={api} onChanged={changed}/>:page==="templates"?<AdminTemplateReferences api={api}/>:page==="module03"?<section className="module03-page"><div className="module03-heading"><p className="student-overview__eyebrow">Module 03 - Admin configuration</p><h1>Dynamic proposal compliance baselines</h1></div><div className="module03-card"><h2>Reference template ingestion</h2><AdminTemplateUploadModal api={api} onSaved={changed}/></div></section>:page==="capacity"?<AdminSupervisorCapacity api={api}/>:page==="supervisorRequests"?<AdminSupervisorRequests api={api}/>:page==="registry"?<AdminFypRegistry api={api}/>:page==="archive"?<ArchiveManagement api={api}/>:page==="rubrics"?<AdminEvaluationRubrics api={api}/>:page==="deadlines"?<AdminDeadlines api={api}/>:page==="reminders"?<AdminReminderRules api={api}/>:page==="audit"?<AdminAuditHistory api={api}/>:page==="eligibility"?<AdminStudentRoster api={api}/>:<AdminOverview key={revision} api={api}/>;
 return <main className={`min-h-screen overflow-x-hidden bg-[#f7f5ef] text-[#243746] ${collapsed?"admin-sidebar-collapsed":""}`}><header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[#dce4de] bg-white/95 px-4 sm:px-6"><div className="flex items-center gap-3"><button type="button" aria-label={menu?"Close navigation":"Open navigation"} aria-expanded={menu} onClick={()=>setMenu(!menu)} className="rounded-lg p-2 md:hidden">☰</button><strong>FYPHub</strong><span className="admin-role hidden sm:inline-flex">Administrator</span></div><div className="admin-account flex gap-3"><span className="admin-avatar">{initials}</span><span className="admin-account-name hidden text-sm font-semibold md:inline">{user.full_name}</span><button type="button" onClick={onLogout} className="admin-logout rounded-lg border px-3 py-1.5 text-sm font-semibold">Logout</button></div></header><div className="flex"><aside className={`${menu?"translate-x-0":"-translate-x-full"} admin-sidebar fixed inset-y-16 left-0 z-30 w-60 border-r p-4 shadow-lg transition-transform md:static md:min-h-[calc(100vh-64px)] md:translate-x-0 md:shadow-none`}><button type="button" className="admin-sidebar-toggle hidden md:grid" aria-label={collapsed?"Expand navigation":"Collapse navigation"} onClick={()=>setCollapsed(value=>!value)}>‹</button><nav aria-label="Admin navigation" className="grid gap-2">{groups.map(group=><div key={group.id} className="admin-nav-group"><button type="button" className="admin-nav-group-toggle flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs font-bold uppercase tracking-[.12em]" aria-expanded={Boolean(expanded[group.id])} onClick={()=>setExpanded(value=>({...value,[group.id]:!value[group.id]}))}><span>{group.label}</span><span aria-hidden="true">{expanded[group.id]?"⌄":"›"}</span></button>{expanded[group.id]&&<div className="grid gap-1 pl-2">{group.items.map(item=>{const allowed=item.page!=="documentRequirements"||permitted;return <button key={item.page} type="button" disabled={!allowed} onClick={()=>navigate(item.page)} aria-current={page===item.page?"page":undefined} className={`${page===item.page?"bg-[#e4eee7] font-bold text-[#176b66]":"text-[#60716b] hover:bg-[#f4f8f5]"} flex items-center rounded-lg px-3 py-2.5 text-left text-sm disabled:cursor-not-allowed disabled:opacity-50`}><span>{item.label}</span></button>})}</div>}</div>)}</nav></aside><button type="button" aria-label="Close navigation" onClick={()=>setMenu(false)} className={`${menu?"opacity-100":"pointer-events-none opacity-0"} fixed inset-0 z-20 bg-[#243746]/25 md:hidden`}/><section className="min-w-0 flex-1 p-6 sm:p-8"><div className="mx-auto max-w-5xl admin-enter">{demoWarning&&<p role="status">{demoWarning}</p>}{content}</div></section></div></main>;
}
