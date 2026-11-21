import { useEffect, useState } from "react";
import { SupervisorRequestsPdf } from "./modules/supervisor-requests/SupervisorRequestsPdf";
import { SupervisorSidebar } from "./SupervisorSidebar";
import { SupervisorOverview } from "./SupervisorOverview";
import { SupervisorAssignedTeams } from "./SupervisorAssignedTeams";
import { SupervisorDecisionHistory } from "./SupervisorDecisionHistory";
import { SupervisorUnavailable } from "./SupervisorUnavailable";
import { SupervisorCapacity } from "./SupervisorCapacity";
import { FypHubBrand } from "../shared/FypHubBrand";
import { Menu } from "lucide-react";
import { ThemeToggle } from "../../ui/ThemeToggle";
import { AnnouncementBell } from "../../announcements/AnnouncementBell";
import "../student/student.css";
import "./modules/supervisor-requests/supervisor-requests.css";
import "./supervisor-group-workspace.css";
import { SupervisorExpertiseProfile } from "./modules/SupervisorExpertiseProfile";

type SupervisorUser = { full_name: string };
type Page = "overview" | "requests" | "assigned" | "capacity" | "history" | "expertise";
export function SupervisorPortal({ api, user, onLogout }: { api: string; user: SupervisorUser; onLogout: () => void }) {
  const [mobileOpen, setMobileOpen] = useState(false); const [collapsed, setCollapsed] = useState(false); const [page, setPage] = useState<Page>(() => window.location.pathname.startsWith("/supervisor/groups/") || window.location.pathname === "/supervisor/assigned-groups" ? "assigned" : window.location.pathname === "/supervisor/expertise" ? "expertise" : "overview");
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  const [requestId, setRequestId] = useState<number | undefined>();
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "S";
  const content = page === "overview" ? <SupervisorOverview api={api} onOpenRequest={(id) => { setRequestId(id); setPage("requests"); }} /> : page === "requests" ? <SupervisorRequestsPdf api={api} initialRequestId={requestId} /> : page === "assigned" ? <SupervisorAssignedTeams api={api} /> : page === "capacity" ? <SupervisorCapacity api={api} /> : page === "history" ? <SupervisorDecisionHistory api={api} /> : page === "expertise" ? <SupervisorExpertiseProfile api={api} /> : <SupervisorUnavailable title="Supervisor Capacity" description="Capacity is configured and changed by an authorized Admin account." />;
  return <main className="student-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}><Menu aria-hidden="true" strokeWidth={1.75} size={20} /></button><FypHubBrand className="student-brand" /><span className="student-role">Supervisor</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><AnnouncementBell api={api} /><ThemeToggle /><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><SupervisorSidebar active={page} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={(value) => setPage(value as Page)} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{content}</div></section></div></main>;
}
