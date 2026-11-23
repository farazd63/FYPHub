import { useEffect, useState } from "react";
import { AdminCycleManager } from "./AdminCycleManager";
import { AdminOverview } from "./AdminOverview";
import { AdminCycleDetails } from "./AdminCycleDetails";
import { AdminAnnouncements } from "./AdminAnnouncements";
import { AdminUsersRoles } from "./AdminUsersRoles";
import { AdminStudentGroups } from "./AdminStudentGroups";
import { AdminSupervisorCapacity } from "./AdminSupervisorCapacity";
import { AdminReminderRules } from "./AdminReminderRules";
import { AdminDeadlines } from "./AdminDeadlines";
import { AdminDocumentArchive } from "./AdminDocumentArchive";
import { AdminProposalTemplates } from "./modules/module-3/AdminProposalTemplates";
import { ArchiveManagement } from "./portals/admin/modules/archive/ArchiveManagement";
import { AdminSupervisorMatching } from "./AdminSupervisorMatching";
import { AdminSupervisorReplacement } from "./AdminSupervisorReplacement";
import { AdminSidebar } from "./portals/shared/AdminSidebar";
import { FypHubBrand } from "./portals/shared/FypHubBrand";
import { ChevronLeft, ChevronRight, Menu } from "lucide-react";
import { ThemeToggle } from "./ui/ThemeToggle";
import { AnnouncementBell } from "./announcements/AnnouncementBell";
import { pushPortalRoute } from "./portals/shared/portal-history";
import { usePersistentSidebarCollapse } from "./portals/shared/usePersistentSidebarCollapse";
import "./AdminSidebar.css";
type User={full_name:string;email:string;role:string};
type Page="overview"|"announcements"|"users"|"studentGroups"|"cycles"|"cycleDetails"|"templates"|"capacity"|"deadlines"|"reminders"|"archive"|"documentRequirements"|"matching"|"replacement";
type NavItem={label:string;page:Page}; type NavGroup={id:string;label:string;items:NavItem[]};
const groups:NavGroup[]=[
 {id:"workspace",label:"Workspace",items:[{label:"Overview",page:"overview"},{label:"FYP Archive",page:"archive"}]},
 {id:"people",label:"People & Access",items:[{label:"Student Groups",page:"studentGroups"},{label:"Users & Roles",page:"users"},{label:"Supervisor Capacity",page:"capacity"},{label:"Supervisor Matching",page:"matching"},{label:"Supervisor Replacement",page:"replacement"}]},
 {id:"academic",label:"Academic Setup",items:[{label:"Academic Cycles & Policies",page:"cycles"},{label:"Proposal Templates",page:"templates"}]},
 {id:"requirements",label:"Requirements & Review",items:[{label:"Required Documents",page:"documentRequirements"}]},
];
const cycleIdFromPath=():number|null=>{const match=window.location.pathname.match(/^\/admin\/cycles\/(\d+)$/);if(!match)return null;const value=Number(match[1]);return Number.isInteger(value)&&value>0?value:null;};
const fromPath=():Page=>cycleIdFromPath()!==null?"cycleDetails":window.location.pathname==="/admin/announcements"?"announcements":window.location.pathname==="/admin/document-requirements"||window.location.pathname.startsWith("/admin/document-requirements/cycles/")?"documentRequirements":window.location.pathname==="/admin/templates"?"templates":window.location.pathname==="/admin/archive"?"archive":window.location.pathname==="/admin/student-groups"?"studentGroups":window.location.pathname==="/admin/users"?"users":window.location.pathname==="/admin/supervisor-matching"?"matching":window.location.pathname==="/admin/supervisor-replacement"?"replacement":"overview";
const pagePath=(page:Page,cycleId?:number)=>page==="cycleDetails"?`/admin/cycles/${cycleId}`:page==="announcements"?"/admin/announcements":page==="documentRequirements"?"/admin/document-requirements":page==="templates"?"/admin/templates":page==="archive"?"/admin/archive":page==="studentGroups"?"/admin/student-groups":page==="users"?"/admin/users":page==="matching"?"/admin/supervisor-matching":page==="replacement"?"/admin/supervisor-replacement":"/admin";
const groupId=(page:Page)=>page==="cycleDetails"?"academic":groups.find(g=>g.items.some(i=>i.page===page))?.id??"workspace";
const expandedFor=(page:Page)=>Object.fromEntries(groups.map(group=>[group.id,group.id===groupId(page)]));

export function AdminPortal({api,user,onLogout}:{api:string;user:User;onLogout:()=>void}){
 const [page,setPage]=useState<Page>(fromPath),[cycleDetailId,setCycleDetailId]=useState<number|null>(()=>cycleIdFromPath()),[menu,setMenu]=useState(false),[collapsed,setCollapsed]=usePersistentSidebarCollapse("admin"),[revision,setRevision]=useState(0),[demoWarning,setDemoWarning]=useState("");
 const [expanded,setExpanded]=useState<Record<string,boolean>>(()=>Object.fromEntries(groups.map(g=>[g.id,g.id===groupId(fromPath())])));
 const permitted=["ADMIN","COORDINATOR"].includes(user.role.trim().toUpperCase());
 const initials=user.full_name.trim().split(/\s+/).filter(Boolean).slice(0,2).map(p=>Array.from(p)[0]).join("").toUpperCase()||"A";
 const changed=()=>setRevision(value=>value+1);
 useEffect(()=>{let cancelled=false;void fetch(`${api}/api/v1/admin/registration-mode`,{credentials:"include"}).then(r=>r.ok?r.json() as Promise<{demo_warning?:string|null}>:null).then(body=>{if(!cancelled&&body?.demo_warning)setDemoWarning(body.demo_warning)}).catch(()=>undefined);return()=>{cancelled=true}},[api]);
  useEffect(()=>{const pop=()=>{const next=fromPath();setPage(next);setCycleDetailId(cycleIdFromPath());setExpanded(expandedFor(next));window.scrollTo({top:0,left:0,behavior:"auto"})};addEventListener("popstate",pop);return()=>removeEventListener("popstate",pop)},[]);
  const navigate=(target:Page,selectedCycleId?:number)=>{if(target==="documentRequirements"&&!permitted)return;if(target==="cycleDetails"&&selectedCycleId===undefined)return;const path=pagePath(target,selectedCycleId);if(window.location.pathname!==path)pushPortalRoute(path,"admin-portal");setPage(target);setCycleDetailId(selectedCycleId??null);setExpanded(expandedFor(target));setMenu(false);window.scrollTo({top:0,left:0,behavior:"auto"});};
  const content=page==="cycleDetails"&&cycleDetailId!==null?<AdminCycleDetails api={api} cycleId={cycleDetailId} onBack={()=>navigate("overview")}/>:page==="announcements"?<AdminAnnouncements api={api}/>:page==="documentRequirements"?<AdminDocumentArchive api={api}/>:page==="studentGroups"?<AdminStudentGroups api={api}/>:page==="users"?<AdminUsersRoles api={api}/>:page==="cycles"?<AdminCycleManager api={api} onChanged={changed}/>:page==="templates"?<AdminProposalTemplates api={api}/>:page==="capacity"?<AdminSupervisorCapacity api={api}/>:page==="archive"?<ArchiveManagement api={api}/>:page==="deadlines"?<AdminDeadlines api={api}/>:page==="reminders"?<AdminReminderRules api={api}/>:page==="matching"?<AdminSupervisorMatching api={api}/>:page==="replacement"?<AdminSupervisorReplacement api={api}/>:<AdminOverview key={revision} api={api} onManage={()=>navigate("announcements")} onCycleDetails={(id)=>navigate("cycleDetails",id)}/>;
  return <main className={`admin-shell bg-fy-page text-fy-text ${collapsed ? "admin-sidebar-collapsed" : ""}`}><header className="admin-shell__header flex h-16 items-center justify-between border-b border-fy-border bg-fy-surface px-4 sm:px-6"><div className="admin-header__identity"><div className="flex items-center gap-3"><button type="button" aria-label={menu ? "Close navigation" : "Open navigation"} aria-expanded={menu} onClick={() => setMenu(!menu)} className="rounded-lg p-2 lg:hidden"><Menu aria-hidden="true" strokeWidth={1.75} size={20} /></button><FypHubBrand className="admin-brand" afterHome={<div className="admin-history-controls" aria-label="Browser page navigation"><button type="button" aria-label="Go back" title="Go back" onClick={() => window.history.back()}><ChevronLeft aria-hidden="true" size={16} strokeWidth={2} /></button><button type="button" aria-label="Go forward" title="Go forward" onClick={() => window.history.forward()}><ChevronRight aria-hidden="true" size={16} strokeWidth={2} /></button></div>} /><span className="admin-role hidden md:inline-flex">Administrator</span></div></div><div className="admin-account flex items-center gap-2 sm:gap-3"><span className="admin-avatar hidden sm:inline-grid" aria-hidden="true">{initials}</span><span className="admin-account-name hidden text-sm font-semibold md:inline">{user.full_name}</span><AnnouncementBell api={api} role={user.role} /><ThemeToggle /><button type="button" onClick={onLogout} className="admin-logout rounded-lg border px-2.5 py-1.5 text-sm font-semibold sm:px-3">Logout</button></div></header><div className="admin-shell__body"><AdminSidebar groups={groups} active={page==="cycleDetails"?"cycles":page} collapsed={collapsed} mobileOpen={menu} permitted={permitted} expanded={expanded} onSelect={(target) => navigate(target as Page)} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMenu(false)} onToggleSection={(section, open) => { const group = groups.find((item) => item.label === section); if (group) setExpanded(Object.fromEntries(groups.map((item) => [item.id, item.id === group.id && (open ?? !expanded[item.id])] ))); }} /><section className="admin-shell__content min-w-0 flex-1"><div className="admin-enter w-full min-w-0">{demoWarning && <p role="status">{demoWarning}</p>}{content}</div></section></div></main>;
}
