import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { IconButton } from "./ui/IconButton";
import { compareCyclesDesc, groupDisplayLabel } from "./lib/displayLabels";

type Supervisor = { id: number; name: string; email: string; is_active: boolean; active_groups: number; departure: { reason: string; notes?: string | null } | null };
type Member = { id?: number; name: string; email?: string; registration_number?: string; designation?: string; is_active?: boolean };
type GroupDetail = { id: number; name: string; group_number?: number | null; status: string; supervision_status: string; academic_cycle_id: number; academic_cycle?: string | null; academic_cycle_code?: string | null; academic_year?: number | null; session?: string | null; created_at?: string | null; updated_at?: string | null; members: Member[] };
type CaseSummary = { id: number; status: string; reason: string; opened_at: string; project_title?: string | null; group?: GroupDetail | null; previous_supervisor?: { id: number; name: string } | null };
type ProjectDetail = { title: string; submission_id: number; version: number; status: string; filename: string; uploaded_at: string; extracted_fields: Record<string, unknown> };
type Detail = CaseSummary & { notes?: string | null; project?: ProjectDetail | null; previous_supervisor?: { id: number; name: string; email: string }; replacement_supervisor?: { id: number; name: string; email: string } | null; reassigned_at?: string | null; completed_at?: string | null; progress: { health: string; average_completion_percent: number; overdue_items: number; milestones: Array<{ id?: number; title: string; completion_percent: number; due_at?: string | null }>; tasks: Array<{ id?: number; title: string; completion_percent: number; due_at?: string | null }> }; assignment_history: Array<{ id: number; supervisor_id: number; assigned_by_id: number; started_at: string; ended_at?: string | null; end_reason?: string | null; end_notes?: string | null }> };
type Recommendation = { rank: number; supervisor_id: number; supervisor_name: string; final_score: number; ai_score?: number; deterministic_score?: number; score_components: Record<string, number>; explanation: { reasons: string[]; gaps: string[]; related_projects: Array<{ title: string; year?: number | null }>; ai_rationale?: string; ranking_method?: string }; workload: { active_groups: number; capacity_limit: number | null; remaining_capacity: number | null } };

const reasons = [
  { value: "LEFT_UNIVERSITY", label: "Left university" },
  { value: "RESIGNED", label: "Resigned" },
  { value: "UNAVAILABLE", label: "Unavailable" },
  { value: "REMOVED", label: "Removed" },
  { value: "LONG_TERM_LEAVE", label: "Long-term leave" },
];

async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail?.message || data?.detail || "The request could not be completed.");
  return data as T;
}

const statusClass = (status: string) => status === "UNSUPERVISED" ? "bg-amber-100 text-amber-800" : status === "REPLACEMENT_PENDING" ? "bg-blue-100 text-blue-800" : status === "REASSIGNED" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700";
const formatStatus = (value?: string | null) => value ? value.replaceAll("_", " ") : "Not available";
const dateTime = (value?: string | null) => value ? new Date(value).toLocaleString() : "Not available";
const displayValue = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "Not detected";
  if (Array.isArray(value)) return value.length ? value.map(displayValue).filter((item) => item !== "Not detected").join(", ") || "Not detected" : "Not detected";
  if (typeof value === "object") {
    const field = value as Record<string, unknown>;
    const readable = [field.display, field.value, field.text, field.content].find((item) => typeof item === "string" && item.trim());
    if (typeof readable === "string") return readable.trim();
    return Object.values(field).map(displayValue).filter((item) => item !== "Not detected").join(", ") || "Not detected";
  }
  return String(value);
};
const fieldLabel = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export function AdminSupervisorReplacement({ api }: { api: string }) {
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedSupervisorId, setSelectedSupervisorId] = useState("");
  const [reason, setReason] = useState("UNAVAILABLE");
  const [departureNotes, setDepartureNotes] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [rankingMethod, setRankingMethod] = useState("");
  const [replacementId, setReplacementId] = useState("");
  const [replacementNotes, setReplacementNotes] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextSupervisors, nextCases] = await Promise.all([
        read<Supervisor[]>(await fetch(`${api}/api/v1/admin/supervisor-replacements/supervisors`, { credentials: "include" })),
        read<CaseSummary[]>(await fetch(`${api}/api/v1/admin/supervisor-replacements/cases`, { credentials: "include" })),
      ]);
      setSupervisors(nextSupervisors);
      setCases(nextCases.filter((item) => item.status !== "COMPLETED"));
    } catch (value) {
      setError(value instanceof Error ? value.message : "Replacement data could not be loaded.");
    }
  }, [api]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const selectedSupervisor = useMemo(() => supervisors.find((item) => String(item.id) === selectedSupervisorId), [selectedSupervisorId, supervisors]);
  const availableChoices = supervisors.filter((item) => item.is_active && !item.departure);
  const orderedCases = useMemo(() => [...cases].sort((left, right) => {
    const cycleOrder = compareCyclesDesc(
      { id: left.group?.academic_cycle_id, display_name: left.group?.academic_cycle, academic_year: left.group?.academic_year, session: left.group?.session },
      { id: right.group?.academic_cycle_id, display_name: right.group?.academic_cycle, academic_year: right.group?.academic_year, session: right.group?.session },
    );
    return cycleOrder || new Date(right.opened_at).getTime() - new Date(left.opened_at).getTime() || right.id - left.id;
  }), [cases]);

  const markUnavailable = async () => {
    if (!selectedSupervisorId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await read<{ affected_groups: CaseSummary[] }>(await fetch(`${api}/api/v1/admin/supervisor-replacements/supervisors/${selectedSupervisorId}/mark-unavailable`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ reason, notes: departureNotes || null }) }));
      setMessage(`${result.affected_groups.length} group(s) moved to the unsupervised queue.`);
      setDepartureNotes("");
      await load();
    } catch (value) {
      setError(value instanceof Error ? value.message : "The supervisor could not be marked unavailable.");
    } finally { setBusy(false); }
  };

  const restoreSupervisor = async () => {
    if (!selectedSupervisorId || !selectedSupervisor?.departure) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await read<{ message: string }>(await fetch(`${api}/api/v1/admin/supervisor-replacements/supervisors/${selectedSupervisorId}/restore`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ notes: departureNotes || null }) }));
      setMessage(result.message);
      setDepartureNotes("");
      await load();
    } catch (value) {
      setError(value instanceof Error ? value.message : "The supervisor could not be restored.");
    } finally { setBusy(false); }
  };

  const openCase = async (id: number) => {
    setSelectedCaseId(id); setRecommendations([]); setReplacementId(""); setError("");
    try {
      setDetail(await read<Detail>(await fetch(`${api}/api/v1/admin/supervisor-replacements/cases/${id}`, { credentials: "include" })));
    } catch (value) {
      setError(value instanceof Error ? value.message : "The replacement case could not be loaded.");
    }
  };

  const recommend = async () => {
    if (!selectedCaseId) return;
    setBusy(true); setError("");
    try {
      const result = await read<{ results: Recommendation[]; ranking_method?: string }>(await fetch(`${api}/api/v1/admin/supervisor-replacements/cases/${selectedCaseId}/recommendations`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }));
      setRecommendations(result.results);
      setRankingMethod(result.ranking_method || "");
      setMessage("Replacement recommendations calculated from the group proposal, history, profile evidence, and capacity.");
    } catch (value) {
      setError(value instanceof Error ? value.message : "Replacement recommendations could not be calculated.");
    } finally { setBusy(false); }
  };

  const reassign = async () => {
    if (!selectedCaseId || !replacementId) return;
    setBusy(true); setError("");
    try {
      await read(await fetch(`${api}/api/v1/admin/supervisor-replacements/cases/${selectedCaseId}/reassign`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ supervisor_id: Number(replacementId), notes: replacementNotes || null }) }));
      setMessage("Supervisor reassigned. The student group, previous supervisor, and new supervisor were notified.");
      setReplacementNotes("");
      await load();
      await openCase(selectedCaseId);
    } catch (value) {
      setError(value instanceof Error ? value.message : "The supervisor could not be reassigned.");
    } finally { setBusy(false); }
  };

  const complete = async () => {
    if (!selectedCaseId) return;
    setBusy(true); setError("");
    try {
      await read(await fetch(`${api}/api/v1/admin/supervisor-replacements/cases/${selectedCaseId}/complete`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({}) }));
      setMessage("Replacement case marked completed.");
      await load();
      setSelectedCaseId(null);
      setDetail(null);
      setRecommendations([]);
      setReplacementId("");
      setRankingMethod("");
    } catch (value) {
      setError(value instanceof Error ? value.message : "The case could not be completed.");
    } finally { setBusy(false); }
  };

  return <section aria-labelledby="replacement-heading" className="admin-replacement-page grid gap-5">
    <div><p className="text-sm font-semibold uppercase tracking-wide text-fy-brand">Supervisor continuity</p><h1 id="replacement-heading" className="text-2xl font-bold tracking-tight">Supervisor Replacement / Reallocation</h1><p className="mt-1 max-w-3xl text-sm text-fy-text-secondary">Move affected groups into an auditable replacement workflow without asking students to submit a new request.</p></div>
    {message && <p role="status" className="rounded-lg bg-fy-success-soft px-3 py-2 text-sm text-fy-success">{message}</p>}{error && <p role="alert" className="rounded-lg bg-fy-danger-soft px-3 py-2 text-sm text-fy-danger">{error}</p>}
    <div className="grid gap-5 xl:grid-cols-[minmax(0,.8fr)_minmax(0,1.2fr)]">
      <article className="rounded-xl border border-fy-border bg-fy-surface p-5 shadow-sm">
        <h2 className="text-lg font-bold">Supervisor availability</h2>
        <p className="mt-1 text-sm text-fy-text-secondary">Mark a supervisor unavailable, or restore an accidental departure before assigning affected groups back to them.</p>
        <div className="mt-4 grid gap-3">
          <label className="grid gap-1 text-sm font-semibold">Supervisor<select className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2" value={selectedSupervisorId} onChange={(event) => setSelectedSupervisorId(event.target.value)}><option value="">Choose supervisor</option>{supervisors.map((item) => <option key={item.id} value={item.id}>{item.name} - {item.active_groups} active group(s){item.departure ? ` - ${item.departure.reason.replaceAll("_", " ")}` : ""}</option>)}</select></label>
          {selectedSupervisor?.departure && <p className="rounded-lg bg-fy-warning-soft px-3 py-2 text-sm text-fy-warning">Currently marked {formatStatus(selectedSupervisor.departure.reason)}. Restore this supervisor to make them available for reassignment.</p>}
          <label className="grid gap-1 text-sm font-semibold">Reason<select className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2" value={reason} onChange={(event) => setReason(event.target.value)}>{reasons.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label className="grid gap-1 text-sm font-semibold">Admin notes<textarea rows={3} maxLength={2000} value={departureNotes} onChange={(event) => setDepartureNotes(event.target.value)} placeholder="Optional context for the audit history" /></label>
          <button type="button" disabled={busy || !selectedSupervisorId} onClick={() => void (selectedSupervisor?.departure ? restoreSupervisor() : markUnavailable())} className="rounded-lg bg-fy-brand px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Saving..." : selectedSupervisor?.departure ? "Restore supervisor" : "Mark and create replacement cases"}</button>
        </div>
      </article>
      <article className="rounded-xl border border-fy-border bg-fy-surface p-5 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">Replacement queue</h2><p className="mt-1 text-sm text-fy-text-secondary">Select a group to inspect its academic cycle, project, members, progress, history, and replacement options.</p></div><IconButton label="Refresh replacement queue" size="sm" variant="secondary" onClick={() => void load()}><RefreshCw size={15} strokeWidth={1.8} aria-hidden /></IconButton></div>{!orderedCases.length ? <p className="mt-5 rounded-lg border border-dashed border-fy-border p-4 text-sm text-fy-text-secondary">No supervisor replacement cases are open.</p> : <div className="mt-4 grid gap-2">{orderedCases.map((item) => <button type="button" key={item.id} onClick={() => void openCase(item.id)} className={`rounded-lg border p-3 text-left ${selectedCaseId === item.id ? "border-fy-brand bg-fy-surface-muted text-fy-text" : "border-fy-border bg-fy-surface text-fy-text"}`}><div className="flex items-start justify-between gap-3"><span className="min-w-0"><strong className="block text-sm">{groupDisplayLabel(item.group, item.group?.academic_cycle)}</strong><small className={selectedCaseId === item.id ? "text-fy-text" : "text-fy-text-secondary"}>{item.group?.academic_cycle || "Cycle unavailable"} · {item.group?.members.length || 0} member(s) · {item.project_title || "Proposal not uploaded"}</small><small className={`mt-1 block ${selectedCaseId === item.id ? "text-fy-text" : "text-fy-text-secondary"}`}>Previous supervisor: {item.previous_supervisor?.name || "Unknown"}</small></span><span className={`rounded-full px-2 py-1 text-[11px] font-bold ${statusClass(item.status)}`}>{formatStatus(item.status)}</span></div></button>)}</div>}</article>
    </div>
    {detail && <article className="rounded-xl border border-fy-border bg-fy-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Replacement case #{detail.id}</p><h2 className="mt-1 text-xl font-bold">{groupDisplayLabel(detail.group, detail.group?.academic_cycle)}</h2><p className="mt-1 text-sm text-fy-text-secondary">{detail.group?.academic_cycle || "Cycle unavailable"} · Opened {dateTime(detail.opened_at)}</p></div><span className={`rounded-full px-3 py-1.5 text-xs font-bold ${statusClass(detail.status)}`}>{formatStatus(detail.status)}</span></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg bg-fy-surface-muted p-3"><p className="text-xs font-bold uppercase text-fy-text-secondary">Group status</p><p className="mt-1 font-semibold">{formatStatus(detail.group?.status)}</p><p className="mt-1 text-xs text-fy-text-secondary">Supervision: {formatStatus(detail.group?.supervision_status)}</p></div>
        <div className="rounded-lg bg-fy-surface-muted p-3"><p className="text-xs font-bold uppercase text-fy-text-secondary">Members</p><p className="mt-1 font-semibold">{detail.group?.members.length || 0}</p><p className="mt-1 text-xs text-fy-text-secondary">{detail.progress.overdue_items} overdue progress item(s)</p></div>
        <div className="rounded-lg bg-fy-surface-muted p-3"><p className="text-xs font-bold uppercase text-fy-text-secondary">Progress</p><p className="mt-1 font-semibold">{detail.progress.average_completion_percent}% - {detail.progress.health}</p></div>
        <div className="rounded-lg bg-fy-surface-muted p-3"><p className="text-xs font-bold uppercase text-fy-text-secondary">Proposal</p><p className="mt-1 font-semibold">{detail.project?.filename || "Not uploaded"}</p><p className="mt-1 text-xs text-fy-text-secondary">{detail.project ? `v${detail.project.version} · ${formatStatus(detail.project.status)}` : "No submission"}</p></div>
        <div className="rounded-lg bg-fy-surface-muted p-3"><p className="text-xs font-bold uppercase text-fy-text-secondary">Previous supervisor</p><p className="mt-1 font-semibold">{detail.previous_supervisor?.name || "Unknown"}</p><p className="mt-1 text-xs text-fy-text-secondary">{detail.previous_supervisor?.email || "Email unavailable"}</p></div>
        <div className="rounded-lg bg-fy-surface-muted p-3"><p className="text-xs font-bold uppercase text-fy-text-secondary">Assignment history</p><p className="mt-1 font-semibold">{detail.assignment_history.length} record(s)</p><p className="mt-1 text-xs text-fy-text-secondary">{detail.replacement_supervisor ? `Current: ${detail.replacement_supervisor.name}` : "Awaiting replacement"}</p></div>
      </div>
      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,.85fr)]">
        <div className="grid gap-5">
          <section><h3 className="font-bold">Group members</h3><div className="mt-2 overflow-x-auto rounded-lg border border-fy-border"><table className="w-full min-w-[620px] text-left text-sm"><thead className="bg-fy-surface-muted text-xs uppercase tracking-wide text-fy-text-secondary"><tr><th className="px-3 py-2">Name</th><th className="px-3 py-2">Role</th><th className="px-3 py-2">Registration number</th><th className="px-3 py-2">Email</th><th className="px-3 py-2">Status</th></tr></thead><tbody className="divide-y divide-fy-border">{detail.group?.members.map((member) => <tr key={member.id || `${member.name}-${member.email}`}><td className="px-3 py-2 font-semibold">{member.name}</td><td className="px-3 py-2">{member.designation || "Member"}</td><td className="px-3 py-2">{member.registration_number || "Not available"}</td><td className="px-3 py-2">{member.email || "Not available"}</td><td className="px-3 py-2">{member.is_active === false ? "Inactive" : "Active"}</td></tr>)}</tbody></table></div></section>
          <section><h3 className="font-bold">Project and proposal details</h3>{detail.project ? <div className="mt-2 grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-fy-border p-3"><p className="text-xs font-semibold tracking-[0.08em] text-fy-text-secondary">Title</p><p className="mt-1 font-semibold">{detail.project.title || "Untitled project"}</p></div><div className="rounded-lg border border-fy-border p-3"><p className="text-xs font-semibold tracking-[0.08em] text-fy-text-secondary">Submission</p><p className="mt-1 font-semibold">#{detail.project.submission_id} · version {detail.project.version}</p><p className="mt-1 text-xs text-fy-text-secondary">Uploaded {dateTime(detail.project.uploaded_at)}</p></div>{Object.entries(detail.project.extracted_fields || {}).filter(([, value]) => value !== null && value !== undefined && value !== "" && (!Array.isArray(value) || value.length > 0)).slice(0, 8).map(([key, value]) => <div key={key} className="rounded-lg border border-fy-border p-3"><p className="text-xs font-semibold tracking-[0.08em] text-fy-text-secondary">{fieldLabel(key)}</p><p className="mt-1 whitespace-pre-wrap text-sm leading-6">{displayValue(value)}</p></div>)}</div> : <p className="mt-2 rounded-lg border border-dashed border-fy-border p-3 text-sm text-fy-text-secondary">No proposal submission has been uploaded for this group.</p>}</section>
          <section><h3 className="font-bold">Progress snapshot</h3><p className="mt-2 text-sm text-fy-text-secondary">{detail.progress.overdue_items} overdue item(s). {detail.progress.milestones.length} milestone(s) and {detail.progress.tasks.length} task(s) are recorded.</p><div className="mt-3 grid gap-2 sm:grid-cols-2">{[...detail.progress.milestones.map((item) => ({ ...item, kind: "Milestone" })), ...detail.progress.tasks.map((item) => ({ ...item, kind: "Task" }))].slice(0, 8).map((item, index) => <div key={`${item.kind}-${item.id || index}`} className="rounded-lg border border-fy-border p-3 text-sm"><div className="flex items-start justify-between gap-2"><span><strong>{item.title}</strong><small className="ml-2 text-fy-text-secondary">{item.kind}</small></span><b>{item.completion_percent}%</b></div>{item.due_at && <small className="mt-1 block text-fy-text-secondary">Due {dateTime(item.due_at)}</small>}</div>)}</div></section>
        </div>
        <div className="grid content-start gap-5">
          <section><h3 className="font-bold">Assignment history</h3>{detail.assignment_history.length ? <div className="mt-2 grid gap-2">{detail.assignment_history.map((assignment) => <div key={assignment.id} className="rounded-lg border border-fy-border p-3 text-sm"><div className="flex items-start justify-between gap-2"><strong>Supervisor ID {assignment.supervisor_id}</strong><span className="text-xs text-fy-text-secondary">#{assignment.id}</span></div><p className="mt-1 text-fy-text-secondary">Started {dateTime(assignment.started_at)}</p><p className="text-fy-text-secondary">{assignment.ended_at ? `Ended ${dateTime(assignment.ended_at)}` : "Current assignment"}</p>{assignment.end_reason && <p className="mt-1">Reason: {formatStatus(assignment.end_reason)}</p>}{assignment.end_notes && <p className="mt-1 whitespace-pre-wrap text-fy-text-secondary">{assignment.end_notes}</p>}</div>)}</div> : <p className="mt-2 rounded-lg border border-dashed border-fy-border p-3 text-sm text-fy-text-secondary">No assignment history available.</p>}</section>
          <section><div className="flex items-center justify-between gap-3"><h3 className="font-bold">Recommended replacement supervisors</h3>{recommendations.length > 0 && <span className="text-xs font-semibold text-fy-text-secondary">{rankingMethod === "llama3.1-assisted" ? "Llama 3.1 assisted · eligibility checked" : "Deterministic fallback"}</span>}</div><button type="button" disabled={busy || detail.status === "REASSIGNED" || detail.status === "COMPLETED"} onClick={() => void recommend()} className="mt-2 rounded-lg bg-fy-brand px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Working..." : "Calculate recommendations"}</button>{recommendations.length > 0 && <div className="mt-3 grid gap-2">{recommendations.map((item) => <button type="button" key={item.supervisor_id} onClick={() => setReplacementId(String(item.supervisor_id))} className={`rounded-lg border p-3 text-left ${replacementId === String(item.supervisor_id) ? "border-fy-brand bg-fy-surface-muted text-fy-text" : "border-fy-border bg-fy-surface text-fy-text"}`}><div className="flex items-start justify-between gap-2"><span><strong className="block text-sm">#{item.rank} - {item.supervisor_name}</strong><small className="text-fy-text-secondary">{item.workload.active_groups} active - {item.workload.remaining_capacity ?? "capacity not configured"} remaining</small></span><b className="text-fy-brand">{item.final_score.toFixed(1)}</b></div><small className="mt-1 block text-fy-text-secondary">{item.explanation.ai_rationale || item.explanation.reasons[0]}</small></button>)}</div>}<label className="mt-3 grid gap-1 text-sm font-semibold">Manual supervisor selection<select className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2" value={replacementId} onChange={(event) => setReplacementId(event.target.value)}><option value="">Choose recommended, previous, or another active supervisor</option>{availableChoices.map((item) => <option key={item.id} value={item.id}>{item.name} - {item.active_groups} active group(s){item.id === detail.previous_supervisor?.id ? " - previous supervisor" : ""}</option>)}</select></label><label className="mt-3 grid gap-1 text-sm font-semibold">Reassignment notes<textarea rows={3} value={replacementNotes} onChange={(event) => setReplacementNotes(event.target.value)} placeholder="Optional handover notes" /></label><div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={busy || !replacementId || detail.status === "REASSIGNED" || detail.status === "COMPLETED"} onClick={() => void reassign()} className="rounded-lg bg-fy-brand px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Assign selected supervisor</button>{detail.status === "REASSIGNED" && <button type="button" disabled={busy} onClick={() => void complete()} className="rounded-lg border border-fy-brand px-3 py-2 text-sm font-semibold text-fy-brand disabled:opacity-50">Mark case completed</button>}</div></section>
          {detail.notes && <section><h3 className="font-bold">Case notes</h3><p className="mt-2 whitespace-pre-wrap rounded-lg border border-fy-border p-3 text-sm text-fy-text-secondary">{detail.notes}</p></section>}
        </div>
      </div>
    </article>}
  </section>;
}
