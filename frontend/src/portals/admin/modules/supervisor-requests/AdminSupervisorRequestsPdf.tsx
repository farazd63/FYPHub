import { useEffect, useMemo, useState } from "react";
import { RequestConversation } from "./RequestConversation";

type Field = { display: string; source: string | null };
type RequestRecord = {
  id: number;
  academic_cycle_id: number;
  requester_name: string;
  team_id: number | null;
  academic_cycle_name: string;
  supervisor_id: number;
  supervisor_name: string;
  submission_note: string | null;
  status: string;
  updated_at: string;
  capacity_used: number;
  capacity_limit: number | null;
  capacity_remaining: number | null;
  capacity_warning: boolean;
  document: { filename: string; document_url: string; extraction_status: string; extraction_runtime: string; extracted_fields: Record<string, Field | Field[] | string[]> } | null;
  status_history: { id: number; to_status: string; actor_name: string; comment: string | null; created_at: string }[];
};
type Audit = { id: number; action: string; created_at: string };
const field = (row: RequestRecord, name: string): Field => { const value = row.document?.extracted_fields?.[name]; return !Array.isArray(value) && typeof value === "object" && value ? value as Field : { display: "Not detected in PDF", source: null }; };

export function AdminSupervisorRequestsPdf({ api }: { api: string }) {
  const [rows, setRows] = useState<RequestRecord[]>([]);
  const [selected, setSelected] = useState<RequestRecord | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [cycleFilter, setCycleFilter] = useState("");
  const [supervisorFilter, setSupervisorFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
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
        const response = await fetch(`${api}/api/v1/supervisor-requests/admin/monitor${suffix}`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error();
        setRows(await response.json() as RequestRecord[]);
        setMessage("");
      } catch {
        if (!controller.signal.aborted) setMessage("Supervisor request monitoring could not be loaded.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [api, cycleFilter, supervisorFilter, statusFilter, fromDate, toDate]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(`${api}/api/v1/admin/audit-events?target_type=SUPERVISOR_REQUEST&target_id=${selected.id}`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error();
        const body = await response.json() as { items: Audit[] };
        setAudit(body.items);
      } catch {
        if (!controller.signal.aborted) setAudit([]);
      }
    })();
    return () => controller.abort();
  }, [api, selected]);
  const cycles = useMemo(() => Array.from(new Map(rows.map((row) => [row.academic_cycle_id, row.academic_cycle_name])).entries()), [rows]);
  const supervisors = useMemo(() => Array.from(new Map(rows.map((row) => [row.supervisor_id, row.supervisor_name])).entries()), [rows]);
  const counts = useMemo(() => rows.reduce<Record<string, number>>((result, row) => { result[row.status] = (result[row.status] ?? 0) + 1; return result; }, {}), [rows]);
  const clearFilters = () => { setCycleFilter(""); setSupervisorFilter(""); setStatusFilter(""); setFromDate(""); setToDate(""); };
  return <section aria-labelledby="admin-supervisor-requests-heading"><div className="mb-5"><h1 id="admin-supervisor-requests-heading" className="text-2xl font-bold tracking-tight">Supervisor Requests</h1><p className="mt-1 text-sm text-[#60716b]">Read-only monitoring of authorized proposal PDFs, extracted content, lifecycle status, capacity impact, and audit history.</p></div>{message && <p role="alert" className="mb-4 rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">{message}</p>}<div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-6">{[["Pending", counts.DRAFT ?? 0], ["Submitted", counts.SUBMITTED ?? 0], ["Changes requested", counts.CHANGES_REQUESTED ?? 0], ["Accepted", counts.ACCEPTED ?? 0], ["Rejected", counts.REJECTED ?? 0], ["Withdrawn", counts.WITHDRAWN ?? 0]].map(([label, value]) => <div className="rounded-xl border border-[#dce4de] bg-white p-4 shadow-[0_2px_12px_rgba(36,55,70,0.035)]" key={label}><strong className="block text-2xl text-[#243746]">{value}</strong><span className="text-xs font-semibold text-[#60716b]">{label}</span></div>)}</div><div className="rounded-xl border border-[#dce4de] bg-white p-5 shadow-[0_2px_12px_rgba(36,55,70,0.035)]"><div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6"><label className="grid gap-1 text-sm font-semibold">Cycle<select className="w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm" value={cycleFilter} onChange={(event) => setCycleFilter(event.target.value)}><option value="">All cycles</option>{cycles.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Supervisor<select className="w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm" value={supervisorFilter} onChange={(event) => setSupervisorFilter(event.target.value)}><option value="">All supervisors</option>{supervisors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Status<select className="w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All statuses</option><option value="SUBMITTED">Submitted</option><option value="CHANGES_REQUESTED">Changes requested</option><option value="ACCEPTED">Accepted</option><option value="REJECTED">Rejected</option><option value="WITHDRAWN">Withdrawn</option></select></label><label className="grid gap-1 text-sm font-semibold">From<input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label><label className="grid gap-1 text-sm font-semibold">To<input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label><button type="button" className="self-end rounded-lg border border-[#b8cdc1] px-3 py-2.5 text-sm font-semibold text-[#176b66]" onClick={clearFilters}>Clear filters</button></div>{loading ? <p className="text-sm text-[#60716b]">Loading requests…</p> : !rows.length ? <p className="text-sm text-[#60716b]">No supervisor requests match these filters.</p> : <div className="overflow-x-auto rounded-lg border border-[#e8ede9]"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-[#fbfcfa] text-xs uppercase tracking-wide text-[#60716b]"><tr><th className="px-3 py-3">Proposal</th><th className="px-3 py-3">Student / team</th><th className="px-3 py-3">Supervisor</th><th className="px-3 py-3">Cycle</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Capacity</th><th className="px-3 py-3">Updated</th></tr></thead><tbody className="divide-y divide-[#e8ede9]">{rows.map((row) => <tr key={row.id}><td className="px-3 py-3"><button type="button" className="font-semibold text-[#176b66] underline" onClick={() => { setAudit([]); setSelected(row); }}>{field(row, "title").display}</button></td><td className="px-3 py-3">{row.requester_name}{row.team_id ? ` · Team ${row.team_id}` : ""}</td><td className="px-3 py-3">{row.supervisor_name}</td><td className="px-3 py-3">{row.academic_cycle_name}</td><td className="px-3 py-3">{row.status}</td><td className="px-3 py-3"><span className={row.capacity_warning ? "font-bold text-[#a43a33]" : ""}>{row.capacity_used}{row.capacity_limit !== null ? ` / ${row.capacity_limit}` : ""}</span></td><td className="px-3 py-3">{new Date(row.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div>}{selected && <article className="mt-5 rounded-lg border border-[#e8ede9] bg-[#fbfcfa] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">{field(selected, "title").display}</h2><p className="mt-1 text-sm text-[#60716b]">{selected.requester_name} · {selected.supervisor_name} · {selected.academic_cycle_name}</p></div><button type="button" className="text-sm font-semibold text-[#176b66] underline" onClick={() => setSelected(null)}>Close details</button></div>{selected.document && <a className="mt-3 inline-block text-sm font-semibold text-[#176b66] underline" href={`${api}${selected.document.document_url}`} target="_blank" rel="noreferrer">Open original PDF: {selected.document.filename}</a>}{selected.submission_note && <div className="mt-3 rounded-lg border border-[#e8ede9] bg-white p-3"><strong className="block text-sm">Student submission note</strong><p className="mt-1 whitespace-pre-wrap text-sm text-[#425a76]">{selected.submission_note}</p></div>}<div className="mt-4 grid gap-2 md:grid-cols-2">{[["Topic / area", "topic"], ["Purpose", "purpose"], ["Objectives", "objectives"], ["Methodology", "methodology"]].map(([label, name]) => <div className="rounded-lg border border-[#e8ede9] p-3" key={name}><strong className="block text-sm">{label}</strong><span className="mt-1 block text-sm text-[#425a76]">{field(selected, name).display}</span>{field(selected, name).source && <small className="text-xs text-[#60716b]">Source: {field(selected, name).source}</small>}</div>)}</div><p className="mt-3 text-xs text-[#60716b]">Extraction: {selected.document?.extraction_status ?? "PENDING"} via {selected.document?.extraction_runtime ?? "not available"}. Capacity: {selected.capacity_used}{selected.capacity_limit !== null ? ` / ${selected.capacity_limit}` : ""}{selected.capacity_warning ? " · At capacity" : ""}.</p><h3 className="mt-4 text-sm font-bold">Status history</h3><ul className="mt-2 grid gap-2 text-xs text-[#60716b]">{selected.status_history.map((entry) => <li key={entry.id}><strong className="text-[#243746]">{entry.to_status}</strong> · {entry.actor_name} · {new Date(entry.created_at).toLocaleString()}{entry.comment ? ` — ${entry.comment}` : ""}</li>)}</ul><h3 className="mt-4 text-sm font-bold">Audit trail</h3><ul className="mt-2 grid gap-2 text-xs text-[#60716b]">{audit.map((entry) => <li key={entry.id}><strong className="text-[#243746]">{entry.action}</strong> · {new Date(entry.created_at).toLocaleString()}</li>)}</ul><RequestConversation api={api} requestId={selected.id} readOnly /></article>}</div></section>;
}
