import { useEffect, useState, type ReactNode } from "react";
import { StudentCollaborationChannel } from "./modules/StudentCollaborationChannel";
import { StudentOverviewWithDocuments as StudentOverview } from "./StudentOverview";
import { StudentSidebar, type StudentPhase } from "./StudentSidebar";
import { StudentPhasePlaceholder } from "./modules/StudentPhasePlaceholder";
import { StudentRequiredDocumentsDashboard } from "./modules/StudentRequiredDocumentsDashboard";
import { StudentSupervisorSelection } from "./modules/supervisor-selection/StudentSupervisorSelection";
import { KnowledgeSearch } from "./modules/knowledge-search/KnowledgeSearch";
import { ProposalComplianceWorkspace } from "../../modules/module-3/ProposalComplianceWorkspace";
import { GroupMembers } from "./components/GroupMembers";
import { StudentSupervisorInfo } from "./modules/StudentSupervisorInfo";
import { FypHubBrand } from "../shared/FypHubBrand";
import { GroupAIChat } from "../../GroupAIChat";
import "./student.css";
import "./student-content.css";
import "./student-admin-theme.css";
import "./modules/archive-knowledge.css";
import "./student-visibility.css";

type StudentUser = { id: number; full_name: string; email: string; registration_number: string | null; role: string; group_email?: string | null; group_name?: string | null; academic_cycle?: string | null; members?: Array<{ id: number; full_name: string; registration_number: string; email: string | null; designation?: string; is_active?: boolean }> };

const icon = (kind: "team" | "proposal" | "search" | "supervisor" | "review" | "route" | "progress" | "archive" | "knowledge" | "compliance" | "ai"): ReactNode => {
  const paths = {
    team: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 8a3 3 0 1 1 0 6m1 2a5 5 0 0 1 3 4"/></>,
    proposal: <><path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h5M9 13h6m-6 4h5"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    supervisor: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 14v6m-3-3h6"/></>,
    review: <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 11l1.5 1.5L13 10m2 1h1m-7 5 1.5 1.5L13 15m2 1h1"/></>,
    route: <><path d="M5 5h14M5 12h10M5 19h6"/><circle cx="19" cy="12" r="2"/></>,
    progress: <><path d="M4 19V5m0 14h16"/><path d="m7 15 3-4 3 2 5-7"/></>,
    archive: <><path d="M4 7h16v13H4zM3 4h18v3H3zM9 11h6"/></>,
    knowledge: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5M8 11h6M11 8v6"/></>,
    compliance: <><path d="M6 3h8l4 4v14H6V3Z"/><path d="m9 13 2 2 4-5M14 3v5h5"/></>,
    ai: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/><rect x="7" y="7" width="10" height="10" rx="3"/><circle cx="10" cy="12" r=".8" fill="currentColor"/><circle cx="14" cy="12" r=".8" fill="currentColor"/></>,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[kind]}</svg>;
};

export const STUDENT_PHASES: readonly StudentPhase[] = [
  { id: "documents", name: "Required Documents & Uploads", route: "/student/documents", status: "Implemented", icon: icon("proposal") },
  { id: "proposal", name: "Proposal Compliance Check", route: "/student/proposal", status: "Implemented", icon: icon("compliance") },
  { id: "supervisor-info", name: "Supervisor Information", route: "/student/supervisor-info", status: "Implemented", icon: icon("supervisor") },
  { id: "supervisors", name: "Supervisor Selection & Proposal Requests", route: "/student/supervisors", status: "Partial", icon: icon("supervisor") },
  { id: "progress", name: "Project Progress & Supervision Dashboard", route: "/student/progress", status: "Partial", icon: icon("progress") },
  { id: "search", name: "FYP Archive & Knowledge Search", route: "/student/search", status: "Implemented", icon: icon("knowledge") },
  { id: "group-ai", name: "AI Chatbot", route: "/student/group-ai", status: "Implemented", icon: icon("ai") },
];

export function StudentPortal({ api, user, onLogout }: { api: string; user: StudentUser; onLogout: () => void }) {
  const [activeId, setActiveId] = useState(() => window.location.pathname.startsWith("/student/group-ai") ? "group-ai" : "overview");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  const phase = STUDENT_PHASES.find((item) => item.id === activeId);
  const groupLabel = user.group_name || "Student Group";
  const initials = groupLabel.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "G";
  const content = activeId === "overview" ? <div className="grid gap-5"><StudentOverview api={api} /><GroupMembers members={user.members ?? []} /><StudentCollaborationChannel api={api} userId={user.id} /></div> : phase?.id === "documents" ? <StudentRequiredDocumentsDashboard api={api} /> : phase?.id === "proposal" ? <ProposalComplianceWorkspace api={api} /> : phase?.id === "supervisor-info" ? <StudentSupervisorInfo api={api} /> : phase?.id === "supervisors" ? <StudentSupervisorSelection api={api} userId={user.id} /> : phase?.id === "search" || phase?.id === "archive" ? <KnowledgeSearch api={api} /> : phase?.id === "group-ai" ? <GroupAIChat api={api} /> : phase ? <StudentPhasePlaceholder phase={phase} api={api} /> : null;
  const selectPage = (id: string) => { setActiveId(id); const target = STUDENT_PHASES.find((item) => item.id === id); window.history.pushState(window.history.state, "", target?.route || "/student"); };
  return <main className="student-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>Menu</button><FypHubBrand className="student-brand" /><span className="student-role">Student group</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name" title={user.group_email || user.email}>{groupLabel}{user.academic_cycle ? ` · ${user.academic_cycle}` : ""}</span><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><StudentSidebar phases={STUDENT_PHASES} activeId={activeId} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={(item) => selectPage(item.id)} onOverview={() => { setActiveId("overview"); window.history.pushState(window.history.state, "", "/student"); }} onToggleCollapse={() => setCollapsed((value) => !value)} onCloseMobile={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{content}</div></section></div></main>;
}
