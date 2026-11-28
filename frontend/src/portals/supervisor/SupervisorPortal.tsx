import { useEffect, useState } from "react";
import { SupervisorRequestsPdf } from "./modules/supervisor-requests/SupervisorRequestsPdf";
import { SupervisorSidebar } from "./SupervisorSidebar";
import { SupervisorOverview } from "./SupervisorOverview";
import { SupervisorAssignedTeams } from "./SupervisorAssignedTeams";
import { SupervisorDecisionHistory } from "./SupervisorDecisionHistory";
import { SupervisorCapacity } from "./SupervisorCapacity";
import { FypHubBrand } from "../shared/FypHubBrand";
import { Menu } from "lucide-react";
import { ThemeToggle } from "../../ui/ThemeToggle";
import { AnnouncementBell } from "../../announcements/AnnouncementBell";
import "../student/student.css";
import "../student/modules/student-collaboration.css";
import "../shared/conversation-layout.css";
import "./modules/supervisor-requests/supervisor-requests.css";
import "./supervisor-group-workspace.css";
import { pushPortalRoute, replacePortalRoute } from "../shared/portal-history";
import { usePersistentSidebarCollapse } from "../shared/usePersistentSidebarCollapse";
import { appPathname } from "../../platform-path";
import { PortalModeSwitcher, type PortalMode } from "../shared/PortalModeSwitcher";

type SupervisorUser = { full_name: string; role?: string; roles?: string[]; coordinator_academic_cycle_ids?: number[] };
type Page = "overview" | "requests" | "assigned" | "capacity" | "history";
const supervisorPageFromPath = (): Page => { const path = appPathname(); return path.startsWith("/supervisor/groups/") || path === "/supervisor/assigned-groups" || path.startsWith("/supervisor/review") ? "assigned" : path === "/supervisor/requests" ? "requests" : path === "/supervisor/capacity" ? "capacity" : path === "/supervisor/history" ? "history" : "overview"; };
const supervisorPath = (page: Page) => page === "overview" ? "/supervisor" : `/supervisor/${page === "assigned" ? "assigned-groups" : page}`;
export function SupervisorPortal({ api, user, onLogout, onPortalChange }: { api: string; user: SupervisorUser; onLogout: () => void; onPortalChange?: (mode: PortalMode) => void }) {
  const [mobileOpen, setMobileOpen] = useState(false); const [collapsed, setCollapsed] = usePersistentSidebarCollapse("supervisor"); const [page, setPage] = useState<Page>(supervisorPageFromPath);
  useEffect(() => { if (appPathname().startsWith("/supervisor/review")) replacePortalRoute("/supervisor/assigned-groups"); }, []);
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  useEffect(() => { const syncFromHistory = () => { setPage(supervisorPageFromPath()); setMobileOpen(false); window.scrollTo({ top: 0, left: 0, behavior: "auto" }); }; window.addEventListener("popstate", syncFromHistory); return () => window.removeEventListener("popstate", syncFromHistory); }, []);
  const [requestId, setRequestId] = useState<number | undefined>();
  const availableModes = (user.roles ?? [user.role]).filter((role): role is PortalMode => role === "SUPERVISOR" || role === "COORDINATOR" || role === "PANEL_MEMBER" || role === "ADMIN");
  if (!availableModes.includes("COORDINATOR") && user.coordinator_academic_cycle_ids?.length) availableModes.push("COORDINATOR");
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "S";
  const navigate = (next: Page) => { setPage(next); setMobileOpen(false); const path = supervisorPath(next); if (appPathname() !== path) pushPortalRoute(path); window.scrollTo({ top: 0, left: 0, behavior: "auto" }); };
  const content = page === "overview" ? <SupervisorOverview api={api} onOpenRequest={(id) => { setRequestId(id); navigate("requests"); }} /> : page === "requests" ? <SupervisorRequestsPdf api={api} initialRequestId={requestId} /> : page === "assigned" ? <SupervisorAssignedTeams api={api} /> : page === "capacity" ? <SupervisorCapacity api={api} /> : <SupervisorDecisionHistory api={api} />;
  return <main className="student-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}><Menu aria-hidden="true" strokeWidth={1.75} size={20} /></button><FypHubBrand className="student-brand" />{onPortalChange ? <PortalModeSwitcher active="SUPERVISOR" available={availableModes} onChange={onPortalChange} /> : <span className="student-role">Supervisor</span>}</div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><AnnouncementBell api={api} role={user.role} /><ThemeToggle /><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><SupervisorSidebar active={page} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={(value) => navigate(value as Page)} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{content}</div></section></div></main>;
}
