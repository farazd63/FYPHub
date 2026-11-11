import { useCallback, useEffect, useState } from "react";
import { OldProjectArchiveImport } from "./OldProjectArchiveImport";

type SourceColumn = { key: string; label: string };
type SourceMetadata = { imported?: boolean; columns?: SourceColumn[]; cells?: Record<string, string>; [key: string]: unknown };
type Project = {
  id: number;
  title: string;
  abstract_summary: string;
  group_name?: string | null;
  academic_year: string;
  session?: string | null;
  supervisor_name?: string | null;
  domain?: string | null;
  completion_percentage?: number | null;
  project_status?: string | null;
  source_batch_id?: string | null;
  source_row_number?: number | null;
  created_at: string;
  updated_at: string;
  source_metadata?: SourceMetadata;
  department_program?: string;
  project_scope?: string;
  completion_stage?: string;
  implemented_scope?: string;
  remaining_gaps?: string;
  future_work?: string;
  supervisor_display_reference?: string | null;
  group_members?: Array<{ name?: string; full_name?: string; registration_number?: string | null; email?: string | null; designation?: string | null }>;
};
type Page = { items: Project[]; page: number; page_size: number; total: number };

const fallbackFields: Array<[keyof Project, string]> = [
  ["title", "Project title"],
  ["abstract_summary", "Abstract / summary"],
  ["academic_year", "Academic year"],
  ["department_program", "Department / program"],
  ["project_scope", "Project scope"],
  ["completion_stage", "Completion stage"],
  ["implemented_scope", "Implemented scope"],
  ["remaining_gaps", "Remaining gaps"],
  ["future_work", "Future work"],
  ["supervisor_display_reference", "Supervisor"],
];

export function AdminArchiveProjects({ api }: { api: string }) {
  const [data, setData] = useState<Page>({ items: [], page: 1, page_size: 25, total: 0 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [editing, setEditing] = useState<Project | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [repairing, setRepairing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "25" });
      if (search.trim()) query.set("search", search.trim());
      const response = await fetch(`${api}/api/v1/admin/archive/projects?${query}`, { credentials: "include" });
      if (!response.ok) throw new Error("Archive projects could not be loaded.");
      setData(await response.json() as Page);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Archive projects could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [api, page, search]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const beginEdit = (project: Project) => {
    const source = project.source_metadata;
    if (source?.imported && source.columns?.length && source.cells) {
      setEditValues({ ...source.cells });
    } else {
      setEditValues(Object.fromEntries(fallbackFields.map(([key]) => [key, String(project[key] ?? "")])));
    }
    setEditing(project);
    setNotice("");
  };

  const saveEdit = async () => {
    if (!editing || saving) return;
    setSaving(true);
    setNotice("");
    const source = editing.source_metadata;
    const body = source?.imported && source.columns?.length ? { source_metadata: { ...source, cells: editValues } } : editValues;
    try {
      const response = await fetch(`${api}/api/v1/admin/archive/projects/${editing.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result?.detail?.message || "The archive project could not be updated.");
      setEditing(null);
      setNotice("Archive project updated.");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "The archive project could not be updated.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    const response = await fetch(`${api}/api/v1/admin/archive/projects/${deleteTarget.id}`, { method: "DELETE", credentials: "include" });
    if (!response.ok) {
      setNotice("The archive project could not be deleted.");
      setDeleting(false);
      return;
    }
    setDeleteTarget(null);
    setNotice("Archive project deleted.");
    await load();
    setDeleting(false);
  };

  const repairImported = async () => {
    if (repairing) return;
    setRepairing(true);
    try {
      const response = await fetch(`${api}/api/v1/admin/archive/projects/repair-imported`, { method: "POST", credentials: "include" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result?.detail?.message || "Imported archive repair failed.");
      setNotice(`Repair complete: ${result.merged_count ?? 0} duplicate project(s) merged${result.ambiguous_count ? `; ${result.ambiguous_count} ambiguous record(s) left unchanged.` : "."}`);
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Imported archive repair failed.");
    } finally {
      setRepairing(false);
    }
  };

  const columns = editing?.source_metadata?.imported && editing.source_metadata.columns?.length ? editing.source_metadata.columns : null;
  const isLong = (label: string) => /summary|scope|objective|method|description|problem|result|outcome/i.test(label);

  return <section aria-labelledby="archive-projects-heading">
    <OldProjectArchiveImport api={api} onImported={load} />
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div><h2 id="archive-projects-heading" className="text-xl font-bold">Archived projects</h2><p className="mt-1 text-sm text-[#60716b]">Each project title is one archive record with its related information grouped together.</p></div>
      <button type="button" disabled={repairing} onClick={() => void repairImported()} className="rounded-lg border border-[#cdd5ff] px-3 py-2 text-sm font-semibold text-[#354fe0] disabled:opacity-50">{repairing ? "Repairing…" : "Repair imported duplicates"}</button>
      <span className="text-sm text-[#60716b]">{data.total} total</span>
    </div>
    <form className="mb-4 flex gap-2" onSubmit={(event) => { event.preventDefault(); setPage(1); void load(); }}>
      <input className="w-full rounded-lg border border-[#cbd6d0] bg-white px-3 py-2 text-sm" placeholder="Search project title" value={search} onChange={(event) => setSearch(event.target.value)} />
      <button className="rounded-lg bg-[#176b66] px-4 py-2 text-sm font-semibold text-white">Search</button>
    </form>
    {notice && <p role="status" className="mb-4 rounded-lg bg-[#eef5ff] px-3 py-2 text-sm text-[#315db4]">{notice}</p>}
    {loading ? <p className="rounded-xl border border-[#dce4de] bg-white p-5 text-sm text-[#60716b]">Loading archived projects…</p> : !data.items.length ? <p className="rounded-xl border border-dashed border-[#cbd6d0] bg-white p-5 text-sm text-[#60716b]">No archived projects found.</p> : <div className="grid gap-3">
      {data.items.map((project) => {
        const open = expanded === project.id;
        const sourceColumns = project.source_metadata?.imported && project.source_metadata.columns?.length && project.source_metadata.cells ? project.source_metadata.columns : [];
        return <article key={project.id} className="rounded-xl border border-[#dce4de] bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <button type="button" className="flex min-w-0 items-start gap-2 text-left" onClick={() => setExpanded(open ? null : project.id)} aria-expanded={open}>
              <span className="mt-0.5 text-[#176b66]">{open ? "▼" : "▶"}</span>
              <span><strong className="block text-lg text-[#17324d]">{project.title}</strong><small className="text-[#60716b]">Project archive record · {project.source_metadata?.source_row_start ? `Excel rows ${project.source_metadata.source_row_start}-${project.source_metadata.source_row_end}` : project.source_row_number ? `Excel row ${project.source_row_number}` : "manual record"}</small></span>
            </button>
            <div className="flex gap-2"><button type="button" onClick={() => beginEdit(project)} className="rounded border border-[#cdd5ff] px-3 py-1.5 text-xs font-semibold text-[#354fe0]">Edit all</button><button type="button" onClick={() => setDeleteTarget(project)} className="rounded border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700">Delete</button></div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[['Group', project.group_name], ['Cycle', `${project.academic_year} · ${project.session || "—"}`], ['Supervisor', project.supervisor_name], ['Domain', project.domain], ['Members', String(project.group_members?.length ?? 0)], ['Completion', project.completion_percentage == null ? "—" : `${project.completion_percentage}%`], ['Status', project.project_status || project.completion_stage], ['Batch', project.source_batch_id ? `${project.source_batch_id.slice(0, 8)}${project.source_row_number ? ` · row ${project.source_row_number}` : ""}` : "—"]].map(([label, value]) => <div key={label} className="rounded-lg bg-[#f7faf8] px-3 py-2"><p className="text-[11px] font-bold uppercase tracking-wide text-[#60716b]">{label}</p><p className="mt-1 text-sm text-[#17324d]">{value || "—"}</p></div>)}
          </div>
          {open && <div className="mt-4 border-t border-[#e8ede9] pt-4"><h3 className="font-semibold text-[#17324d]">Project details</h3><p className="mt-2 whitespace-pre-wrap text-sm text-[#3f5363]">{project.abstract_summary || "No description supplied."}</p>{Boolean(project.group_members?.length) && <div className="mt-4"><h4 className="text-sm font-semibold text-[#17324d]">Members</h4><div className="mt-2 grid gap-2 sm:grid-cols-2">{project.group_members?.map((member, index) => <div key={`${member.email || member.registration_number || member.name}-${index}`} className="rounded-lg border border-[#e8ede9] px-3 py-2"><strong className="text-sm text-[#17324d]">{member.full_name || member.name}</strong><p className="text-xs text-[#60716b]">{member.designation || "Member"} · {member.registration_number || "No registration"} · {member.email || "No email"}</p></div>)}</div></div>}<p className="mt-2 text-xs text-[#60716b]">Created {new Date(project.created_at).toLocaleString()} · Updated {new Date(project.updated_at).toLocaleString()}</p>{sourceColumns.length > 0 && <div className="mt-4"><h4 className="text-sm font-semibold text-[#17324d]">Original Excel data</h4><div className="mt-2 grid gap-2 sm:grid-cols-2">{sourceColumns.map((column) => <div key={column.key} className="rounded-lg border border-[#e8ede9] px-3 py-2"><p className="text-[11px] font-bold uppercase tracking-wide text-[#60716b]">{column.label || column.key}</p><p className="mt-1 whitespace-pre-wrap text-sm text-[#17324d]">{project.source_metadata?.cells?.[column.key] || "—"}</p></div>)}</div></div>}</div>}
        </article>;
      })}
    </div>}
    {data.total > data.page_size && <div className="mt-4 flex items-center justify-between text-sm"><button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="rounded border px-3 py-2 disabled:opacity-50">Previous</button><span>Page {data.page}</span><button type="button" disabled={page * data.page_size >= data.total} onClick={() => setPage((value) => value + 1)} className="rounded border px-3 py-2 disabled:opacity-50">Next</button></div>}
    {editing && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditing(null); }}><div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="archive-edit-heading"><div className="flex items-start justify-between gap-4"><div><h2 id="archive-edit-heading" className="text-xl font-bold text-slate-900">Edit archived project</h2><p className="mt-1 text-sm text-slate-500">Every imported Excel column is editable. Blank values remain blank.</p></div><button type="button" className="text-2xl leading-none text-slate-500" onClick={() => setEditing(null)} aria-label="Close">×</button></div><div className="mt-5 grid gap-4 sm:grid-cols-2">{(columns ? columns.map((column) => [column.key, column.label || column.key] as [string, string]) : fallbackFields.map(([key, label]) => [String(key), label] as [string, string])).map(([key, label]) => <label key={key} className="grid gap-1 text-sm font-semibold text-slate-700"><span>{label}</span>{isLong(label) ? <textarea rows={3} className="rounded-lg border border-slate-300 px-3 py-2 font-normal" value={editValues[key] ?? ""} onChange={(event) => setEditValues({ ...editValues, [key]: event.target.value })} /> : <input className="rounded-lg border border-slate-300 px-3 py-2 font-normal" value={editValues[key] ?? ""} onChange={(event) => setEditValues({ ...editValues, [key]: event.target.value })} />}</label>)}</div><div className="mt-6 flex justify-end gap-2"><button type="button" className="rounded-lg border border-slate-300 px-4 py-2 font-semibold" onClick={() => setEditing(null)}>Cancel</button><button type="button" disabled={saving} className="rounded-lg bg-[#4663ff] px-4 py-2 font-semibold text-white disabled:opacity-50" onClick={() => void saveEdit()}>{saving ? "Saving…" : "Save changes"}</button></div></div></div>}
    {deleteTarget && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !deleting) setDeleteTarget(null); }}><div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="archive-delete-heading"><h2 id="archive-delete-heading" className="text-lg font-bold text-slate-900">Delete archived project?</h2><p className="mt-2 text-sm text-slate-600">This will permanently remove <strong>{deleteTarget.title}</strong> and its archive record.</p><div className="mt-6 flex justify-end gap-2"><button type="button" disabled={deleting} className="rounded-lg border border-slate-300 px-4 py-2 font-semibold" onClick={() => setDeleteTarget(null)}>Cancel</button><button type="button" disabled={deleting} className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white disabled:opacity-50" onClick={() => void remove()}>{deleting ? "Deleting…" : "Delete permanently"}</button></div></div></div>}
  </section>;
}
