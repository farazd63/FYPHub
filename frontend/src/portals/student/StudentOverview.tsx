import { StudentRequiredDocumentsDashboard } from "./modules/StudentRequiredDocumentsDashboard";
import { API } from "../../App";
import type { StudentPhase } from "./StudentSidebar";

type Props = { phases: readonly StudentPhase[]; onSelect: (phase: StudentPhase) => void };

export function StudentOverview({ phases, onSelect }: Props) {
  const implemented = phases.filter((phase) => phase.status === "Implemented").length;
  return <section className="student-overview" aria-labelledby="student-overview-heading"><header className="student-overview__hero"><p className="student-overview__eyebrow">Student workspace</p><h1 id="student-overview-heading">Your FYP workspace</h1><p>Use the collaboration, supervisor-request, and archive tools currently available to your account.</p></header><div className="student-overview__summary" aria-label="Student workspace summary"><div><strong>{phases.length}</strong><span>available areas</span></div><div><strong>{implemented}</strong><span>fully implemented</span></div><div><strong>{phases.length - implemented}</strong><span>partial areas</span></div></div><div className="student-overview__heading"><div><h2>Available student features</h2><p>Each area below is backed by an existing component and authorized API.</p></div></div><div className="student-overview__grid">{phases.map((phase) => <button key={phase.id} type="button" className="student-phase-card" onClick={() => onSelect(phase)} data-route={phase.route}><span className="student-phase-card__top"><span className="student-phase-card__icon" aria-hidden="true">{phase.icon}</span><span className={`student-status student-status--${phase.status === "Implemented" ? "implemented" : "partial"}`}>{phase.status}</span></span><strong>{phase.name}</strong><span className="student-phase-card__open">Open feature <span aria-hidden="true">→</span></span></button>)}</div></section>;
}

export function StudentOverviewWithDocuments(props: Props) {
  return <><StudentOverview {...props} /><StudentRequiredDocumentsDashboard api={API} /></>;
}
