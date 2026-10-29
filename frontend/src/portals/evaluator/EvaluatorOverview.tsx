type FeatureKey = "queue" | "proposal" | "schedule" | "criteria" | "scoring" | "history";
type EvaluatorOverviewProps = { onSelect: (key: FeatureKey) => void };

const cards: Array<{ key: FeatureKey; title: string; summary: string; status: string }> = [
  { key: "queue", title: "Evaluation Queue", summary: "Assigned evaluation work will appear here when the evaluator assignment service is available.", status: "Unavailable" },
  { key: "proposal", title: "Proposal Review", summary: "Authorized proposal documents will be shown here only after a review assignment exists.", status: "Unavailable" },
  { key: "schedule", title: "Defense Schedule", summary: "No defense schedule is exposed until the scheduling workflow is implemented.", status: "Unavailable" },
  { key: "criteria", title: "Evaluation Criteria", summary: "Evaluation criteria remain managed by Administrator configuration and are not fabricated here.", status: "Unavailable" },
  { key: "scoring", title: "Scoring & Feedback", summary: "Scoring and feedback submission is unavailable until its authorized API is implemented.", status: "Unavailable" },
  { key: "history", title: "Decision History", summary: "Submitted evaluations and decisions will appear here when persisted evaluator records exist.", status: "Unavailable" },
];

export function EvaluatorOverview({ onSelect }: EvaluatorOverviewProps) {
  return (
    <section className="student-overview evaluator-overview" aria-labelledby="evaluator-overview-heading">
      <header className="student-overview__hero">
        <p className="student-overview__eyebrow">Evaluator workspace</p>
        <h1 id="evaluator-overview-heading">Evaluation workspace</h1>
        <p>Review assigned project work, configured criteria, and evaluation history when the corresponding authorized workflows are available.</p>
      </header>
      <div className="student-overview__summary" aria-label="Evaluator workspace summary">
        <div><strong>0</strong><span>assigned evaluations</span></div>
        <div><strong>0</strong><span>pending actions</span></div>
        <div><strong>—</strong><span>submitted results</span></div>
      </div>
      <div className="student-overview__heading"><div><h2>Evaluator features</h2><p>Only authorized, implemented evaluator data will be displayed.</p></div></div>
      <div className="student-overview__grid">
        {cards.map((card) => (
          <button key={card.key} type="button" className="student-phase-card evaluator-feature-card" onClick={() => onSelect(card.key)}>
            <span className="student-phase-card__top"><span className="student-phase-card__icon" aria-hidden="true">•</span><span className="student-status student-status--future">{card.status}</span></span>
            <strong>{card.title}</strong>
            <span className="evaluator-feature-card__summary">{card.summary}</span>
            <span className="student-phase-card__open">Open feature <span aria-hidden="true">→</span></span>
          </button>
        ))}
      </div>
    </section>
  );
}
