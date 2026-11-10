/* eslint-disable react-hooks/set-state-in-effect, react-hooks/purity, react-hooks/exhaustive-deps */
import { useCallback, useEffect, useState } from "react";

type Requirement = { id: number; title: string; description?: string | null; due_at: string; is_required?: boolean; priority?: string; allowed_file_types?: string[]; max_file_size_mb?: number; status?: string };
type Submission = { status?: string; is_late?: boolean };
const endpoint = (api: string) => `${api}/api/v1/student/document-requirements`;
const readable = (status: number) => ({ 401: "You must sign in to load required documents.", 403: "You are not authorized to view required documents.", 404: "The required-documents route was not found.", 500: "The backend could not load required documents." }[status] ?? "Required documents could not be loaded.");

export function StudentRequiredDocumentsDashboard({ api }: { api: string }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [submissions, setSubmissions] = useState<Record<number, Submission>>({});
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setState("loading"); setError("");
    const url = endpoint(api);
    try {
      const response = await fetch(url, { credentials: "include" });
      const body: unknown = await response.json().catch(() => []);
      const rows = Array.isArray(body) ? body : (body && typeof body === "object" && Array.isArray((body as { requirements?: unknown }).requirements) ? (body as { requirements: Requirement[] }).requirements : null);
      if (import.meta.env.DEV) console.debug("student_document_requirements", { url, status: response.status, responseKeys: body && typeof body === "object" && !Array.isArray(body) ? Object.keys(body) : [], requirementCount: rows?.length ?? 0 });
      if (!response.ok) throw new Error(readable(response.status));
      if (!rows) throw new Error("The required-documents response was malformed.");
      setRequirements(rows);
      const loaded = await Promise.all(rows.map(async item => { const r = await fetch(`${api}/api/v1/document-requirements/${item.id}/submission`, { credentials: "include" }); return [item.id, r.ok ? await r.json() as Submission : undefined] as const; }));
      setSubmissions(Object.fromEntries(loaded.filter(([, value]) => value)));
      setState("ready");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Required documents could not be loaded."); setState("error"); }
  }, [api]);
  useEffect(() => { void load(); }, [load]);
  return <section aria-label="Required Documents & Uploads" className="mt-8 rounded-2xl border border-[#dce4de] bg-white p-6"><div className="flex items-start justify-between gap-4"><div><p className="student-overview__eyebrow">Student documents</p><h2 className="text-2xl font-semibold">Required Documents &amp; Uploads</h2><p className="mt-1 text-sm text-slate-600">Upload and track assigned documents outside the proposal timeline.</p></div>{state === "error" && <button type="button" onClick={() => void load()} className="rounded-lg border px-3 py-2 text-sm font-semibold">Retry</button>}</div>{state === "loading" && <p role="status" className="mt-5">Loading required documents…</p>}{state === "error" && <p role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm">{error}</p>}{state === "ready" && requirements.length === 0 && <p className="mt-5 rounded-lg border border-dashed p-4 text-sm">No required documents are currently assigned.</p>}{state === "ready" && requirements.length > 0 && <div className="mt-5 grid gap-3">{requirements.map(item => { const submission = submissions[item.id]; const overdue = new Date(item.due_at).getTime() < Date.now() && submission?.status !== "APPROVED"; return <article key={item.id} className="rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-4"><div><h3 className="font-semibold">{item.title}</h3><p className="text-sm text-slate-600">{item.description || "No description provided."}</p><p className="mt-2 text-xs">{item.is_required === false ? "Optional" : "Required"} · Priority: {item.priority || "NORMAL"} · Due: {new Date(item.due_at).toLocaleDateString()} · {overdue ? "OVERDUE" : "ON TIME"}</p><p className="mt-1 text-sm">Submission status: <strong>{submission?.status || "NOT_STARTED"}</strong>{submission?.is_late ? " · Late upload" : ""}</p><p className="mt-1 text-xs">Allowed: {(item.allowed_file_types || []).join(", ") || "PDF, DOC, DOCX"} · Max: {item.max_file_size_mb || 10} MB</p></div><button type="button" className="rounded-lg bg-[#4663FF] px-3 py-2 text-sm font-semibold text-white" onClick={() => document.getElementById(`document-upload-${item.id}`)?.click()}>Upload / Replace<input id={`document-upload-${item.id}`} className="sr-only" type="file" accept={(item.allowed_file_types || ["pdf", "doc", "docx"]).map(type => `.${type}`).join(",")} onChange={async event => { const file = event.target.files?.[0]; if (!file) return; const form = new FormData(); form.append("file", file); const response = await fetch(`${api}/api/v1/document-requirements/${item.id}/upload`, { method: "POST", credentials: "include", body: form }); if (response.ok) await load(); else setError(readable(response.status)); }} /></button></div></article>; })}</div>}</section>;
}
