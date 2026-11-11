import { useEffect, useState } from "react";

type Cycle = { id: number; academic_year?: number | null; session?: string | null };

export function OldProjectArchiveImport({ api, onImported }: { api: string; onImported?: () => void }) {
  const [cycleId, setCycleId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Academic cycle unavailable.");
        const cycles = await response.json() as Cycle[];
        const first = cycles.find((cycle) => cycle.academic_year && cycle.session);
        if (first) setCycleId(String(first.id));
        else throw new Error("No academic cycle available.");
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Academic cycle unavailable."));
  }, [api]);

  const upload = async (file: File) => {
    if (!cycleId || busy) return;
    setBusy(true);
    setMessage("");
    const body = new FormData();
    body.append("academic_cycle_id", cycleId);
    body.append("file", file);
    body.append("has_headers", "true");
    try {
      const response = await fetch(`${api}/api/v1/admin/archive/import/confirm`, { method: "POST", credentials: "include", body });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail?.message === "string" ? data.detail.message : "The Excel file could not be imported.");
      setFile(null);
      const warning = Array.isArray(data.warnings) && data.warnings.length ? ` Warning: ${data.warnings.join(" ")}` : "";
      setMessage(`Imported ${data.unique_projects_created ?? data.inserted ?? data.imported_count ?? 0} unique projects; ${data.members_attached ?? 0} members attached; duplicates skipped ${data.duplicates_skipped ?? 0}; orphan rows ${data.orphan_rows ?? 0}; invalid rows ${data.invalid_rows ?? 0}; processed ${data.source_rows_processed ?? data.total_rows ?? 0}.${warning} Batch ${data.batch_id ?? "created"}.`);
      onImported?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The Excel file could not be imported.");
    } finally {
      setBusy(false);
    }
  };

  return <section className="mb-5 rounded-xl border border-[#dce4de] bg-white p-5" aria-labelledby="archive-import-heading">
    <h2 id="archive-import-heading" className="font-bold">Upload Excel file</h2>
    <label className="mt-4 grid gap-1 text-sm font-semibold">Excel file
      <input type="file" accept=".xls,.xlsx" disabled={!cycleId || busy} className="rounded-lg border border-[#dce4de] px-3 py-2" onChange={(event) => { setFile(event.target.files?.[0] ?? null); }} />
    </label>
    <button type="button" disabled={!file || !cycleId || busy} onClick={() => { if (file) void upload(file); }} className="mt-4 rounded-lg bg-[#4663ff] px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Uploading..." : "Upload Excel file"}</button>
    {message && <p role="status" className="mt-3 rounded-lg bg-[#eef5ff] px-3 py-2 text-sm text-[#315db4]">{message}</p>}
  </section>;
}
