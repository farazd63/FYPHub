import { useEffect, useState } from "react";
import { SupervisorRequestsPdf } from "./modules/supervisor-requests/SupervisorRequestsPdf";
import { SupervisorSidebar } from "./SupervisorSidebar";
import { SupervisorOverview } from "./SupervisorOverview";
import { SupervisorAssignedTeams } from "./SupervisorAssignedTeams";
import { SupervisorDecisionHistory } from "./SupervisorDecisionHistory";
import { SupervisorUnavailable } from "./SupervisorUnavailable";
import { SupervisorAgentSupervision } from "./SupervisorAgentSupervision";
import { ProposalComplianceWorkspace } from "../../modules/module-3/ProposalComplianceWorkspace";
import "../student/student.css";
import "./modules/supervisor-requests/supervisor-requests.css";

type SupervisorUser = { full_name: string };
type Page = "overview" | "requests" | "assigned" | "review" | "capacity" | "conversations" | "history" | "agent-supervision";
export function SupervisorPortal({ api, user, onLogout }: { api: string; user: SupervisorUser; onLogout: () => void }) {
  const [mobileOpen, setMobileOpen] = useState(false); const [collapsed, setCollapsed] = useState(false); const [page, setPage] = useState<Page>("overview");
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "S";
  const content = page === "overview" ? <SupervisorOverview api={api} onOpenRequest={() => setPage("requests")} /> : page === "requests" ? <><SupervisorRequestsPdf api={api} /><ProposalComplianceWorkspace api={api} reviewerMode /></> : page === "assigned" ? <SupervisorAssignedTeams api={api} /> : page === "history" ? <SupervisorDecisionHistory api={api} /> : page === "agent-supervision" ? <SupervisorAgentSupervision api={api} /> : page === "review" || page === "conversations" ? <SupervisorRequestsPdf api={api} /> : <SupervisorUnavailable title="Supervisor Capacity" description="Capacity is configured and changed by an authorized Admin account." />;
  return <main className="student-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>☰</button><div className="student-brand"><svg aria-hidden="true" viewBox="0 0 56 40" fill="none"><path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor"/><path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg><span>FYPHub</span></div><span className="student-role">Supervisor</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><SupervisorSidebar active={page} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={(value) => setPage(value as Page)} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{content}</div></section></div></main>;
}
