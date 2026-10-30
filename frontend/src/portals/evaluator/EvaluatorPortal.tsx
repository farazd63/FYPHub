import { useEffect, useState } from "react";
import { EvaluatorOverview } from "./EvaluatorOverview";
import { EvaluatorSidebar } from "./EvaluatorSidebar";
import "../student/student.css";
import "./evaluator.css";

export type EvaluatorNavKey = "overview" | "queue" | "proposal" | "schedule" | "criteria" | "scoring" | "history";

type Props = { user: { full_name: string }; onLogout: () => void };

const titles: Record<Exclude<EvaluatorNavKey, "overview">, string> = {
  queue: "Evaluation Queue",
  proposal: "Proposal Review",
  schedule: "Defense Schedule",
  criteria: "Evaluation Criteria",
  scoring: "Scoring & Feedback",
  history: "Decision History",
};

export function EvaluatorPortal({ user, onLogout }: Props) {
  const [active, setActive] = useState<EvaluatorNavKey>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  const initials = user.full_name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "E";
  return (
    <main className="student-shell evaluator-shell">
      <header className="student-header">
        <div className="student-header__left">
          <button type="button" className="student-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>☰</button>
          <div className="student-brand"><svg aria-hidden="true" viewBox="0 0 56 40" fill="none"><path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor"/><path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg><span>FYPHub</span></div>
          <span className="student-role">Evaluator</span>
        </div>
        <div className="student-account"><span className="student-avatar" aria-hidden="true">{initials}</span><span className="student-account__name">{user.full_name}</span><button type="button" className="student-logout" onClick={onLogout}>Logout</button></div>
      </header>
      <div className="student-body">
        <EvaluatorSidebar active={active} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={setActive} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} />
        <section className="student-content"><div className="student-content__inner">
          {active === "overview" ? <EvaluatorOverview onSelect={setActive} /> : <section className="student-phase-page" aria-labelledby="evaluator-feature-heading"><div className="student-page-heading"><p className="student-overview__eyebrow">Evaluator workspace</p><h1 id="evaluator-feature-heading">{titles[active]}</h1><p>This evaluator feature is not available yet because the corresponding authorized backend workflow is not implemented.</p></div><article className="student-placeholder evaluator-placeholder"><div className="student-placeholder__icon" aria-hidden="true">✓</div><div><span className="student-status student-status--future">Unavailable</span><h2>No evaluator records available</h2><p>No assignments, documents, criteria, scores, feedback, schedules, or decisions are fabricated. Access will remain limited to records assigned to this evaluator.</p></div></article></section>}
        </div></section>
      </div>
    </main>
  );
}
