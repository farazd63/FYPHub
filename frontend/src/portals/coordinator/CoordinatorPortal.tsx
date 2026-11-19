import { useEffect, useState } from "react";
import { CoordinatorRequestsPdf } from "./modules/supervisor-requests/CoordinatorRequestsPdf";
import { CoordinatorSidebar } from "./CoordinatorSidebar";
import { ProposalComplianceWorkspace } from "../../modules/module-3/ProposalComplianceWorkspace";
import { FypHubBrand } from "../shared/FypHubBrand";
import "../student/student.css";
import "../supervisor/modules/supervisor-requests/supervisor-requests.css";
import "./modules/supervisor-requests/coordinator-requests.css";

type Page = "requests" | "scheduling";

export function CoordinatorPortal({ api, user, onLogout }: { api: string; user: { full_name: string }; onLogout: () => void }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [page, setPage] = useState<Page>("requests");
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "C";
  const content = <><CoordinatorRequestsPdf api={api} /><ProposalComplianceWorkspace api={api} reviewerMode /></>;
  return <main className="student-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>Menu</button><FypHubBrand className="student-brand" /><span className="student-role">Coordinator</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><CoordinatorSidebar active={page} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={(id) => setPage(id as Page)} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{content}</div></section></div></main>;
}
