import { useEffect, useState } from "react";
import { EvaluatorOverview } from "../../evaluator/EvaluatorOverview";
import { EvaluatorSidebar } from "../../evaluator/EvaluatorSidebar";
import { EvaluatorWorkflow } from "./EvaluatorWorkflow";
import "../student.css";
import "../../evaluator/evaluator.css";

type EvaluatorNavKey = "overview" | "queue" | "proposal" | "schedule" | "criteria" | "scoring" | "history";

export function StudentEvaluatorPortal({ api, user, onLogout }: { api: string; user: { full_name: string }; onLogout: () => void }) {
  const [active, setActive] = useState<EvaluatorNavKey>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "E";
  return <main className="student-shell evaluator-shell"><header className="student-header"><div className="student-header__left"><button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>☰</button><div className="student-brand"><span>FYPHub</span></div><span className="student-role">Evaluator</span></div><div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div></header><div className="student-body"><EvaluatorSidebar active={active} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={setActive} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} /><section className="student-content"><div className="student-content__inner">{active === "overview" ? <EvaluatorOverview onSelect={setActive} /> : <EvaluatorWorkflow api={api} view={active} />}</div></section></div></main>;
}
