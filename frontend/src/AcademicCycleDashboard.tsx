import { useCallback, useEffect, useState } from "react";
import { AdminCycleManager } from "./AdminCycleManager";
import "./AcademicCycleDashboard.css";

type Cycle = { id: number; code: string; display_name: string; registration_open: boolean; status?: string; start_date?: string | null; end_date?: string | null; supervisors_count?: number; projects_count?: number; groups_count?: number; students_count?: number };
type Summary = { supervisors: number; students: number; groups: number; projects: number; active_projects: number; completed_projects: number; pending_reviews: number; required_documents: number };
type Overview = { cycle: Cycle & { department?: string | null }; summary: Summary; supervisors: Array<Record<string, unknown>>; projects: Array<Record<string, unknown>>; groups: Array<Record<string, unknown>>; students: Array<Record<string, unknown>>; documents: Array<Record<string, unknown>> };
type Tab = "supervisors" | "projects" | "groups" | "students" | "documents";

const statusMessage = (status: number) => status === 401 ? "Your session has expired." : status === 403 ? "Coordinator or administrator permission is required." : status === 404 ? "Cycle details were not found." : status >= 500 ? "The academic cycle service returned an error." : "Academic cycle data could not be loaded.";
const display = (value: unknown, fallback = "Not available") => value === null || value === undefined || value === "" ? fallback : String(value);
const date = (value: unknown) => value ? new Date(String(value)).toLocaleDateString() : "Not recorded";
const readDetailId = (base: string) => { const prefix = `${base}/`; if (!window.location.pathname.startsWith(prefix)) return null; const value = Number(window.location.pathname.slice(prefix.length)); return Number.isInteger(value) && value > 0 ? value : null; };

export function AcademicCycleDashboard({ api, canManage = false, routeBase = "/admin/academic-cycles" }: { api: string; canManage?: boolean; routeBase?: string }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selected, setSelected] = useState<Overview | null>(null);
  const [detailId, setDetailId] = useState<number | null>(() => readDetailId(routeBase));
  const [tab, setTab] = useState<Tab>("supervisors");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");

  const loadCycles = useCallback(async () => {
    setLoading(true); setListError("");
    try {
      const response = await fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(statusMessage(response.status));
      setCycles(Array.isArray(body) ? body as Cycle[] : []);
    } catch (reason) {
      setListError(reason instanceof Error ? reason.message : "Academic cycle data could not be loaded.");
      setCycles([]);
    } finally { setLoading(false); }
  }, [api]);

  useEffect(() => { void Promise.resolve().then(loadCycles); }, [loadCycles]);

  useEffect(() => {
    const onPopState = () => { setDetailId(readDetailId(routeBase)); setSelected(null); setDetailError(""); };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [routeBase]);

  useEffect(() => {
    if (detailId === null) return;
    let cancelled = false;
    const loadDetail = async () => {
      setDetailLoading(true); setDetailError("");
      const detailPath = `/api/v1/academic-cycles/${detailId}/overview`;
      try {
        const response = await fetch(`${api}${detailPath}`, { credentials: "include" });
        if (import.meta.env.DEV) console.debug("Academic cycle overview", { cycle_id: detailId, path: detailPath, status: response.status });
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(statusMessage(response.status));
        if (!cancelled) { setSelected(body as Overview); setTab("supervisors"); }
      } catch (reason) {
        if (import.meta.env.DEV) console.debug("Academic cycle overview", { cycle_id: detailId, path: detailPath, status: "none" });
        if (!cancelled) { setSelected(null); setDetailError(reason instanceof Error ? reason.message : "Cycle details could not be loaded."); }
      } finally { if (!cancelled) setDetailLoading(false); }
    };
    void loadDetail();
    return () => { cancelled = true; };
  }, [api, detailId]);

  const open = (cycle: Cycle) => { window.history.pushState({ academicCycleId: cycle.id }, "", `${routeBase}/${cycle.id}`); setDetailId(cycle.id); setSelected(null); setDetailError(""); };
  const back = () => { window.history.pushState({ academicCycles: true }, "", routeBase); setDetailId(null); setSelected(null); setDetailError(""); };

  if (detailId !== null) {
    const cycle = selected?.cycle ?? cycles.find((item) => item.id === detailId);
    if (detailLoading) return <section className="academic-cycle-dashboard" aria-labelledby="academic-cycle-detail-heading"><button type="button" className="academic-cycle-dashboard__back" onClick={back}>← Back to Academic Cycles</button><p className="academic-cycle-dashboard__state">Loading cycle details…</p></section>;
    if (detailError || !selected) return <section className="academic-cycle-dashboard" aria-labelledby="academic-cycle-detail-heading"><button type="button" className="academic-cycle-dashboard__back" onClick={back}>← Back to Academic Cycles</button><div className="academic-cycle-dashboard__detail-heading"><div><p className="academic-cycle-dashboard__eyebrow">Academic cycle detail</p><h1 id="academic-cycle-detail-heading">{cycle?.display_name ?? "Academic Cycle"}</h1><p>{cycle?.code ?? `Cycle ID ${detailId}`}</p></div></div><p role="alert" className="academic-cycle-dashboard__error">{detailError || "Cycle details were not found."}</p></section>;
    return <section className="academic-cycle-dashboard" aria-labelledby="academic-cycle-detail-heading"><button type="button" className="academic-cycle-dashboard__back" onClick={back}>← Back to Academic Cycles</button><div className="academic-cycle-dashboard__detail-heading"><div><p className="academic-cycle-dashboard__eyebrow">Academic cycle detail</p><h1 id="academic-cycle-detail-heading">{selected.cycle.display_name}</h1><p>{selected.cycle.code} · {display(selected.cycle.department, "Department not recorded")}</p></div><span className="academic-cycle-dashboard__status">{selected.cycle.status ?? (selected.cycle.registration_open ? "ACTIVE" : "CLOSED")}</span></div><div className="academic-cycle-dashboard__meta"><span>Start <strong>{date(selected.cycle.start_date)}</strong></span><span>End <strong>{date(selected.cycle.end_date)}</strong></span><span>Registration <strong>{selected.cycle.registration_open ? "Open" : "Closed"}</strong></span></div><div className="academic-cycle-dashboard__summary">{(["supervisors", "students", "groups", "projects", "active_projects", "completed_projects", "pending_reviews", "required_documents"] as const).map((key) => <div key={key}><strong>{selected.summary[key]}</strong><span>{key.replaceAll("_", " ")}</span></div>)}</div><div className="academic-cycle-dashboard__tabs" role="tablist" aria-label="Academic cycle details">{(["supervisors", "projects", "groups", "students", "documents"] as const).map((key) => <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}>{key}</button>)}</div><CycleTable tab={tab} overview={selected} />{canManage && <details className="academic-cycle-dashboard__management"><summary>Manage cycle settings</summary><AdminCycleManager api={api} onChanged={() => void loadCycles()} /></details>}</section>;
  }

  return <section className="academic-cycle-dashboard" aria-labelledby="academic-cycles-heading"><div className="academic-cycle-dashboard__heading"><div><p className="academic-cycle-dashboard__eyebrow">Academic operations</p><h1 id="academic-cycles-heading">Academic Cycles</h1><p>Review cycle status, project activity, people, groups, and document requirements from one authorized dashboard.</p></div></div>{listError && <p role="alert" className="academic-cycle-dashboard__error">{listError} <button type="button" onClick={() => void loadCycles()}>Retry</button></p>}{loading && <p className="academic-cycle-dashboard__state">Loading academic cycles…</p>}{!loading && !cycles.length && <p className="academic-cycle-dashboard__state">No academic cycles are configured.</p>}<div className="academic-cycle-dashboard__grid">{cycles.map((cycle) => <button type="button" key={cycle.id} className="academic-cycle-dashboard__card" onClick={() => open(cycle)}><div className="academic-cycle-dashboard__card-top"><div><span>Cycle</span><h2>{cycle.display_name}</h2><p>{cycle.code}</p></div><b>{cycle.status ?? (cycle.registration_open ? "ACTIVE" : "CLOSED")}</b></div><div className="academic-cycle-dashboard__dates"><span>Start <strong>{date(cycle.start_date)}</strong></span><span>End <strong>{date(cycle.end_date)}</strong></span></div><div className="academic-cycle-dashboard__counts">{typeof cycle.supervisors_count === "number" && <span>{cycle.supervisors_count} supervisors</span>}{typeof cycle.projects_count === "number" && <span>{cycle.projects_count} projects</span>}{typeof cycle.groups_count === "number" && <span>{cycle.groups_count} groups</span>}{typeof cycle.students_count === "number" && <span>{cycle.students_count} students</span>}{![cycle.supervisors_count, cycle.projects_count, cycle.groups_count, cycle.students_count].some((value) => typeof value === "number") && <span>Open details for live totals</span>}</div><span className="academic-cycle-dashboard__view">View details →</span></button>)}</div></section>;
}

function CycleTable({ tab, overview }: { tab: Tab; overview: Overview }) {
  const rows = overview[tab];
  if (!rows.length) return <p className="academic-cycle-dashboard__state">No {tab} are recorded for this cycle.</p>;
  const fields: Record<Tab, string[]> = { supervisors: ["name", "email", "assigned_students", "assigned_groups", "capacity_used", "available_capacity", "assignment_status"], projects: ["title", "student_or_group", "proposal_type", "proposal_status", "project_stage", "review_status", "related_documents_count"], groups: ["name", "leader", "assigned_supervisor", "project_title", "status", "created_at"], students: ["name", "registration_number", "email", "group_id", "project_title", "proposal_status", "required_document_status", "assignment_status"], documents: ["title", "status", "due_at", "allowed_file_types", "submissions"] };
  return <div className="academic-cycle-dashboard__table-wrap"><table><thead><tr>{fields[tab].map((field) => <th key={field}>{field.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)}>{fields[tab].map((field) => <td key={field}>{field === "allowed_file_types" && Array.isArray(row[field]) ? (row[field] as unknown[]).join(", ") : field === "submissions" && Array.isArray(row[field]) ? `${(row[field] as unknown[]).length} submission(s)` : typeof row[field] === "object" && row[field] !== null ? display((row[field] as Record<string, unknown>).name ?? (row[field] as Record<string, unknown>).full_name) : display(row[field])}</td>)}</tr>)}</tbody></table></div>;
}
