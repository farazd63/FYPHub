import { useEffect, useState } from "react";

type ArchiveRow = { id: number; title: string; short_summary?: string; academic_year?: string; project_scope?: string; completion_stage?: string; available_documents_count?: number };

export function CoordinatorArchive({ api }: { api: string }) {
  const [rows, setRows] = useState<ArchiveRow[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const search = async () => {
    setLoading(true); setError("");
    try {
      const suffix = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";
      const response = await fetch(`${api}/api/v1/archived-projects/search${suffix}`, { credentials: "include" });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(response.status === 403 ? "You are not authorized to view the FYP archive." : `Archive request failed (HTTP ${response.status}).`);
      setRows(body && typeof body === "object" && Array.isArray((body as { results?: unknown }).results) ? (body as { results: ArchiveRow[] }).results : []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The FYP archive could not be loaded."); } finally { setLoading(false); }
  };
  // Initial data loading is intentionally performed after mount.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void search(); }, [api]);
  return <section className="student-phase-page" aria-labelledby="coordinator-archive-heading"><div className="student-page-heading"><p className="student-overview__eyebrow">Workspace</p><h1 id="coordinator-archive-heading">FYP Archive</h1><p>Search active archived projects and their available knowledge documents.</p></div><div className="mt-5 flex gap-2"><input aria-label="Search archive" value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1 rounded-lg border px-3 py-2" placeholder="Search by title or keyword" /><button type="button" className="rounded-lg bg-[#4663FF] px-4 py-2 font-semibold text-white" onClick={() => void search()} disabled={loading}>Search</button></div>{error && <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm">{error}<button type="button" className="ml-3 underline" onClick={() => void search()}>Retry</button></p>}{loading ? <p role="status" className="mt-5">Loading archive…</p> : !rows.length ? <p className="mt-5 rounded-xl border border-dashed bg-white p-5">No archived projects match this search.</p> : <div className="mt-5 grid gap-3">{rows.map((row) => <article key={row.id} className="rounded-xl border bg-white p-5"><h2 className="font-semibold">{row.title}</h2><p className="mt-1 text-sm text-slate-600">{row.short_summary || "No summary available."}</p><p className="mt-2 text-xs">{row.academic_year || "Year not recorded"} · {row.project_scope || "Scope not recorded"} · {row.completion_stage || "Stage not recorded"} · {row.available_documents_count ?? 0} documents</p></article>)}</div>}</section>;
}
