import { useEffect, useState } from "react";
import { EvaluatorOverview } from "../../evaluator/EvaluatorOverview";
import { EvaluatorSidebar } from "../../evaluator/EvaluatorSidebar";
import { FypHubBrand } from "../../shared/FypHubBrand";
import { Menu } from "lucide-react";
import { ThemeToggle } from "../../../ui/ThemeToggle";
import { AnnouncementBell } from "../../../announcements/AnnouncementBell";
import { pushPortalRoute } from "../../shared/portal-history";
import { usePersistentSidebarCollapse } from "../../shared/usePersistentSidebarCollapse";
import { displayInitials } from "../../shared/displayInitials";
import { EvaluatorWorkflow } from "./EvaluatorWorkflow";
import { ProposalComplianceWorkspace } from "../../../modules/module-3/ProposalComplianceWorkspace";
import "../student.css";
import "../../evaluator/evaluator.css";
import { appPathname } from "../../../platform-path";

type EvaluatorNavKey = "overview" | "queue" | "proposal" | "schedule" | "criteria" | "scoring" | "history";
const evaluatorPageFromPath = (): EvaluatorNavKey => {
  const value = appPathname().split("/").filter(Boolean).at(-1);
  return ["queue", "proposal", "schedule", "criteria", "scoring", "history"].includes(value ?? "") ? value as EvaluatorNavKey : "overview";
};
const evaluatorPath = (page: EvaluatorNavKey) => page === "overview" ? "/evaluator" : `/evaluator/${page}`;

export function StudentEvaluatorPortal({ api, user, onLogout }: { api: string; user: { full_name: string; role?: string }; onLogout: () => void }) {
  const [active, setActive] = useState<EvaluatorNavKey>(evaluatorPageFromPath);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = usePersistentSidebarCollapse("evaluator");
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  useEffect(() => { const syncFromHistory = () => { setActive(evaluatorPageFromPath()); setMobileOpen(false); window.scrollTo({ top: 0, left: 0, behavior: "auto" }); }; window.addEventListener("popstate", syncFromHistory); return () => window.removeEventListener("popstate", syncFromHistory); }, []);
  const initials = displayInitials(user.full_name, "E");
  const navigate = (next: EvaluatorNavKey) => { setActive(next); setMobileOpen(false); const path = evaluatorPath(next); if (appPathname() !== path) pushPortalRoute(path); window.scrollTo({ top: 0, left: 0, behavior: "auto" }); };
  return <main className="student-shell evaluator-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}><Menu aria-hidden="true" strokeWidth={1.75} size={20} /></button><FypHubBrand className="student-brand" /><span className="student-role">Evaluator</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><AnnouncementBell api={api} role={user.role} /><ThemeToggle /><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><EvaluatorSidebar active={active} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={navigate} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{active === "overview" ? <EvaluatorOverview api={api} onSelect={navigate} /> : active === "proposal" ? <ProposalComplianceWorkspace api={api} reviewerMode /> : <EvaluatorWorkflow api={api} view={active} />}</div></section></div></main>;
}
