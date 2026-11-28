import { useEffect, useState } from "react";
import { CoordinatorRequestsPdf } from "./modules/supervisor-requests/CoordinatorRequestsPdf";
import { PanelScheduling } from "./modules/supervisor-requests/PanelScheduling";
import { CoordinatorSidebar } from "./CoordinatorSidebar";
import { ProposalComplianceWorkspace } from "../../modules/module-3/ProposalComplianceWorkspace";
import "../student/student.css";
import "../student/student-content.css";
import "../supervisor/modules/supervisor-requests/supervisor-requests.css";
import "./modules/supervisor-requests/coordinator-requests.css";
import { Menu } from "lucide-react";
import { ThemeToggle } from "../../ui/ThemeToggle";
import { AnnouncementBell } from "../../announcements/AnnouncementBell";
import { FypHubBrand } from "../shared/FypHubBrand";
import { AnnouncementSection } from "../../announcements/AnnouncementSection";
import { pushPortalRoute } from "../shared/portal-history";
import { usePersistentSidebarCollapse } from "../shared/usePersistentSidebarCollapse";
import { appPathname } from "../../platform-path";
import { PortalModeSwitcher, type PortalMode } from "../shared/PortalModeSwitcher";

type Page = "overview" | "requests" | "scheduling";
const coordinatorPageFromPath = (): Page => appPathname() === "/coordinator/requests" ? "requests" : appPathname() === "/coordinator/scheduling" ? "scheduling" : "overview";
const coordinatorPath = (page: Page) => page === "overview" ? "/coordinator" : `/coordinator/${page}`;

type CoordinatorUser = { full_name: string; role?: string; roles?: string[]; coordinator_academic_cycle_ids?: number[] };

export function CoordinatorPortal({ api, user, onLogout, onPortalChange }: { api: string; user: CoordinatorUser; onLogout: () => void; onPortalChange?: (mode: PortalMode) => void }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = usePersistentSidebarCollapse("coordinator");
  const [page, setPage] = useState<Page>("overview");
  const availableModes = (user.roles ?? [user.role]).filter((role): role is PortalMode => role === "SUPERVISOR" || role === "COORDINATOR" || role === "PANEL_MEMBER" || role === "ADMIN");
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  useEffect(() => { const syncFromHistory = () => { setPage(coordinatorPageFromPath()); setMobileOpen(false); window.scrollTo({ top: 0, left: 0, behavior: "auto" }); }; window.addEventListener("popstate", syncFromHistory); return () => window.removeEventListener("popstate", syncFromHistory); }, []);
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "C";
  const navigate = (next: Page) => { setPage(next); setMobileOpen(false); const path = coordinatorPath(next); if (appPathname() !== path) pushPortalRoute(path); window.scrollTo({ top: 0, left: 0, behavior: "auto" }); };
  const content = page === "scheduling"
    ? <PanelScheduling api={api} />
    : <div className="coordinator-requests-stack"><AnnouncementSection api={api} /><CoordinatorRequestsPdf api={api} /><ProposalComplianceWorkspace api={api} reviewerMode /></div>;
  return <main className="student-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}><Menu aria-hidden="true" strokeWidth={1.75} size={20} /></button><FypHubBrand className="student-brand" />{onPortalChange ? <PortalModeSwitcher active="COORDINATOR" available={availableModes} onChange={onPortalChange} /> : <span className="student-role">Coordinator</span>}</div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><AnnouncementBell api={api} role={user.role} /><ThemeToggle /><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><CoordinatorSidebar active={page} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={(id) => navigate(id as Page)} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{content}</div></section></div></main>;
}
