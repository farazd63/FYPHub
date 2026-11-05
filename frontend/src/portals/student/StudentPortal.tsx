import { useEffect, useState, type ReactNode } from "react";
import { StudentOverviewWithDocuments as StudentOverview } from "./StudentOverview";
import { StudentSidebar, type StudentPhase } from "./StudentSidebar";
import { StudentPhasePlaceholder } from "./modules/StudentPhasePlaceholder";
import { StudentTeamPhase } from "./modules/StudentTeamPhase";
import { StudentSupervisorSelection } from "./modules/supervisor-selection/StudentSupervisorSelection";
import { KnowledgeSearch } from "./modules/knowledge-search/KnowledgeSearch";
import { ProposalWorkspace } from "../../modules/module-3/ProposalWorkspace";
import "./student.css";
import "./modules/archive-knowledge.css";
import "./student-visibility.css";

type StudentUser = { id: number; full_name: string; email: string; registration_number: string | null; role: string };

const icon = (kind: "team" | "proposal" | "search" | "supervisor" | "review" | "route" | "panel" | "progress" | "archive" | "knowledge" | "compliance"): ReactNode => {
  const paths = {
    team: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 8a3 3 0 1 1 0 6m1 2a5 5 0 0 1 3 4"/></>,
    proposal: <><path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h5M9 13h6m-6 4h5"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    supervisor: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 14v6m-3-3h6"/></>,
    review: <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 11l1.5 1.5L13 10m2 1h1m-7 5 1.5 1.5L13 15m2 1h1"/></>,
    route: <><path d="M5 5h14M5 12h10M5 19h6"/><circle cx="19" cy="12" r="2"/></>,
    panel: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18m-9 4v4m-2-2h4"/></>,
    progress: <><path d="M4 19V5m0 14h16"/><path d="m7 15 3-4 3 2 5-7"/></>,
    archive: <><path d="M4 7h16v13H4zM3 4h18v3H3zM9 11h6"/></>,
    knowledge: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5M8 11h6M11 8v6"/></>,
    compliance: <><path d="M6 3h8l4 4v14H6V3Z"/><path d="m9 13 2 2 4-5M14 3v5h5"/></>,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[kind]}</svg>;
};

export const STUDENT_PHASES: readonly StudentPhase[] = [
  { id: "documents", name: "Required Documents & Uploads", route: "/student/documents", status: "Implemented", icon: icon("proposal") },
  { id: "proposal", name: "Proposal Submission & Review", route: "/student/proposal", status: "Implemented", icon: icon("proposal") },
  { id: "team", name: "Student Team & Collaboration Hub", route: "/student/team", status: "Partial", icon: icon("team") },
  { id: "supervisors", name: "Supervisor Selection & Proposal Requests", route: "/student/supervisors", status: "Partial", icon: icon("supervisor") },
  { id: "progress", name: "Project Progress & Supervision Dashboard", route: "/student/progress", status: "Partial", icon: icon("progress") },
  { id: "search", name: "FYP Archive & Knowledge Search", route: "/student/search", status: "Implemented", icon: icon("knowledge") },
];

function Brand() {
  return <div className="student-brand"><svg aria-hidden="true" viewBox="0 0 56 40" fill="none"><path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor"/><path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg><span>FYPHub</span></div>;
}

export function StudentPortal({ api, user, onLogout }: { api: string; user: StudentUser; onLogout: () => void }) {
  const [activeId, setActiveId] = useState("overview");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  const phase = STUDENT_PHASES.find((item) => item.id === activeId);
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "S";
  const select = (item: StudentPhase) => setActiveId(item.id);
  const content = activeId === "overview"
    ? <StudentOverview phases={STUDENT_PHASES} onSelect={select} />
      : phase?.id === "proposal"
        ? <ProposalWorkspace api={api} />
      : phase?.id === "team"
      ? <StudentTeamPhase api={api} />
      : phase?.id === "supervisors"
        ? <StudentSupervisorSelection api={api} userId={user.id} />
        : phase?.id === "search" || phase?.id === "archive"
          ? <KnowledgeSearch api={api} />
          : phase ? <StudentPhasePlaceholder phase={phase} api={api} /> : null;

  return <main className="student-shell">
    <header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>☰</button><Brand/><span className="student-role">Student</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header>
    <div className="student-body"><StudentSidebar phases={STUDENT_PHASES} activeId={activeId} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={select} onOverview={() => setActiveId("overview")} onToggleCollapse={() => setCollapsed((value) => !value)} onCloseMobile={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{content}</div></section></div>
  </main>;
}
