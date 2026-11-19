/* eslint-disable react-hooks/set-state-in-effect, react-hooks/purity */
import { useCallback, useEffect, useMemo, useState } from "react";

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
type Submission = { status?: string; is_late?: boolean; review_comment?: string | null; uploaded_at?: string; versions: Version[] };
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

const statusLabel = (value?: string) => ({
  UPLOADED: "Submitted · awaiting review",
  ACCEPTED: "Approved",
  REJECTED: "Rejected",
  RESUBMISSION_REQUIRED: "Changes requested",
}[value || ""] || "Not submitted");

export function StudentRequiredDocumentsDashboard({ api }: { api: string }) {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [submissions, setSubmissions] = useState<Record<number, Submission>>({});
  const [group, setGroup] = useState<GroupContext | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [preview, setPreview] = useState<PreviewState | null>(null);

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

  const grouped = useMemo(() => {
    const sections = new Map<string, Requirement[]>();
    requirements.forEach((item) => {
      const key = item.module?.trim() || "Other";
      sections.set(key, [...(sections.get(key) || []), item]);
    });
    return [...sections.entries()];
  }, [requirements]);

  return <section aria-label="Required Documents & Uploads" className="mt-8 rounded-2xl border border-[#dce4de] bg-white p-6">
    <div className="flex items-start justify-between gap-4"><div><p className="student-overview__eyebrow">Student documents</p><h2 className="text-2xl font-semibold">Required Documents &amp; Uploads</h2><p className="mt-1 text-sm text-slate-600">Your active cycle requirements, grouped by submission section.</p></div>{state === "error" && <button type="button" onClick={() => void load()} className="rounded-lg border px-3 py-2 text-sm font-semibold">Retry</button>}</div>
    {(group || requirements.length > 0) && <div className="mt-4 grid gap-2 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-3"><div><span className="block text-xs uppercase tracking-wide text-slate-500">Academic cycle</span><strong>{group?.academic_cycle || (requirements[0] ? `Cycle ${requirements[0].academic_cycle_id}` : "Not detected")}</strong></div><div><span className="block text-xs uppercase tracking-wide text-slate-500">Group</span><strong>{group?.group_name || "Not detected"}</strong></div><div><span className="block text-xs uppercase tracking-wide text-slate-500">Project</span><strong>{group?.project?.title || "Not assigned"}</strong></div></div>}
    {message && <p role="status" className="mt-4 rounded-lg border p-3 text-sm">{message}</p>}
    {state === "loading" && <p className="mt-5">Loading required documents…</p>}
    {state === "ready" && !requirements.length && <p className="mt-5 rounded-lg border border-dashed p-4 text-sm">No published document requirements are currently assigned.</p>}
    {state === "ready" && <div className="mt-5 grid gap-5">{grouped.map(([section, rows]) => <section key={section} aria-label={`${section} requirements`}><h3 className="mb-2 text-lg font-semibold">{section}</h3><div className="grid gap-3">{rows.map((item) => {
      const submission = submissions[item.id];
      const closed = item.status === "CLOSED";
      const overdue = new Date(item.due_at).getTime() < Date.now();
      const disabled = closed || (overdue && !item.late_upload_allowed) || busy !== null;
      return <article key={item.id} className="rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 flex-1"><h4 className="font-semibold">{item.title}</h4><p className="text-sm text-slate-600">{item.description || "No instructions provided."}</p><p className="mt-2 text-xs">{item.is_required === false ? "Optional" : "Required"} · {item.status} · Due: {new Date(item.due_at).toLocaleString()}</p><p className="mt-1 text-sm">Submission status: <strong>{statusLabel(submission?.status)}</strong>{submission?.is_late ? " · Late upload" : ""}</p><p className="mt-1 text-xs">Allowed: {(item.allowed_file_types || []).join(", ")} · Max: {item.max_file_size_mb || 10} MB</p>{submission?.review_comment && <p className="mt-2 rounded border-l-2 border-amber-400 bg-amber-50 p-2 text-sm">Reviewer comment: {submission.review_comment}</p>}{submission?.versions?.length ? <div className="mt-3 rounded-lg bg-slate-50 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your version history</p><div className="mt-2 grid gap-2">{submission.versions.map((version) => <div key={version.id} className="flex flex-wrap items-center justify-between gap-2 rounded border bg-white px-3 py-2 text-sm"><span>{version.original_filename} <small className="text-slate-500">· Version {version.version_number} · {new Date(version.uploaded_at).toLocaleString()}</small></span><span className="flex flex-wrap gap-2"><button type="button" onClick={() => void openPreview(version)} className="rounded border border-[#4663ff] px-3 py-1 text-xs font-semibold text-[#354fe0]">View</button><button type="button" disabled={downloading === version.id} onClick={() => void download(version)} className="rounded border border-[#4663ff] px-3 py-1 text-xs font-semibold text-[#354fe0]">{downloading === version.id ? "Downloading…" : "Download"}</button></span></div>)}</div></div> : null}</div><label onClick={(event) => { if (!disabled && submission && !window.confirm("Replace this submission with a new version? Continue to choose a file?")) event.preventDefault(); }} className={`rounded-lg px-3 py-2 text-sm font-semibold ${disabled ? "cursor-not-allowed bg-slate-300 text-slate-600" : "cursor-pointer bg-[#4663FF] text-white"}`}>{closed ? "Closed" : overdue && !item.late_upload_allowed ? "Deadline passed" : busy === item.id ? "Uploading…" : submission ? "Replace / resubmit" : "Upload file"}<input className="sr-only" type="file" accept={(item.allowed_file_types || []).map((type) => `.${type}`).join(",")} disabled={disabled} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(item, file); event.currentTarget.value = ""; }} /></label></div></article>;
    })}</div></section>)}</div>}

    {preview && <div role="dialog" aria-modal="true" aria-label={`Preview ${preview.title}`} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4"><div className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"><div className="flex flex-wrap items-center justify-between gap-3 border-b p-4"><div><h2 className="font-semibold">{preview.title}</h2><p className="text-xs text-slate-500">Inline preview · use Download only when a local copy is needed</p></div><div className="flex flex-wrap items-center gap-2 text-sm"><button type="button" disabled={preview.page <= 1} onClick={() => setPreview((current) => current && ({ ...current, page: current.page - 1 }))} className="rounded border px-2 py-1">Previous</button><span>Page {preview.page} / {preview.pages}</span><button type="button" disabled={preview.page >= preview.pages} onClick={() => setPreview((current) => current && ({ ...current, page: current.page + 1 }))} className="rounded border px-2 py-1">Next</button><button type="button" onClick={() => setPreview((current) => current && ({ ...current, zoom: Math.max(50, current.zoom - 10) }))} className="rounded border px-2 py-1">−</button><span>{preview.zoom}%</span><button type="button" onClick={() => setPreview((current) => current && ({ ...current, zoom: Math.min(200, current.zoom + 10) }))} className="rounded border px-2 py-1">+</button><button type="button" onClick={closePreview} className="rounded bg-slate-800 px-3 py-1 text-white">Close</button></div></div><div className="min-h-0 flex-1 bg-slate-100 p-3">{preview.loading ? <p className="p-6 text-sm">Generating preview…</p> : preview.error ? <p role="alert" className="p-6 text-sm text-red-700">{preview.error}</p> : <iframe title={`Preview of ${preview.title}`} src={`${preview.url}#page=${preview.page}&zoom=${preview.zoom}`} className="h-full w-full rounded border bg-white" />}</div></div></div>}
  </section>;
}
