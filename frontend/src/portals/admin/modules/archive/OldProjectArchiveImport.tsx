import { useEffect, useState } from "react";

type Cycle = { id: number; code: string; display_name: string; academic_year?: number | null; session?: string | null };
type Preview = { total_rows: number; valid_rows: Array<{ row: number; data: Record<string, string> }>; invalid_rows: Array<{ row: number; errors: string[] }>; cycle: { academic_year: number; session: string } };

export function OldProjectArchiveImport({ api }: { api: string }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [cycleId, setCycleId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" }).then(async (response) => {
      if (!response.ok) throw new Error("Academic cycles could not be loaded.");
      const data = await response.json() as Cycle[];
      if (!cancelled) setCycles(data.filter((cycle) => cycle.academic_year && cycle.session));
    }).catch((error) => { if (!cancelled) setMessage(error instanceof Error ? error.message : "Academic cycles could not be loaded."); });
    return () => { cancelled = true; };
  }, [api]);

  const downloadTemplate = async () => {
    const response = await fetch(`${api}/api/v1/admin/archive/import-template`, { credentials: "include" });
    if (!response.ok) { setMessage("The official archive template could not be downloaded."); return; }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "old-fyp-projects-template.xlsx"; anchor.click(); URL.revokeObjectURL(url);
  };

  const previewImport = async () => {
    if (!cycleId || !file || busy) return;
    setBusy(true); setMessage(""); setPreview(null);
    const body = new FormData(); body.append("academic_cycle_id", cycleId); body.append("file", file);
    try { const response = await fetch(`${api}/api/v1/admin/archive/import/preview`, { method: "POST", credentials: "include", body }); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(typeof data.detail?.message === "string" ? data.detail.message : "The workbook could not be previewed."); setPreview(data as Preview); } catch (error) { setMessage(error instanceof Error ? error.message : "The workbook could not be previewed."); } finally { setBusy(false); }
  };

  const confirmImport = async () => {
    if (!cycleId || !file || !preview || preview.invalid_rows.length || busy) return;
    setBusy(true); setMessage(""); const body = new FormData(); body.append("academic_cycle_id", cycleId); body.append("file", file);
    try { const response = await fetch(`${api}/api/v1/admin/archive/import/confirm`, { method: "POST", credentials: "include", body }); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(typeof data.detail?.message === "string" ? data.detail.message : "The archive import failed."); setMessage(`${data.imported_count ?? 0} historical project(s) imported successfully.`); setPreview(null); setFile(null); } catch (error) { setMessage(error instanceof Error ? error.message : "The archive import failed."); } finally { setBusy(false); }
  };

  return <section aria-labelledby="old-project-import-heading" className="mb-5 rounded-xl border border-[#dce4de] bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="old-project-import-heading" className="font-bold">Import old FYP projects</h2><p className="mt-1 text-sm text-[#60716b]">Select an existing academic cycle, preview the official XLSX, then confirm a validated historical import.</p></div><button type="button" onClick={() => void downloadTemplate()} className="rounded-lg border border-[#176b66] px-3 py-2 text-sm font-semibold text-[#176b66]">Download official template</button></div><div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"><label className="grid gap-1 text-sm font-semibold">Academic cycle<select value={cycleId} onChange={(event) => { setCycleId(event.target.value); setPreview(null); }} className="rounded-lg border border-[#dce4de] px-3 py-2" required><option value="">Select an academic cycle</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name || cycle.code} ({cycle.academic_year} {cycle.session})</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">XLSX workbook<input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={!cycleId || busy} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setPreview(null); }} className="rounded-lg border border-[#dce4de] px-3 py-2" /></label><button type="button" disabled={!cycleId || !file || busy} onClick={() => void previewImport()} className="self-end rounded-lg bg-[#176b66] px-4 py-2 font-semibold text-white disabled:opacity-50">{busy ? "Working…" : "Preview import"}</button></div>{message && <p role="status" className="mt-3 rounded-lg bg-[#eef5ff] px-3 py-2 text-sm text-[#315db4]">{message}</p>}{preview && <div className="mt-4 rounded-lg border border-[#dce4de] bg-[#f8fbf9] p-4"><p className="font-semibold">Preview: {preview.valid_rows.length} valid, {preview.invalid_rows.length} invalid, {preview.total_rows} total</p>{preview.invalid_rows.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm text-red-700">{preview.invalid_rows.map((item) => <li key={item.row}>Row {item.row}: {item.errors.join("; ")}</li>)}</ul>}<button type="button" disabled={busy || preview.invalid_rows.length > 0 || !preview.valid_rows.length} onClick={() => void confirmImport()} className="mt-3 rounded-lg bg-[#4663ff] px-4 py-2 font-semibold text-white disabled:opacity-50">Confirm import</button></div>}</section>;
}
