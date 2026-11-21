import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { PageHeader, StatCard, StatusBadge } from "../../ui";
import { IconButton } from "../../ui/IconButton";
import { AnnouncementSection } from "../../announcements/AnnouncementSection";

type History = { id: number; to_status: string; comment: string | null; actor_name: string; created_at: string };
type RequestRecord = { id: number; title: string | null; status: string; academic_cycle_name: string; requester_name: string; updated_at: string; status_history: History[] };
const statuses = ["SUBMITTED", "CHANGES_REQUESTED", "ACCEPTED", "REJECTED", "WITHDRAWN"];

export function SupervisorOverview({ api, onOpenRequest }: { api: string; onOpenRequest: (requestId?: number) => void }) {
  const [rows, setRows] = useState<RequestRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const responses = await Promise.all(statuses.map((status) => fetch(`${api}/api/v1/supervisor-requests/supervisor/queue?status=${status}`, { credentials: "include" })));
      if (responses.some((response) => !response.ok)) throw new Error();
      const data = (await Promise.all(responses.map((response) => response.json()))) as RequestRecord[][];
      setRows(data.flat().sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()));
    } catch {
      setError("Supervisor activity could not be loaded. Refresh to try again.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const counts = rows.reduce<Record<string, number>>((result, row) => { result[row.status] = (result[row.status] ?? 0) + 1; return result; }, {});
  const pending = rows.find((row) => row.status === "SUBMITTED" || row.status === "CHANGES_REQUESTED");
  const recent = rows.slice(0, 5);
  const statItems: Array<[string, number]> = [
    ["Total requests (including history)", rows.length],
    ["Pending", (counts.SUBMITTED ?? 0) + (counts.CHANGES_REQUESTED ?? 0)],
    ["Accepted", counts.ACCEPTED ?? 0],
    ["Changes requested", counts.CHANGES_REQUESTED ?? 0],
    ["Rejected", counts.REJECTED ?? 0],
    ["Withdrawn", counts.WITHDRAWN ?? 0],
  ];

  return (
    <section className="supervisor-page" aria-labelledby="supervisor-overview-heading">
      <PageHeader className="supervisor-page-heading" eyebrow="Supervisor workspace" title="Overview" description="Live request activity and decisions for your supervisor account." />
      <AnnouncementSection api={api} />
      {error && <div className="supervisor-alert" role="alert">{error} <IconButton label="Refresh supervisor activity" size="sm" variant="secondary" onClick={() => void load()}><RefreshCw size={15} strokeWidth={1.8} aria-hidden /></IconButton></div>}
      {loading ? <div className="supervisor-card supervisor-empty">Loading supervisor activity…</div> : !rows.length ? (
        <div className="supervisor-card supervisor-empty">
          <h2>No assigned request activity yet</h2>
          <p className="mt-2">New requests assigned to you will appear here after a student submits a proposal.</p>
          <IconButton label="Refresh supervisor activity" size="sm" variant="primary" className="mt-4" onClick={() => void load()}><RefreshCw size={15} strokeWidth={1.8} aria-hidden /></IconButton>
        </div>
      ) : (
        <>
          <div className="supervisor-overview-stats grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {statItems.map(([label, value]) => <StatCard key={label} label={label} value={value} />)}
          </div>
          <div className="supervisor-overview-grid">
            <div className="supervisor-card">
              <div className="flex items-center justify-between gap-3">
                <h2>Recent proposal activity</h2>
                <button type="button" className="fy-btn fy-btn--secondary fy-btn--sm" onClick={() => onOpenRequest()}>Open requests</button>
              </div>
              <div className="supervisor-overview-list">
                {recent.map((row) => (
                  <button type="button" key={row.id} onClick={() => onOpenRequest(row.id)}>
                    <span>
                      <strong>{row.title ?? "Proposal PDF"}</strong>
                      <small>{row.requester_name} · {row.academic_cycle_name}</small>
                    </span>
                    <StatusBadge status={row.status} />
                  </button>
                ))}
              </div>
            </div>
            <div className="supervisor-card">
              <h2>Latest pending request</h2>
              {pending ? (
                <button type="button" className="supervisor-latest-request" onClick={() => onOpenRequest(pending.id)}>
                  <strong>{pending.title ?? "Proposal PDF"}</strong>
                  <span className="flex flex-wrap items-center gap-2">{pending.requester_name} <StatusBadge status={pending.status} /></span>
                  <small>Updated {new Date(pending.updated_at).toLocaleString()}</small>
                </button>
              ) : (
                <p className="supervisor-empty">There are no submitted requests awaiting a decision. Withdrawn requests are history; student drafts are not sent yet.</p>
              )}
              <div className="supervisor-capacity-unavailable">
                <strong>Capacity</strong>
                <span>Capacity configuration is managed by Admin.</span>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
