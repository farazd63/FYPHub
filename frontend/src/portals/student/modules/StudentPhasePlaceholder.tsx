import type { StudentPhase } from "../StudentSidebar";
import { ProposalLifecycleWorkspace } from "./ProposalLifecycleWorkspace";
import { StudentProgressDashboard } from "./StudentProgressDashboard";
import { AgentSupervisionPanel } from "./AgentSupervisionPanel";
export function StudentPhasePlaceholder({ phase, api }: { phase: StudentPhase; api?: string }) {
  if (phase.id === "proposal") return <><ProposalLifecycleWorkspace api={api ?? "http://localhost:8010"} /><AgentSupervisionPanel api={api ?? "http://localhost:8010"} /></>;
  if (phase.id === "progress") return <StudentProgressDashboard api={api ?? "http://localhost:8010"} />;
  const partial = phase.status === "Partial";
  const statusClass = phase.status === "Implemented" ? "implemented" : partial ? "partial" : "future";
  return <section className="student-phase-page" aria-labelledby={`${phase.id}-heading`}><div className="student-page-heading"><p className="student-overview__eyebrow">Student research phase</p><h1 id={`${phase.id}-heading`}>{phase.name}</h1><p>{partial ? "Some supporting foundation exists, but the student-facing workflow is not available yet." : "This phase is not available yet. No academic record or result has been created."}</p></div><div className="student-placeholder" data-future-route={phase.route}><span className="student-placeholder__icon" aria-hidden="true">{phase.icon}</span><div><span className={`student-status student-status--${statusClass}`}>{phase.status}</span><h2>{partial ? "Partial availability" : "Coming soon"}</h2><p>{partial ? "Student actions will appear here when the approved student workflow is implemented." : "Student actions for this proposal phase will appear here when its approved backend workflow is implemented."}</p></div></div></section>;
}
