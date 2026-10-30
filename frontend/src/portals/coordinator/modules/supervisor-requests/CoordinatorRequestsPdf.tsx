import { useEffect, useMemo, useState } from "react";
import { RequestConversation } from "./RequestConversation";
import { PanelScheduling } from "./PanelScheduling";

type Field = { display: string; source: string | null };
type RequestRecord = {
  id: number;
  academic_cycle_id: number;
  requester_name: string;
  team_id: number | null;
  academic_cycle_name: string;
  supervisor_name: string;
  supervisor_id: number;
  submission_note: string | null;
  status: string;
  created_at: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  updated_at: string;
  capacity_used: number;
  capacity_limit: number | null;
  capacity_remaining: number | null;
  capacity_warning: boolean;
  document: { filename: string; document_url: string; extraction_status: string; extraction_runtime: string; extracted_fields: Record<string, Field | Field[] | string[]> } | null;
  status_history: { id: number; to_status: string; actor_name: string; comment: string | null; created_at: string }[];
};

const field = (row: RequestRecord, name: string): Field => {
  const value = row.document?.extracted_fields?.[name];
  return !Array.isArray(value) && typeof value === "object" && value ? value as Field : { display: "Not detected in PDF", source: null };
};

export function CoordinatorRequestsPdf({ api }: { api: string }) {
  const [rows, setRows] = useState<RequestRecord[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [cycleFilter, setCycleFilter] = useState("");
  const [supervisorFilter, setSupervisorFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [selected, setSelected] = useState<RequestRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [showScheduling, setShowScheduling] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      setLoading(true);
      try {
        const query = new URLSearchParams();
        if (cycleFilter) query.set("academic_cycle_id", cycleFilter);
        if (supervisorFilter) query.set("supervisor_id", supervisorFilter);
        if (statusFilter) query.set("status", statusFilter);
        if (fromDate) query.set("from_date", new Date(`${fromDate}T00:00:00Z`).toISOString());
        if (toDate) query.set("to_date", new Date(`${toDate}T23:59:59Z`).toISOString());
        const suffix = query.toString() ? `?${query}` : "";
        const response = await fetch(`${api}/api/v1/supervisor-requests/coordinator/monitor${suffix}`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error();
        setRows(await response.json() as RequestRecord[]);
        setMessage("");
      } catch {
        if (!controller.signal.aborted) setMessage("Supervisor monitoring data could not be loaded.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [api, cycleFilter, supervisorFilter, statusFilter, fromDate, toDate]);
  const cycles = useMemo(() => Array.from(new Map(rows.map((row) => [row.academic_cycle_id ?? row.academic_cycle_name, row.academic_cycle_name])).entries()), [rows]);
  const supervisors = useMemo(() => Array.from(new Map(rows.map((row) => [row.supervisor_id ?? row.supervisor_name, row.supervisor_name])).entries()), [rows]);
  const counts = useMemo(() => rows.reduce<Record<string, number>>((result, row) => { result[row.status] = (result[row.status] ?? 0) + 1; return result; }, {}), [rows]);
  const clearFilters = () => { setCycleFilter(""); setSupervisorFilter(""); setStatusFilter(""); setFromDate(""); setToDate(""); };
  if (showScheduling) return <section className="supervisor-page"><button type="button" className="supervisor-filter-clear" onClick={() => setShowScheduling(false)}>Back to monitoring</button><PanelScheduling api={api} /></section>;
  return <section className="supervisor-page" aria-labelledby="coordinator-requests-heading">
    <div className="supervisor-page-heading"><p>Coordinator / PM workspace</p><h1 id="coordinator-requests-heading">Supervisor Request Monitoring</h1><span>Read-only monitoring for authorized cycles. Supervisor decisions remain with the selected supervisor.</span><button type="button" className="supervisor-filter-clear" onClick={() => setShowScheduling(true)}>Open Panel Scheduling</button></div>
    {message && <p className="supervisor-alert" role="alert">{message}</p>}
    <div className="supervisor-monitor-summary"><span><strong>{counts.DRAFT ?? 0}</strong> pending drafts</span><span><strong>{counts.SUBMITTED ?? 0}</strong> submitted</span><span><strong>{counts.CHANGES_REQUESTED ?? 0}</strong> changes requested</span><span><strong>{counts.ACCEPTED ?? 0}</strong> accepted</span><span><strong>{counts.REJECTED ?? 0}</strong> rejected</span></div>
    <div className="supervisor-card">
      <div className="supervisor-monitor-filters">
        <label className="supervisor-filter">Cycle<select value={cycleFilter} onChange={(event) => setCycleFilter(event.target.value)}><option value="">All cycles</option>{cycles.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label className="supervisor-filter">Supervisor<select value={supervisorFilter} onChange={(event) => setSupervisorFilter(event.target.value)}><option value="">All supervisors</option>{supervisors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label className="supervisor-filter">Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All statuses</option><option value="DRAFT">Pending drafts</option><option value="SUBMITTED">Submitted</option><option value="CHANGES_REQUESTED">Changes requested</option><option value="ACCEPTED">Accepted</option><option value="REJECTED">Rejected</option><option value="WITHDRAWN">Withdrawn</option></select></label>
        <label className="supervisor-filter">From<input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label>
        <label className="supervisor-filter">To<input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label>
        <button type="button" className="supervisor-filter-clear" onClick={clearFilters}>Clear filters</button>
      </div>
      {loading ? <p className="supervisor-empty">Loading monitoring data…</p> : !rows.length ? <p className="supervisor-empty">No supervisor requests match these filters.</p> : <div className="supervisor-monitor-table"><table><thead><tr><th>Proposal</th><th>Student / team</th><th>Supervisor</th><th>Cycle</th><th>Status</th><th>Capacity</th><th>Updated</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><button type="button" className="coordinator-document-button" onClick={() => setSelected(row)}>{field(row, "title").display}</button></td><td>{row.requester_name}{row.team_id ? ` · Team ${row.team_id}` : ""}</td><td>{row.supervisor_name}</td><td>{row.academic_cycle_name}</td><td><span>{row.status}</span></td><td><span className={row.capacity_warning ? "supervisor-capacity-warning" : ""}>{row.capacity_used}{row.capacity_limit !== null ? ` / ${row.capacity_limit}` : ""}</span></td><td>{new Date(row.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
      {selected && <article className="supervisor-card supervisor-detail"><div className="supervisor-detail-top"><div><h2>{field(selected, "title").display}</h2><p>{selected.requester_name} · {selected.supervisor_name} · {selected.academic_cycle_name}</p></div><button type="button" className="coordinator-document-button" onClick={() => setSelected(null)}>Close details</button></div>{selected.document && <a className="supervisor-document-link" href={`${api}${selected.document.document_url}`} target="_blank" rel="noreferrer">Open original PDF: {selected.document.filename}</a>}{selected.submission_note && <div className="supervisor-submission-note"><strong>Student submission note</strong><p>{selected.submission_note}</p></div>}<div className="supervisor-extracted-grid">{[["Topic / area", "topic"], ["Purpose", "purpose"], ["Objectives", "objectives"], ["Methodology", "methodology"]].map(([label, name]) => <div key={name}><strong>{label}</strong><span>{field(selected, name).display}</span>{field(selected, name).source && <small>Source: {field(selected, name).source}</small>}</div>)}</div><p className="supervisor-capacity">Extraction: {selected.document?.extraction_status ?? "PENDING"} via {selected.document?.extraction_runtime ?? "not available"}. Capacity: {selected.capacity_used}{selected.capacity_limit !== null ? ` / ${selected.capacity_limit}` : ""}{selected.capacity_warning ? " · At capacity" : ""}.</p><div className="supervisor-history">{selected.status_history.map((entry) => <div key={entry.id}><strong>{entry.to_status}</strong><small>{entry.actor_name} · {new Date(entry.created_at).toLocaleString()}</small>{entry.comment && <q>{entry.comment}</q>}</div>)}</div><RequestConversation api={api} requestId={selected.id} readOnly /></article>}
    </div>
  </section>;
}
