import { useEffect, useState } from "react";
import { EvaluatorOverview } from "../../evaluator/EvaluatorOverview";
import { EvaluatorSidebar } from "../../evaluator/EvaluatorSidebar";
import { FypHubBrand } from "../../shared/FypHubBrand";
import { Menu } from "lucide-react";
import { ThemeToggle } from "../../../ui/ThemeToggle";
import { displayInitials } from "../../shared/displayInitials";
import { EvaluatorWorkflow } from "./EvaluatorWorkflow";
import { ProposalComplianceWorkspace } from "../../../modules/module-3/ProposalComplianceWorkspace";
import "../student.css";
import "../../evaluator/evaluator.css";

type EvaluatorNavKey = "overview" | "queue" | "proposal" | "schedule" | "criteria" | "scoring" | "history";

export function StudentEvaluatorPortal({ api, user, onLogout }: { api: string; user: { full_name: string }; onLogout: () => void }) {
  const [active, setActive] = useState<EvaluatorNavKey>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  const initials = displayInitials(user.full_name, "E");
  return <main className="student-shell evaluator-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}><Menu aria-hidden="true" strokeWidth={1.75} size={20} /></button><FypHubBrand className="student-brand" /><span className="student-role">Evaluator</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><ThemeToggle /><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><EvaluatorSidebar active={active} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={setActive} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{active === "overview" ? <EvaluatorOverview onSelect={setActive} /> : active === "proposal" ? <ProposalComplianceWorkspace api={api} reviewerMode /> : <EvaluatorWorkflow api={api} view={active} />}</div></section></div></main>;
}
