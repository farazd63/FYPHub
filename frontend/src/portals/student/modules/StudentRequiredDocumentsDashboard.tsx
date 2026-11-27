/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, FileUpload, StatusBadge } from "../../../ui";
import { shortGroupLabel } from "../../../lib/displayLabels";

type Requirement = {
  id: number;
  title: string;
  description?: string | null;
  module?: string | null;
  academic_cycle_id: number;
  due_at: string;
  is_required?: boolean;
  allowed_file_types?: string[];
  max_file_size_mb?: number;
  late_upload_allowed?: boolean;
  status?: string;
};
type Version = { id: number; version_number: number; original_filename: string; uploaded_at: string; download_url?: string; preview_url?: string };
type ReviewEvent = { id: number; status: string; reviewer_name?: string | null; comment?: string | null; created_at: string };
type Submission = { id: number; status?: string; is_late?: boolean; review_comment?: string | null; reviewed_at?: string | null; uploaded_at?: string; versions: Version[]; review_history?: ReviewEvent[] };
type GroupContext = { group_name?: string | null; academic_cycle?: string | null; project?: { title?: string | null } | null };
type PreviewState = { url: string; title: string; page: number; pages: number; zoom: number; loading: boolean; error?: string };

const messageFor = (status: number) => ({ 401: "You must sign in to load required documents.", 403: "You are not authorized to view required documents.", 409: "This requirement is closed or the deadline has passed.", 413: "The selected file is too large.", 422: "The selected file type is not allowed.", 415: "This file type cannot be previewed in the application." }[status] || "The document request could not be completed.");

async function downloadVersion(api: string, version: Version) {
  if (!version.download_url) return;
  const response = await fetch(`${api}${version.download_url}`, { credentials: "include" });
  if (!response.ok) throw new Error("The uploaded file could not be downloaded.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = version.original_filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function StudentRequiredDocumentsDashboard({ api }: { api: string }) {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [submissions, setSubmissions] = useState<Record<number, Submission>>({});
  const [group, setGroup] = useState<GroupContext | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [deletingVersion, setDeletingVersion] = useState<number | null>(null);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [now] = useState(() => Date.now());

  const load = useCallback(async () => {
    setState("loading");
    setMessage("");
    try {
      const [response, groupResponse] = await Promise.all([
        fetch(`${api}/api/v1/student/group/requirements`, { credentials: "include" }),
        fetch(`${api}/api/v1/student/group/me`, { credentials: "include" }),
      ]);
      const body = await response.json().catch(() => []);
      if (!response.ok) throw new Error(messageFor(response.status));
      const rows = Array.isArray(body) ? body as Requirement[] : [];
      setRequirements(rows);
      if (groupResponse.ok) setGroup(await groupResponse.json() as GroupContext);
      const loaded = await Promise.all(rows.map(async (item) => {
        const result = await fetch(`${api}/api/v1/student/group/requirements/${item.id}/submission`, { credentials: "include" });
        return [item.id, result.ok ? await result.json() as Submission : undefined] as const;
      }));
      const next: Record<number, Submission> = {};
      loaded.forEach(([id, value]) => { if (value) next[id] = value; });
      setSubmissions(next);
      setState("ready");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Required documents could not be loaded.");
      setState("error");
    }
  }, [api]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview?.url]);
  useEffect(() => {
    if (state !== "ready") return;
    const requirementId = Number(new URLSearchParams(window.location.search).get("requirement_id"));
    if (!Number.isInteger(requirementId) || requirementId <= 0) return;
    const target = document.getElementById(`student-requirement-${requirementId}`);
    if (!target) return;
    const timer = window.setTimeout(() => target.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    return () => window.clearTimeout(timer);
  }, [requirements, state]);

  const upload = async (item: Requirement, file: File) => {
    if (busy !== null) return;
    const suffix = file.name.split(".").pop()?.toLowerCase() || "";
    const allowed = item.allowed_file_types || [];
    if (!allowed.includes(suffix)) {
      setMessage(`Only ${allowed.join(", ")} files are allowed.`);
      return;
    }
    if (file.size > (item.max_file_size_mb || 10) * 1024 * 1024) {
      setMessage(`The file must be ${item.max_file_size_mb || 10} MB or smaller.`);
      return;
    }
    setBusy(item.id);
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const endpoint = submissions[item.id] ? "resubmit" : "upload";
      const response = await fetch(`${api}/api/v1/student/group/requirements/${item.id}/${endpoint}`, { method: "POST", credentials: "include", body: form });
      if (!response.ok) throw new Error(messageFor(response.status));
      setMessage("Document uploaded successfully.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setBusy(null);
    }
  };

  const download = async (version: Version) => {
    setDownloading(version.id);
    setMessage("");
    try {
      await downloadVersion(api, version);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Download failed.");
    } finally {
      setDownloading(null);
    }
  };

  const deleteVersion = async (submission: Submission, version: Version) => {
    if (deletingVersion !== null) return;
    if (!window.confirm(`Remove “${version.original_filename}” from your upload history? Admin and supervisor records will be preserved.`)) return;
    setDeletingVersion(version.id);
    setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/document-requirements/submissions/${submission.id}/versions/${version.id}`, { method: "DELETE", credentials: "include" });
      if (!response.ok) throw new Error(messageFor(response.status));
      setMessage("Upload removed from your view. Admin and supervisor records are preserved.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The upload could not be removed.");
    } finally {
      setDeletingVersion(null);
    }
  };

  const openPreview = async (version: Version) => {
    if (!version.preview_url) {
      setMessage("This file does not have a preview endpoint.");
      return;
    }
    if (preview?.url) URL.revokeObjectURL(preview.url);
    setPreview({ url: "", title: version.original_filename, page: 1, pages: 1, zoom: 100, loading: true });
    try {
      const response = await fetch(`${api}${version.preview_url}`, { credentials: "include" });
      if (!response.ok) throw new Error((await response.text()) || messageFor(response.status));
      const blob = await response.blob();
      setPreview({ url: URL.createObjectURL(blob), title: version.original_filename, page: 1, pages: Number(response.headers.get("X-Preview-Page-Count")) || 1, zoom: 100, loading: false });
    } catch (error) {
      setPreview({ url: "", title: version.original_filename, page: 1, pages: 1, zoom: 100, loading: false, error: error instanceof Error ? error.message : "The document could not be previewed." });
    }
  };

  const closePreview = () => {
    if (preview?.url) URL.revokeObjectURL(preview.url);
    setPreview(null);
  };

  return <section aria-label="Required Documents & Uploads" className="student-documents-dashboard mt-8 rounded-2xl border border-fy-border bg-fy-surface p-6">
    <div className="flex items-start justify-between gap-4"><div><p className="student-overview__eyebrow">Student documents</p><h2 className="text-2xl font-semibold">Required Documents &amp; Uploads</h2><p className="mt-1 text-sm text-fy-text-secondary">Every requirement has its own submission and review record. Upload Video, PDF, and other requirements separately.</p></div></div>
    {state === "error" && <Alert tone="danger" title="Required documents unavailable" className="mt-4"><p className="m-0">{message}</p><div className="mt-3"><Button type="button" variant="secondary" size="sm" onClick={() => void load()}>Retry</Button></div></Alert>}
    {(group || requirements.length > 0) && <div className="mt-4 grid gap-2 rounded-xl bg-fy-surface-muted p-4 text-sm sm:grid-cols-3"><div><span className="block text-xs uppercase tracking-wide text-fy-text-secondary">Academic cycle</span><strong>{group?.academic_cycle || (requirements[0] ? `Cycle ${requirements[0].academic_cycle_id}` : "Not detected")}</strong></div><div><span className="block text-xs uppercase tracking-wide text-fy-text-secondary">Group</span><strong>{group ? shortGroupLabel(group.group_name, group.academic_cycle) : "Not detected"}</strong></div><div><span className="block text-xs uppercase tracking-wide text-fy-text-secondary">Project</span><strong>{group?.project?.title || "Not assigned"}</strong></div></div>}
    {message && <p role="status" className="mt-4 rounded-lg border p-3 text-sm">{message}</p>}
    {state === "loading" && <p className="mt-5">Loading required documents…</p>}
    {state === "ready" && !requirements.length && <p className="mt-5 rounded-lg border border-dashed p-4 text-sm">No published document requirements are currently assigned.</p>}
    {state === "ready" && <div className="mt-5 grid gap-5">{requirements.map((item) => {
      const submission = submissions[item.id];
      const closed = item.status === "CLOSED";
      const overdue = new Date(item.due_at).getTime() < now;
      const disabled = closed || (overdue && !item.late_upload_allowed) || busy !== null || deletingVersion !== null;
      return <article id={`student-requirement-${item.id}`} key={item.id} className="scroll-mt-6 rounded-xl border p-4"><div className="student-document-row flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 flex-1"><p className="text-xs font-semibold uppercase tracking-wide text-fy-text-secondary">{item.module?.trim() || "Other requirement"}</p><h3 className="mt-1 font-semibold">{item.title}</h3><p className="text-sm text-fy-text-secondary">{item.description || "No instructions provided."}</p><p className="mt-2 flex flex-wrap items-center gap-2 text-xs">{item.is_required === false ? "Optional" : "Required"}<StatusBadge status={item.status || "OPEN"} />Due: {new Date(item.due_at).toLocaleString()}</p><p className="mt-1 flex flex-wrap items-center gap-2 text-sm">Submission status: <StatusBadge status={submission?.status || "NOT_SUBMITTED"} />{submission?.is_late ? <span className="text-fy-warning">Late upload</span> : null}</p><p className="mt-1 text-xs">Allowed: {(item.allowed_file_types || []).join(", ")} · Max: {item.max_file_size_mb || 10} MB</p>{submission?.review_comment && <p className="mt-2 rounded border-l-2 border-fy-warning bg-fy-warning-soft p-2 text-sm">Reviewer comment: {submission.review_comment}</p>}{submission?.versions?.length ? <div className="mt-3 rounded-lg bg-fy-surface-muted p-3"><p className="text-xs font-semibold uppercase tracking-wide text-fy-text-secondary">Your version history</p><div className="mt-2 grid gap-2">{submission.versions.map((version) => <div key={version.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-fy-border bg-fy-surface px-3 py-2 text-sm"><span>{version.original_filename} <small className="text-fy-text-secondary">· Version {version.version_number} · {new Date(version.uploaded_at).toLocaleString()}</small></span><span className="flex flex-wrap gap-2"><button type="button" onClick={() => void openPreview(version)} className="fy-btn fy-btn--secondary fy-btn--sm">View</button><button type="button" disabled={downloading === version.id || deletingVersion !== null} onClick={() => void download(version)} className="fy-btn fy-btn--secondary fy-btn--sm">{downloading === version.id ? "Downloading…" : "Download"}</button><button type="button" disabled={deletingVersion !== null || busy !== null} onClick={() => void deleteVersion(submission, version)} className="fy-btn fy-btn--danger fy-btn--sm">{deletingVersion === version.id ? "Removing…" : "Delete"}</button></span></div>)}</div></div> : null}</div><FileUpload className="student-document-upload" accept={(item.allowed_file_types || []).map((type) => `.${type}`).join(",")} disabled={disabled} label={closed ? "Closed" : overdue && !item.late_upload_allowed ? "Deadline passed" : busy === item.id ? "Uploading…" : submission ? "Replace / resubmit" : "Upload file"} hint={`Up to ${item.max_file_size_mb || 10} MB`} onFiles={(files) => { const file = files[0]; if (!file) return; if (submission && !window.confirm("Replace this submission with a new version? Continue to choose a file?")) return; void upload(item, file); }} /></div></article>;
    })}</div>}

    {preview && <div role="dialog" aria-modal="true" aria-label={`Preview ${preview.title}`} className="portal-document-preview fixed flex items-center justify-center bg-fy-text/70 p-4"><div className="portal-document-preview__card flex h-full max-h-full w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-fy-surface shadow-2xl"><div className="flex flex-wrap items-center justify-between gap-3 border-b p-4"><div><h2 className="font-semibold">{preview.title}</h2><p className="text-xs text-fy-text-secondary">Inline preview · use Download only when a local copy is needed</p></div><div className="flex flex-wrap items-center gap-2 text-sm"><button type="button" disabled={preview.page <= 1} onClick={() => setPreview((current) => current && ({ ...current, page: current.page - 1 }))} className="rounded border px-2 py-1">Previous</button><span>Page {preview.page} / {preview.pages}</span><button type="button" disabled={preview.page >= preview.pages} onClick={() => setPreview((current) => current && ({ ...current, page: current.page + 1 }))} className="rounded border px-2 py-1">Next</button><button type="button" onClick={() => setPreview((current) => current && ({ ...current, zoom: Math.max(50, current.zoom - 10) }))} className="rounded border px-2 py-1">−</button><span>{preview.zoom}%</span><button type="button" onClick={() => setPreview((current) => current && ({ ...current, zoom: Math.min(200, current.zoom + 10) }))} className="rounded border px-2 py-1">+</button><button type="button" onClick={closePreview} className="fy-btn fy-btn--primary fy-btn--sm">Close</button></div></div><div className="min-h-0 flex-1 bg-fy-surface-muted p-3">{preview.loading ? <p className="p-6 text-sm">Generating preview…</p> : preview.error ? <p role="alert" className="p-6 text-sm text-fy-danger">{preview.error}</p> : <iframe title={`Preview of ${preview.title}`} src={`${preview.url}#page=${preview.page}&zoom=${preview.zoom}`} className="h-full w-full rounded border border-fy-border bg-fy-surface" />}</div></div></div>}
    {Object.entries(submissions).some(([, submission]) => Boolean(submission.review_history?.length)) && <section className="mt-6 rounded-xl border border-fy-border bg-fy-surface p-5"><h3 className="text-lg font-semibold">Review history</h3><div className="mt-3 grid gap-3">{requirements.map((item) => { const history = submissions[item.id]?.review_history || []; return history.length ? <article key={item.id} className="rounded-lg border border-fy-border bg-fy-surface-muted p-3"><strong>{item.title}</strong><div className="mt-2 grid gap-2 text-sm">{history.map((event) => <div key={event.id} className="flex flex-wrap items-center gap-2"><StatusBadge status={event.status} /><span>{event.reviewer_name || "Reviewer"} · {new Date(event.created_at).toLocaleString()}</span>{event.comment && <p className="w-full text-fy-text-secondary">{event.comment}</p>}</div>)}</div></article> : null; })}</div></section>}
  </section>;
}
