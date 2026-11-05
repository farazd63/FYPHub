import { useState } from "react";

const input = "w-full rounded-lg border border-[#cbd6d0] bg-white px-3 py-2 text-sm text-[#243746] focus:border-[#176b66]";
type UploadedTemplate = { version_id: number; version_number: number; title: string; is_active: boolean };

export function AdminTemplateUpload({ api }: { api: string }) {
  const [type, setType] = useState<"SHORT" | "LONG">("SHORT");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [activationBusy, setActivationBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [uploaded, setUploaded] = useState<UploadedTemplate | null>(null);

  const activate = async () => {
    if (!uploaded || activationBusy) return;
    setActivationBusy(true); setError("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/admin/templates/${uploaded.version_id}/activate`, { method: "POST", credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "The template could not be activated.");
      setUploaded({ ...uploaded, is_active: true });
      setMessage(`${uploaded.title} v${uploaded.version_number} is now the active ${type} baseline. Previous reports remain unchanged.`);
      window.dispatchEvent(new CustomEvent("module3-template-uploaded"));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The template activation service is unavailable."); }
    finally { setActivationBusy(false); }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || busy) { setError("Choose the approved PDF or DOCX template first."); return; }
    setBusy(true); setError(""); setMessage(""); setUploaded(null);
    try {
      const form = new FormData();
      form.append("template_type", type); form.append("title", title.trim() || file.name); form.append("provenance", "OBSERVED_REFERENCE");
      form.append("source_note", `Automatically extracted from ${file.name}`); form.append("template_file", file);
      const response = await fetch(`${api}/api/v1/proposal-compliance/admin/templates/upload`, { method: "POST", credentials: "include", body: form });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "The template could not be extracted.");
      const result = body as UploadedTemplate;
      setUploaded(result); setMessage(`${result.title} was extracted as version ${result.version_number}. Activate it after reviewing the extracted rules.`); setFile(null); setTitle("");
      window.dispatchEvent(new CustomEvent("module3-template-uploaded"));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The template service is unavailable."); }
    finally { setBusy(false); }
  };

  return <form onSubmit={submit} className="mb-5 rounded-xl border border-[#9cb7e8] bg-[#f3f7ff] p-5" aria-labelledby="template-upload-heading">
    <div className="mb-3"><h2 id="template-upload-heading" className="font-bold text-[#1e3965]">Upload official proposal template</h2><p className="mt-1 text-sm text-[#60716b]">Upload the approved SHORT or LONG PDF/DOCX. Rules and required sections will be extracted from the file.</p></div>
    {message && <p role="status" className="mb-3 rounded-lg bg-[#e4eee7] p-3 text-sm text-[#176b66]">{message}</p>}{error && <p role="alert" className="mb-3 rounded-lg bg-[#fff3f0] p-3 text-sm text-[#a43a33]">{error}</p>}
    <div className="grid gap-3 md:grid-cols-[150px_1fr_1.5fr_auto] md:items-end"><label className="grid gap-1 text-sm font-semibold">Type<select className={input} value={type} onChange={(event) => setType(event.target.value as "SHORT" | "LONG")}><option>SHORT</option><option>LONG</option></select></label><label className="grid gap-1 text-sm font-semibold">Template title<input className={input} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Uses filename if blank" /></label><label className="grid gap-1 text-sm font-semibold">Approved PDF/DOCX<input className={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label><button type="submit" disabled={busy} className="rounded-lg bg-[#176b66] px-4 py-2 font-semibold text-white disabled:opacity-50">{busy ? "Extracting..." : "Upload & extract"}</button></div>
    {uploaded && !uploaded.is_active && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#f0ca78] bg-[#fff8e8] p-3 text-sm text-[#805b00]"><span>Review the extracted rules, then activate v{uploaded.version_number} for student comparisons.</span><button type="button" disabled={activationBusy} onClick={() => void activate()} className="rounded-lg bg-[#176b66] px-4 py-2 font-semibold text-white disabled:opacity-50">{activationBusy ? "Activating..." : `Activate v${uploaded.version_number}`}</button></div>}
  </form>;
}
