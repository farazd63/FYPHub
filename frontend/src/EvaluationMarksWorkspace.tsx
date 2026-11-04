import { useCallback, useEffect, useMemo, useState } from "react";

/* The workspace synchronizes async API state and draft controls from persisted records. */
/* eslint-disable react-hooks/set-state-in-effect */

type Variant = "supervisor" | "panel" | "admin" | "student";
type Evaluation = { id: number; student_id: number | null; group_id: number | null; evaluator_id: number; evaluator_role: string; evaluation_category: string; maximum_marks: number; obtained_marks: number | null; feedback: string | null; status: string; returned_reason: string | null; submitted_at: string | null; approved_at: string | null; published_at: string | null; updated_at: string };
type Assignment = { group_id: number; academic_cycle_id: number; students: Array<{ id: number; full_name: string; registration_number: string; university_email: string }>; categories: string[] };
type ResultCategory = { category: string; maximum_marks: number; obtained_marks: number | null; status: string; evaluator_ids: number[]; feedback: string[] };
type Result = { student_id: number; group_id: number | null; student_name: string; registration_number: string | null; categories: ResultCategory[]; total_marks: number; maximum_marks: number; percentage: number; grade: string | null; gpa: number | null; published: boolean };
type Draft = { marks: string; feedback: string };

const labels: Record<string, string> = { FINAL_PRESENTATION: "Final Presentation", MID_REVIEW: "Mid Review", SUPERVISOR_EVALUATION: "Supervisor Evaluation", PROJECT_DOCUMENTATION: "Project Documentation", PROPOSAL: "Proposal" };
const maxMarks: Record<string, number> = { FINAL_PRESENTATION: 30, MID_REVIEW: 30, SUPERVISOR_EVALUATION: 10, PROJECT_DOCUMENTATION: 20, PROPOSAL: 10 };
const configs: Record<Exclude<Variant, "student">, { title: string; description: string; categories: string[] }> = {
  supervisor: { title: "Supervisor Evaluation & Marks", description: "Enter supervision evaluation marks out of 10 for your assigned FYP groups.", categories: ["SUPERVISOR_EVALUATION"] },
  panel: { title: "Panel Evaluation Dashboard", description: "Enter only your independent Final Presentation and Mid Review marks for assigned groups.", categories: ["FINAL_PRESENTATION", "MID_REVIEW"] },
  admin: { title: "Documentation & Proposal Evaluation", description: "Enter authorized Proposal and Project Documentation marks and monitor the evaluation process.", categories: ["PROJECT_DOCUMENTATION", "PROPOSAL"] },
};

async function responseBody(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : body?.detail?.message;
    throw new Error(detail || `Request failed with HTTP ${response.status}.`);
  }
  return body;
}

function draftKey(groupId: number, category: string) { return `${groupId}-${category}`; }

export function EvaluationMarksWorkspace({ api, variant }: { api: string; variant: Variant }) {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const config = variant === "student" ? null : configs[variant];

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      if (variant === "student") {
        setResult(await responseBody(await fetch(`${api}/api/v1/student/results`, { credentials: "include" })) as Result);
      } else {
        const [assignmentBody, evaluationBody] = await Promise.all([
          responseBody(await fetch(`${api}/api/v1/evaluations/assignments`, { credentials: "include" })),
          responseBody(await fetch(`${api}/api/v1/evaluations/my`, { credentials: "include" })),
        ]);
        setAssignments(Array.isArray(assignmentBody) ? assignmentBody : []);
        setEvaluations(Array.isArray(evaluationBody) ? evaluationBody : []);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Evaluation data could not be loaded."); }
    finally { setLoading(false); }
  }, [api, variant]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    setDrafts((current) => {
      const next = { ...current };
      evaluations.forEach((item) => { if (item.group_id !== null) next[draftKey(item.group_id, item.evaluation_category)] = { marks: item.obtained_marks === null ? "" : String(item.obtained_marks), feedback: item.feedback ?? "" }; });
      return next;
    });
  }, [evaluations]);

  const allowed = useMemo(() => new Set(config?.categories ?? []), [config]);
  const save = async (assignment: Assignment, category: string, evaluation: Evaluation | undefined, submit: boolean) => {
    const draft = drafts[draftKey(assignment.group_id, category)] ?? { marks: "", feedback: "" };
    const maximum = evaluation?.maximum_marks ?? maxMarks[category];
    const marks = draft.marks.trim() === "" ? null : Number(draft.marks);
    if (marks !== null && (!Number.isInteger(marks) || marks < 0 || marks > maximum)) { setError(`Enter a whole number between 0 and ${maximum} for ${labels[category]}.`); return; }
    if (submit && marks === null) { setError(`Marks are required before submitting ${labels[category]}.`); return; }
    if (submit && !window.confirm(`Submit ${labels[category]} for Group ${assignment.group_id}? Submitted marks are locked until correction is authorized.`)) return;
    setBusy(evaluation?.id ?? draftKey(assignment.group_id, category)); setMessage(""); setError("");
    try {
      const response = await fetch(evaluation ? `${api}/api/v1/evaluations/${evaluation.id}` : `${api}/api/v1/evaluations`, { method: evaluation ? "PATCH" : "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ group_id: assignment.group_id, evaluation_category: category, obtained_marks: marks, feedback: draft.feedback, submit }) });
      const body = await responseBody(response) as Evaluation;
      setEvaluations((current) => [...current.filter((item) => item.id !== body.id), body]);
      setMessage(submit ? "Evaluation submitted successfully." : "Evaluation draft saved.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Evaluation could not be saved."); }
    finally { setBusy(null); }
  };

  if (loading) return <section className="student-phase-page" aria-busy="true"><div className="student-page-heading"><h1>{config?.title ?? "My FYP Results"}</h1><p>Loading evaluation records…</p></div><div className="student-placeholder">Loading…</div></section>;
  if (variant === "student") return <StudentResultView result={result} error={error} onRetry={() => void load()} />;
  return <section className="student-phase-page" aria-labelledby="evaluation-marks-heading"><div className="student-page-heading"><p className="student-overview__eyebrow">Evaluation &amp; Marks</p><h1 id="evaluation-marks-heading">{config?.title}</h1><p>{config?.description}</p></div>{message && <p className="student-request-success" role="status">{message}</p>}{error && <p className="student-request-alert" role="alert">{error} <button type="button" onClick={() => void load()}>Retry</button></p>}{!assignments.length && !error && <div className="student-placeholder"><h2>No assigned FYP groups</h2><p>Authorized assignments will appear here when a group or panel schedule is assigned.</p></div>}<div className="student-overview__grid">{assignments.map((assignment) => <article key={assignment.group_id} className="student-request-card"><div className="student-phase-card__top"><span className="student-status student-status--partial">Group {assignment.group_id}</span><span>Cycle {assignment.academic_cycle_id}</span></div><h2>Assigned FYP group</h2><p>{assignment.students.map((student) => `${student.full_name} (${student.registration_number})`).join(", ") || "No student details available"}</p><div className="grid gap-3">{assignment.categories.filter((category) => allowed.has(category)).map((category) => <EvaluationCard key={category} api={api} assignment={assignment} category={category} evaluation={evaluations.find((item) => item.group_id === assignment.group_id && item.evaluation_category === category)} draft={drafts[draftKey(assignment.group_id, category)] ?? { marks: "", feedback: "" }} setDraft={(draft) => setDrafts((current) => ({ ...current, [draftKey(assignment.group_id, category)]: draft }))} busy={busy} onSave={(submit) => void save(assignment, category, evaluations.find((item) => item.group_id === assignment.group_id && item.evaluation_category === category), submit)} />)}</div></article>)}</div>{variant === "admin" && <AdminMonitoring api={api} />}</section>;
}

function EvaluationCard({ api, assignment, category, evaluation, draft, setDraft, busy, onSave }: { api: string; assignment: Assignment; category: string; evaluation?: Evaluation; draft: Draft; setDraft: (draft: Draft) => void; busy: number | string | null; onSave: (submit: boolean) => void }) {
  const [reportBusy, setReportBusy] = useState(false);
  const locked = Boolean(evaluation && ["SUBMITTED", "APPROVED", "PUBLISHED"].includes(evaluation.status));
  const isBusy = busy === (evaluation?.id ?? draftKey(assignment.group_id, category));
  const maximum = evaluation?.maximum_marks ?? maxMarks[category];
  const downloadReport = async () => {
    if (!evaluation) return;
    setReportBusy(true);
    try {
      const response = await fetch(`${api}/api/v1/evaluations/${evaluation.id}/report.pdf`, { credentials: "include" });
      if (!response.ok) throw new Error(`Report request failed with HTTP ${response.status}.`);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = `evaluation-${evaluation.id}.pdf`; link.click(); URL.revokeObjectURL(url);
    } finally { setReportBusy(false); }
  };
  return <div className="rounded-lg border border-[#dce5f2] bg-white p-4"><div className="flex flex-wrap items-center justify-between gap-2"><label className="font-semibold" htmlFor={`marks-${assignment.group_id}-${category}`}>{labels[category]} Marks (0–{maximum})</label><span>{evaluation?.status ?? "DRAFT"}</span></div><input id={`marks-${assignment.group_id}-${category}`} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2" type="number" min="0" max={maximum} step="1" value={draft.marks} disabled={locked || busy !== null} onChange={(event) => setDraft({ ...draft, marks: event.target.value })} aria-label={`${labels[category]} marks`} /><label className="mt-3 block text-sm font-semibold" htmlFor={`feedback-${assignment.group_id}-${category}`}>Feedback / Comments</label><textarea id={`feedback-${assignment.group_id}-${category}`} className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2" value={draft.feedback} disabled={locked || busy !== null} onChange={(event) => setDraft({ ...draft, feedback: event.target.value })} />{evaluation?.returned_reason && <p className="mt-2 text-sm text-amber-700">Correction requested: {evaluation.returned_reason}</p>}<div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={busy !== null || locked} onClick={() => onSave(false)}>{isBusy ? "Saving…" : locked ? "Locked" : "Save Draft"}</button><button type="button" disabled={busy !== null || locked} onClick={() => onSave(true)}>{isBusy ? "Submitting…" : "Submit Evaluation"}</button>{evaluation && <button type="button" disabled={reportBusy} onClick={() => void downloadReport()}>{reportBusy ? "Downloading…" : "Download Report"}</button>}</div></div>;
}

function StudentResultView({ result, error, onRetry }: { result: Result | null; error: string; onRetry: () => void }) {
  return <section className="student-phase-page" aria-labelledby="student-results-heading"><div className="student-page-heading"><p className="student-overview__eyebrow">Published academic results</p><h1 id="student-results-heading">My FYP Results</h1><p>Only officially published marks are displayed.</p></div>{error && <p className="student-request-alert" role="alert">{error} <button type="button" onClick={onRetry}>Retry</button></p>}{!error && result && !result.published && <div className="student-placeholder">Results are not published yet. Your marks will appear here after authorization and publication.</div>}{result?.published && <><div className="student-overview__summary"><div><strong>{result.total_marks}</strong><span>/ {result.maximum_marks} marks</span></div><div><strong>{result.percentage}%</strong><span>percentage</span></div><div><strong>{result.grade}</strong><span>grade · GPA {result.gpa?.toFixed(2)}</span></div></div><div className="student-request-card"><h2>Consolidated marksheet</h2><div className="grid gap-2">{result.categories.map((category) => <div key={category.category} className="flex flex-wrap items-center justify-between border-b border-slate-100 py-2"><span>{labels[category.category] ?? category.category}</span><strong>{category.obtained_marks} / {category.maximum_marks}</strong></div>)}</div></div></>}</section>;
}

function AdminMonitoring({ api }: { api: string }) {
  const [rows, setRows] = useState<Evaluation[]>([]);
  const [groupResults, setGroupResults] = useState<Record<number, Result[]>>({});
  const [aggregation, setAggregation] = useState<Array<{ id: number; evaluation_category: string; method: string }>>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<number | string | null>(null);
  const load = useCallback(async () => {
    setMessage("");
    try {
      const [rowsResponse, aggregationResponse] = await Promise.all([
        fetch(`${api}/api/v1/admin/evaluations`, { credentials: "include" }),
        fetch(`${api}/api/v1/admin/evaluations/aggregation`, { credentials: "include" }),
      ]);
      const rowsBody = await responseBody(rowsResponse);
      setRows(Array.isArray(rowsBody) ? rowsBody : []);
      if (aggregationResponse.ok) {
        const aggregationBody = await aggregationResponse.json();
        setAggregation(Array.isArray(aggregationBody) ? aggregationBody : []);
      }
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Central evaluation monitoring is unavailable.");
    }
  }, [api]);
  useEffect(() => { void load(); }, [load]);
  const runAction = async (row: Evaluation, action: "approve" | "publish" | "return" | "correct") => {
    let body: string | undefined;
    if (action === "return") {
      const reason = window.prompt("Reason for returning this evaluation:", "Please review and correct the submitted marks.");
      if (!reason) return;
      body = JSON.stringify({ reason });
    }
    if (action === "correct") {
      const newMarks = window.prompt(`Authorized correction, marks out of ${row.maximum_marks}:`, String(row.obtained_marks ?? ""));
      const reason = window.prompt("Justification for this correction:", "Authorized correction after verification.");
      if (newMarks === null || reason === null) return;
      body = JSON.stringify({ new_marks: Number(newMarks), reason });
    }
    setBusy(`${action}-${row.id}`); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/evaluations/${row.id}/${action}`, { method: "POST", credentials: "include", headers: body ? { "Content-Type": "application/json" } : undefined, body });
      await responseBody(response);
      setMessage(`Evaluation ${action === "return" ? "returned for correction" : `${action}d`} successfully.`);
      await load();
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "The evaluation action could not be completed."); }
    finally { setBusy(null); }
  };
  const updateAggregation = async (category: string, method: string) => {
    setBusy(`aggregation-${category}`); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/admin/evaluations/aggregation`, { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ evaluation_category: category, method }) });
      await responseBody(response); setMessage("Panel aggregation method updated."); await load();
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "Aggregation configuration could not be updated."); }
    finally { setBusy(null); }
  };
  const viewGroupResults = async (groupId: number) => {
    setBusy(`results-${groupId}`); setMessage("");
    try {
      const body = await responseBody(await fetch(`${api}/api/v1/admin/results/group/${groupId}`, { credentials: "include" }));
      setGroupResults((current) => ({ ...current, [groupId]: Array.isArray(body) ? body : [] }));
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "The consolidated group result could not be loaded."); }
    finally { setBusy(null); }
  };
  return <article className="student-request-card mt-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2>Centralized evaluation monitoring</h2><p className="student-request-muted">Review all evaluator submissions without changing evaluator ownership.</p></div><button type="button" onClick={() => void load()} disabled={busy !== null}>Refresh</button></div>{message && <p className="student-request-alert" role="alert">{message}</p>}{!rows.length && !message && <p className="student-request-muted">No evaluator records have been submitted.</p>}<div className="grid gap-2">{rows.map((row) => <div key={row.id} className="rounded-lg border border-slate-100 p-3"><div className="flex flex-wrap items-center justify-between gap-3"><span>{labels[row.evaluation_category] ?? row.evaluation_category} · Evaluator {row.evaluator_id}</span><strong>{row.obtained_marks ?? "—"}/{row.maximum_marks} · {row.status}</strong></div><div className="mt-2 flex flex-wrap gap-2">{row.status === "SUBMITTED" && <><button type="button" disabled={busy !== null} onClick={() => void runAction(row, "approve")}>Approve</button><button type="button" disabled={busy !== null} onClick={() => void runAction(row, "return")}>Return for correction</button></>}{["SUBMITTED", "APPROVED", "PUBLISHED"].includes(row.status) && <button type="button" disabled={busy !== null} onClick={() => void runAction(row, "correct")}>Authorize correction</button>}{row.status === "APPROVED" && <button type="button" disabled={busy !== null} onClick={() => void runAction(row, "publish")}>Publish result</button>}{row.group_id !== null && <button type="button" disabled={busy !== null} onClick={() => void viewGroupResults(row.group_id!)}>View consolidated result</button>}<a href={`${api}/api/v1/evaluations/${row.id}/report.pdf`} target="_blank" rel="noreferrer">Individual report</a></div>{row.group_id !== null && groupResults[row.group_id] && <div className="mt-3 grid gap-2 border-t border-slate-100 pt-2">{groupResults[row.group_id].map((result) => <div key={result.student_id} className="flex flex-wrap justify-between gap-2 text-sm"><span>{result.student_name} · {result.registration_number ?? "No registration number"}</span><strong>{result.total_marks}/{result.maximum_marks} · {result.grade ?? "Incomplete"}</strong></div>)}</div>}</div>)}</div><div className="mt-6 border-t border-slate-100 pt-4"><h3>Panel aggregation</h3><p className="student-request-muted">Panel marks are combined per category and never added as separate full-mark categories.</p><div className="grid gap-2 sm:grid-cols-2">{aggregation.map((item) => <label key={item.evaluation_category} className="grid gap-1 text-sm font-semibold">{labels[item.evaluation_category] ?? item.evaluation_category}<select value={item.method} disabled={busy !== null} onChange={(event) => void updateAggregation(item.evaluation_category, event.target.value)}><option value="AVERAGE">Average</option><option value="MAXIMUM">Maximum</option><option value="MEDIAN">Median</option></select></label>)}</div></div></article>;
}
