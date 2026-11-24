import { useEffect, useState } from "react";
import {
  CalendarDays,
  ClipboardList,
  FileSearch,
  History,
  ListChecks,
  MessageSquareText,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { FeatureChip, PageHeader } from "../../ui";
import { AnnouncementSection } from "../../announcements/AnnouncementSection";

type FeatureKey = "queue" | "proposal" | "schedule" | "criteria" | "scoring" | "history";
type EvaluatorOverviewProps = { api: string; onSelect: (key: FeatureKey) => void };
type Schedule = { id: number; status: string };
type Evaluation = { id: number; status: string };

const cards: Array<{ key: FeatureKey; title: string; status: string; icon: LucideIcon }> = [
  { key: "queue", title: "Evaluation Queue", status: "Available", icon: ClipboardList },
  { key: "proposal", title: "Proposal Review", status: "Available", icon: FileSearch },
  { key: "schedule", title: "Defense Schedule", status: "Available", icon: CalendarDays },
  { key: "criteria", title: "Evaluation Criteria", status: "Available", icon: ListChecks },
  { key: "scoring", title: "Scoring & Feedback", status: "Available", icon: MessageSquareText },
  { key: "history", title: "Decision History", status: "Available", icon: History },
];

export function EvaluatorOverview({ api, onSelect }: EvaluatorOverviewProps) {
  const [assigned, setAssigned] = useState(0);
  const [pending, setPending] = useState(0);
  const [submitted, setSubmitted] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(`${api}/api/v1/panel-schedules`, { credentials: "include", signal: controller.signal });
        if (!response.ok) return;
        const schedules = await response.json() as Schedule[];
        setAssigned(schedules.length);
        const active = schedules.filter((row) => !["COMPLETED", "CANCELLED"].includes(row.status));
        setPending(active.length);
        const evalCounts = await Promise.all(schedules.slice(0, 12).map(async (row) => {
          const evalResponse = await fetch(`${api}/api/v1/panel-evaluations/schedule/${row.id}`, { credentials: "include", signal: controller.signal });
          if (!evalResponse.ok) return 0;
          const rows = await evalResponse.json() as Evaluation[];
          return rows.filter((item) => item.status === "SUBMITTED").length;
        }));
        if (!controller.signal.aborted) setSubmitted(evalCounts.reduce((sum, n) => sum + n, 0));
      } catch {
        /* keep zeros on load failure */
      }
    })();
    return () => controller.abort();
  }, [api]);

  return (
    <section className="student-overview evaluator-overview" aria-labelledby="evaluator-overview-heading">
      <PageHeader
        className="student-overview__hero"
        title="Evaluation workspace"
      />
      <AnnouncementSection api={api} />
      <div className="student-overview__summary" aria-label="Evaluator workspace summary">
        <div><strong>{assigned}</strong><span>assigned evaluations</span></div>
        <div><strong>{pending}</strong><span>pending actions</span></div>
        <div><strong>{submitted || "—"}</strong><span>submitted results</span></div>
      </div>
      <div className="student-overview__heading"><h2>Evaluator features</h2></div>
      <div className="student-overview__grid">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <button key={card.key} type="button" className="student-phase-card evaluator-feature-card" onClick={() => onSelect(card.key)}>
              <span className="student-phase-card__top">
                <span className="student-phase-card__icon" aria-hidden="true"><Icon strokeWidth={1.75} size={18} /></span>
                <FeatureChip>{card.status}</FeatureChip>
              </span>
              <strong>{card.title}</strong>
              <span className="student-phase-card__open">Open feature <span aria-hidden="true">→</span></span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
