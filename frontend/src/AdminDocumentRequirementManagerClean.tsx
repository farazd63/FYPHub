/* eslint-disable react-hooks/set-state-in-effect -- initial list loading is intentionally started on mount. */
import { useCallback, useEffect, useState } from "react";

type Requirement = { id: number; title: string; due_at: string; allowed_file_types: string[]; status: string };
type FormatKey = "PDF" | "DOC" | "DOCX" | "TEX" | "TXT" | "MD" | "IMAGE" | "VIDEO" | "AUDIO" | "SPREADSHEET" | "PRESENTATION" | "ARCHIVE" | "ALL";
type Diagnostic = { origin: string; url: string; method: "GET" | "POST"; status: number | "none"; errorType: string };

const FORMAT_MAP: Record<FormatKey, string[]> = {
  PDF: ["PDF"], DOC: ["DOC"], DOCX: ["DOCX"], TEX: ["TEX"], TXT: ["TXT"], MD: ["MD"],
  IMAGE: ["JPG", "JPEG", "PNG", "GIF", "WEBP", "SVG"], VIDEO: ["MP4", "MOV", "AVI", "MKV", "WEBM"],
  AUDIO: ["MP3", "WAV", "M4A", "OGG"], SPREADSHEET: ["XLS", "XLSX", "CSV"],
  PRESENTATION: ["PPT", "PPTX"], ARCHIVE: ["ZIP", "RAR", "7Z"], ALL: [],
};
FORMAT_MAP.ALL = Object.values(FORMAT_MAP).flat();

const errorMessage = (status: number, detail: unknown) => {
  const detailText = typeof detail === "string" ? detail : detail && typeof detail === "object" && typeof (detail as { detail?: unknown }).detail === "string" ? (detail as { detail: string }).detail : "";
  return ({ 401: "Your session has expired. Please sign in again.", 403: "Admin or coordinator permission is required.", 404: "Document requirement endpoint was not found.", 422: detailText || "The backend rejected the submitted fields.", 500: detailText || "The backend returned a server error." } as Record<number, string>)[status] ?? (detailText || `The request failed with HTTP ${status}.`);
};

const responseRows = (body: unknown): Requirement[] => Array.isArray(body) ? body as Requirement[] : body && typeof body === "object" && Array.isArray((body as { requirements?: unknown }).requirements) ? (body as { requirements: Requirement[] }).requirements : [];

export function AdminDocumentRequirementManagerClean({ api }: { api: string }) {
  const base = api.replace(/\/$/, "");
  const listUrl = `${base}/api/v1/document-requirements`;
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [deadline, setDeadline] = useState("");
  const [format, setFormat] = useState<FormatKey>("PDF");
  const [fieldError, setFieldError] = useState("");
  const [requestError, setRequestError] = useState("");
  const [success, setSuccess] = useState("");
  const [diagnostic, setDiagnostic] = useState<Diagnostic | null>(null);

  const request = useCallback(async (method: "GET" | "POST", payload?: object) => {
    const url = listUrl;
    try {
      const response = await fetch(url, {
        method,
        credentials: "include",
        headers: method === "POST" ? { "Content-Type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      });
      const body: unknown = await response.json().catch(() => null);
      const keys = body && typeof body === "object" && !Array.isArray(body) ? Object.keys(body) : [];
      setDiagnostic({ origin: window.location.origin, url, method, status: response.status, errorType: response.ok ? "none" : `HTTP_${response.status}` });
      if (import.meta.env.DEV) console.debug("document_requirements_request", { origin: window.location.origin, url, method, status: response.status, responseKeys: keys, errorType: response.ok ? "none" : `HTTP_${response.status}` });
      if (!response.ok) throw new Error(errorMessage(response.status, body));
      return body;
    } catch (error) {
      if (error instanceof TypeError) {
        setDiagnostic({ origin: window.location.origin, url, method, status: "none", errorType: error.name });
        if (import.meta.env.DEV) console.debug("document_requirements_request", { origin: window.location.origin, url, method, status: "none", responseKeys: [], errorType: error.name });
        throw new Error(`Network error: backend unavailable (${error.message || error.name}).`, { cause: error });
      }
      throw error;
    }
  }, [listUrl]);

  const load = useCallback(async () => {
    setLoading(true); setRequestError("");
    try { setRequirements(responseRows(await request("GET"))); }
    catch (error) { setRequestError(error instanceof Error ? error.message : "Required documents could not be loaded."); }
    finally { setLoading(false); }
  }, [request]);
  useEffect(() => { void load(); }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setFieldError(""); setRequestError(""); setSuccess("");
    const cleanTitle = title.trim();
    if (cleanTitle.length < 3) return setFieldError("Document to Upload must contain at least 3 characters.");
    if (!deadline) return setFieldError("Deadline is required.");
    const date = new Date(deadline);
    if (Number.isNaN(date.getTime())) return setFieldError("Deadline must be a valid date and time.");
    if (date.getTime() <= Date.now()) return setFieldError("Deadline must be in the future.");
    const allowed = FORMAT_MAP[format];
    if (!allowed?.length) return setFieldError("File Format is required.");
    setSaving(true);
    try {
      const body = await request("POST", { title: cleanTitle, due_date: date.toISOString(), allowed_file_types: [...allowed] });
      setSuccess("Requirement created successfully."); setTitle(""); setDeadline(""); setFormat("PDF");
      setRequirements(responseRows(await request("GET")));
      void body;
    } catch (error) { setRequestError(error instanceof Error ? error.message : "Requirement could not be created."); }
    finally { setSaving(false); }
  };

  return <section className="mx-auto w-full max-w-3xl"><h1 className="text-3xl font-bold">Required Documents</h1><p className="mt-1 text-slate-600">Create and manage document requirements.</p><form onSubmit={submit} className="mt-6 grid gap-4 rounded-2xl border bg-white p-6"><h2 className="text-xl font-semibold">Create document requirement</h2><label className="grid gap-1">Document to Upload<input value={title} onChange={event => setTitle(event.target.value)} className="rounded border p-3" />{fieldError && title.trim().length < 3 && <small className="text-red-600">{fieldError}</small>}</label><label className="grid gap-1">Deadline<input type="datetime-local" value={deadline} onChange={event => setDeadline(event.target.value)} className="rounded border p-3" />{fieldError && !deadline && <small className="text-red-600">{fieldError}</small>}</label><label className="grid gap-1">File Format<select value={format} onChange={event => setFormat(event.target.value as FormatKey)} className="rounded border p-3"><option value="PDF">PDF</option><option value="DOC">DOC</option><option value="DOCX">DOCX</option><option value="TEX">LaTeX (.tex)</option><option value="TXT">Plain text (.txt)</option><option value="MD">Markdown (.md)</option><option value="IMAGE">Image</option><option value="VIDEO">Video</option><option value="AUDIO">Audio</option><option value="SPREADSHEET">Spreadsheet</option><option value="PRESENTATION">Presentation</option><option value="ARCHIVE">Archive</option><option value="ALL">Any supported format / ALL</option></select></label>{fieldError && <p className="text-sm text-red-600">{fieldError}</p>}{requestError && <p role="alert" className="text-sm text-red-600">{requestError}<button type="button" className="ml-2 underline" onClick={() => void load()}>Retry</button></p>}{success && <p role="status" className="text-sm text-green-700">{success}</p>}{import.meta.env.DEV && diagnostic && <pre className="rounded bg-slate-100 p-2 text-xs" data-testid="request-diagnostic" data-origin={diagnostic.origin}>Origin: {diagnostic.origin}{"\n"}URL: {diagnostic.url}{"\n"}Method: {diagnostic.method}{"\n"}Status: {diagnostic.status}{"\n"}Error type: {diagnostic.errorType}</pre>}<button type="submit" disabled={saving} className="rounded bg-[#176b66] p-3 font-semibold text-white">{saving ? "Creating requirement…" : "Create Requirement"}</button></form><section className="mt-6 rounded-2xl border bg-white p-6"><h2 className="text-xl font-semibold">Existing document requirements</h2>{loading ? <p>Loading document requirements…</p> : requirements.length === 0 ? <p>No document requirements created yet.</p> : requirements.map(item => <article key={item.id} className="mt-3 rounded border p-4"><h3 className="font-semibold">{item.title}</h3><p>Format: {item.allowed_file_types.join(", ")} · Deadline: {new Date(item.due_at).toLocaleString()}</p><p>Status: {item.status}</p></article>)}</section></section>;
}
