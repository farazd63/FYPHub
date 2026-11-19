import { useCallback, useEffect, useMemo, useState } from "react";

type Cycle = { id: number; code: string; name: string; display_name: string; group_count?: number; requirement_count?: number; submission_count?: number };
type Member = { id: number; name: string; registration_number?: string | null; email?: string | null; designation?: string | null };
type Person = { id: number; name: string; email?: string | null; registration_number?: string | null } | null;
type Group = {
  id: number; group_id: number; cycle_id: number; cycle_name: string; group_code: string; project_title?: string | null;
  project?: { id: number; title?: string | null; status?: string | null } | null; members: Member[]; supervisor: Person;
  completion_percentage: number; last_submission_at?: string | null; requirement_count: number; submitted_requirement_count: number; status: string;
};
type Version = { id: number; version_number: number; original_filename: string; mime_type: string; file_size: number; uploaded_at: string; uploaded_by_id?: number | null; view_url?: string | null; download_url?: string | null };
type ReviewEvent = { id: number; status: string; reviewer?: Person; reviewed_at?: string | null; comment?: string | null; version_id?: number | null };
type ArchiveRow = {
  id: number; cycle_id: number; cycle_name: string; group_id: number; group_code: string; project_id?: number | null; project_title?: string | null;
  requirement_section_id?: number | null; requirement_section: string; requirement_id: number; requirement_name: string; student_id?: number | null;
  student_name?: string | null; registration_number?: string | null; uploader_id?: number | null; uploader_name?: string | null;
  submission_id?: number | null; submitted_file_name?: string | null; submitted_at?: string | null; version_number?: number | null;
  current_status: string; reviewer?: Person; reviewer_name?: string | null; reviewed_at?: string | null; reviewer_comments?: string | null;
  latest_version_id?: number | null; view_url?: string | null; download_url?: string | null; versions: Version[]; review_history: ReviewEvent[];
  requirement_status: string; is_required: boolean; due_at: string;
};
type Archive = Group & { requirements: ArchiveRow[]; total_requirements: number; filtered_requirements: number; member_user_ids: number[] };
type Filters = { search: string; section: string; status: string; student: string; requirement: string; date_from: string; date_to: string };
type Preview = { url: string; title: string; pageCount: number; error?: string };

const emptyFilters: Filters = { search: "", section: "", status: "", student: "", requirement: "", date_from: "", date_to: "" };
const statuses = ["NOT_SUBMITTED", "DRAFT", "SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED", "ACCEPTED", "REJECTED", "CLOSED"];

const errorText = (body: unknown, fallback: string) => {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  return typeof detail === "string" ? detail : fallback;
};

const dateText = (value?: string | null) => value ? new Date(value).toLocaleString() : "Not submitted";
const display = (value?: string | null, fallback = "Not assigned") => value && value.trim() ? value : fallback;
const statusLabel = (value: string) => ({
  NOT_SUBMITTED: "Not submitted", DRAFT: "Draft", SUBMITTED: "Submitted", UNDER_REVIEW: "Under review",
  CHANGES_REQUESTED: "Changes requested", ACCEPTED: "Accepted", REJECTED: "Rejected", CLOSED: "Closed",
}[value] || value);
const statusClass = (value: string) => ({
  NOT_SUBMITTED: "bg-slate-100 text-slate-600", DRAFT: "bg-slate-100 text-slate-700", SUBMITTED: "bg-blue-100 text-blue-700",
  UNDER_REVIEW: "bg-amber-100 text-amber-800", CHANGES_REQUESTED: "bg-orange-100 text-orange-800", ACCEPTED: "bg-emerald-100 text-emerald-800",
  REJECTED: "bg-red-100 text-red-700", CLOSED: "bg-slate-200 text-slate-700",
}[value] || "bg-slate-100 text-slate-700");

async function readJson(response: Response) {
  return response.json().catch(() => ({})) as Promise<unknown>;
}

export function AdminDocumentArchive({ api }: { api: string }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [archive, setArchive] = useState<Archive | null>(null);
  const [cycleState, setCycleState] = useState<"loading" | "ready" | "error">("loading");
  const [groupState, setGroupState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [detailState, setDetailState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(emptyFilters);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [module, setModule] = useState("General");
  const [format, setFormat] = useState("pdf");
  const [maxSize, setMaxSize] = useState("10");
  const [required, setRequired] = useState(true);

  const selectedCycle = useMemo(() => cycles.find((cycle) => cycle.id === selectedCycleId) || null, [cycles, selectedCycleId]);

  const loadCycles = useCallback(async () => {
    setCycleState("loading");
    try {
      const response = await fetch(`${api}/api/v1/admin/document-archive/cycles`, { credentials: "include" });
      const body = await readJson(response);
      if (!response.ok) throw new Error(errorText(body, "Academic cycles could not be loaded."));
      setCycles(Array.isArray(body) ? body as Cycle[] : []);
      setCycleState("ready");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Academic cycles could not be loaded.");
      setCycleState("error");
    }
  }, [api]);

  const loadGroups = useCallback(async (cycleId: number) => {
    setGroupState("loading");
    try {
      const response = await fetch(`${api}/api/v1/admin/document-archive/cycles/${cycleId}/groups`, { credentials: "include" });
      const body = await readJson(response);
      if (!response.ok) throw new Error(errorText(body, "Groups could not be loaded."));
      setGroups(body && typeof body === "object" && Array.isArray((body as { groups?: unknown }).groups) ? (body as { groups: Group[] }).groups : []);
      setGroupState("ready");
    } catch (error) {
      setGroups([]);
      setNotice(error instanceof Error ? error.message : "Groups could not be loaded.");
      setGroupState("error");
    }
  }, [api]);

  const loadArchive = useCallback(async (cycleId: number, groupId: number, nextFilters: Filters = appliedFilters) => {
    setDetailState("loading");
    const query = new URLSearchParams();
    Object.entries(nextFilters).forEach(([key, value]) => { if (value.trim()) query.set(key, value.trim()); });
    try {
      const suffix = query.toString() ? `?${query.toString()}` : "";
      const response = await fetch(`${api}/api/v1/admin/document-archive/cycles/${cycleId}/groups/${groupId}${suffix}`, { credentials: "include" });
      const body = await readJson(response);
      if (!response.ok) throw new Error(errorText(body, "The group archive could not be loaded."));
      setArchive((body && typeof body === "object" && "group" in body ? (body as { group: Archive }).group : body) as Archive);
      setDetailState("ready");
    } catch (error) {
      setArchive(null);
      setNotice(error instanceof Error ? error.message : "The group archive could not be loaded.");
      setDetailState("error");
    }
  }, [api, appliedFilters]);

  useEffect(() => { const timer = window.setTimeout(() => { void loadCycles(); }, 0); return () => window.clearTimeout(timer); }, [loadCycles]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (selectedCycleId === null) { setGroups([]); setSelectedGroupId(null); setArchive(null); setGroupState("idle"); setDetailState("idle"); return; }
      setSelectedGroupId(null); setArchive(null); setAppliedFilters(emptyFilters); setFilters(emptyFilters); void loadGroups(selectedCycleId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadGroups, selectedCycleId]);
  useEffect(() => { const timer = window.setTimeout(() => { if (selectedCycleId !== null && selectedGroupId !== null) void loadArchive(selectedCycleId, selectedGroupId); }, 0); return () => window.clearTimeout(timer); }, [loadArchive, selectedCycleId, selectedGroupId]);
  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview?.url]);

  const selectCycle = (value: string) => { setNotice(""); setSelectedCycleId(value ? Number(value) : null); };
  const openGroup = (groupId: number) => { setNotice(""); setSelectedGroupId(groupId); };
  const submitFilters = (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); setAppliedFilters(filters); if (selectedCycleId !== null && selectedGroupId !== null) void loadArchive(selectedCycleId, selectedGroupId, filters); };
  const resetFilters = () => { setFilters(emptyFilters); setAppliedFilters(emptyFilters); if (selectedCycleId !== null && selectedGroupId !== null) void loadArchive(selectedCycleId, selectedGroupId, emptyFilters); };

  const download = async (row: ArchiveRow, version = row.latest_version_id ? row.versions.find((item) => item.id === row.latest_version_id) : row.versions[row.versions.length - 1]) => {
    if (!version?.download_url) return;
    setBusy(`download-${version.id}`); setNotice("");
    try {
      const response = await fetch(`${api}${version.download_url}`, { credentials: "include" });
      if (!response.ok) throw new Error("The document could not be downloaded.");
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
      link.href = url; link.download = version.original_filename; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (error) { setNotice(error instanceof Error ? error.message : "The document could not be downloaded."); }
    finally { setBusy(null); }
  };

  const openPreview = async (row: ArchiveRow, version = row.latest_version_id ? row.versions.find((item) => item.id === row.latest_version_id) : row.versions[row.versions.length - 1]) => {
    if (!version?.view_url) return;
    if (preview?.url) URL.revokeObjectURL(preview.url);
    setBusy(`preview-${version.id}`); setPreview({ url: "", title: version.original_filename, pageCount: 1 });
    try {
      const response = await fetch(`${api}${version.view_url}`, { credentials: "include" });
      if (!response.ok) throw new Error("The document could not be previewed.");
      setPreview({ url: URL.createObjectURL(await response.blob()), title: version.original_filename, pageCount: Number(response.headers.get("X-Preview-Page-Count")) || 1 });
    } catch (error) { setPreview({ url: "", title: version.original_filename, pageCount: 1, error: error instanceof Error ? error.message : "The document could not be previewed." }); }
    finally { setBusy(null); }
  };

  const review = async (row: ArchiveRow, action: "approve" | "under-review" | "request-changes" | "request-replacement" | "reject") => {
    if (!row.submission_id) return;
    const comment = action === "reject" || action === "request-changes" || action === "request-replacement" ? window.prompt(action === "reject" ? "Reason for rejection (optional):" : "Changes requested (optional):", "") : null;
    if (comment === null && (action === "reject" || action === "request-changes" || action === "request-replacement")) return;
    setBusy(`review-${row.submission_id}`); setNotice("");
    try {
      const query = comment ? `?comment=${encodeURIComponent(comment)}` : "";
      const response = await fetch(`${api}/api/v1/document-requirements/${row.requirement_id}/submissions/${row.submission_id}/${action}${query}`, { method: "POST", credentials: "include" });
      const body = await readJson(response);
      if (!response.ok) throw new Error(errorText(body, "The review action could not be completed."));
      setNotice(`Document marked ${action === "under-review" ? "under review" : action === "request-changes" || action === "request-replacement" ? "changes requested" : action === "approve" ? "accepted" : "rejected"}.`);
      if (selectedCycleId !== null && selectedGroupId !== null) await loadArchive(selectedCycleId, selectedGroupId, appliedFilters);
    } catch (error) { setNotice(error instanceof Error ? error.message : "The review action could not be completed."); }
    finally { setBusy(null); }
  };

  const createRequirement = async (publish: boolean) => {
    if (selectedCycleId === null || !title.trim() || !deadline) { setNotice("Select a cycle and provide a title and deadline."); return; }
    setBusy("create"); setNotice("");
    try {
      const response = await fetch(`${api}/api/v1/document-requirements`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        title: title.trim(), description: description.trim() || null, academic_cycle_id: selectedCycleId, module: module.trim() || "General", allowed_file_types: [format], max_file_size_mb: Number(maxSize), is_required: required, due_at: new Date(deadline).toISOString(),
      }) });
      const body = await readJson(response);
      if (!response.ok) throw new Error(errorText(body, "The requirement could not be created."));
      if (publish && body && typeof body === "object" && typeof (body as { id?: unknown }).id === "number") {
        const publishResponse = await fetch(`${api}/api/v1/document-requirements/${(body as { id: number }).id}/publish`, { method: "POST", credentials: "include" });
        if (!publishResponse.ok) throw new Error(errorText(await readJson(publishResponse), "The requirement was created but could not be published."));
      }
      setTitle(""); setDescription(""); setDeadline(""); setNotice(publish ? "Requirement published." : "Requirement saved as draft.");
      await loadCycles(); await loadGroups(selectedCycleId);
      if (selectedGroupId !== null) await loadArchive(selectedCycleId, selectedGroupId, appliedFilters);
    } catch (error) { setNotice(error instanceof Error ? error.message : "The requirement could not be created."); }
    finally { setBusy(null); }
  };

  return <section aria-label="Document Submission Archive" className="mx-auto w-full max-w-[1500px]">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#3567d6]">Requirements &amp; Review</p><h1 className="text-3xl font-bold text-[#17324d]">Document Submission Archive</h1><p className="mt-1 text-sm text-slate-600">Browse every requirement by academic cycle, group, project, student, version, and review history.</p></div><label className="grid min-w-[260px] gap-1 text-sm font-semibold text-[#17324d]">Academic cycle<select value={selectedCycleId ?? ""} onChange={(event) => selectCycle(event.target.value)} className="rounded-lg border border-[#cbd6d0] bg-white px-3 py-2"><option value="">Select a cycle</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name || cycle.name} ({cycle.code})</option>)}</select></label></div>
    {notice && <p role="status" className="mt-4 rounded-lg border border-[#cddaf7] bg-[#f6f8ff] px-3 py-2 text-sm text-[#315db4]">{notice}</p>}
    {cycleState === "loading" && <p className="mt-6 rounded-xl border bg-white p-5 text-sm">Loading academic cycles...</p>}
    {cycleState === "error" && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">Academic cycles could not be loaded.</p>}
    {cycleState === "ready" && selectedCycleId === null && <div className="mt-6 rounded-xl border border-dashed border-[#cbd6d0] bg-white p-8 text-center text-sm text-slate-600">Select an academic cycle to view only its groups and document archive.</div>}
    {selectedCycle && <>
      <section className="mt-6 rounded-xl border border-[#dce4de] bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Selected cycle</p><h2 className="text-xl font-bold text-[#17324d]">{selectedCycle.display_name || selectedCycle.name}</h2><p className="text-sm text-slate-600">{selectedCycle.code}</p></div><button type="button" onClick={() => setShowCreate((value) => !value)} className="rounded-lg border border-[#315db4] px-3 py-2 text-sm font-semibold text-[#315db4]">{showCreate ? "Hide requirement form" : "Create requirement"}</button></div>
        {showCreate && <div className="mt-5 grid gap-4 border-t pt-5"><h3 className="text-lg font-semibold">Create requirement for this cycle</h3><label className="grid gap-1 text-sm">Requirement name<input value={title} onChange={(event) => setTitle(event.target.value)} className="rounded border p-3" /></label><label className="grid gap-1 text-sm">Requirement section<input value={module} onChange={(event) => setModule(event.target.value)} className="rounded border p-3" /></label><label className="grid gap-1 text-sm">Instructions<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} className="rounded border p-3" /></label><label className="grid gap-1 text-sm">Deadline<input type="datetime-local" value={deadline} onChange={(event) => setDeadline(event.target.value)} className="rounded border p-3" /></label><div className="grid gap-3 sm:grid-cols-3"><label className="grid gap-1 text-sm">File format<select value={format} onChange={(event) => setFormat(event.target.value)} className="rounded border p-3"><option value="pdf">PDF</option><option value="doc">DOC</option><option value="docx">DOCX</option><option value="txt">TXT</option><option value="zip">ZIP</option></select></label><label className="grid gap-1 text-sm">Max size (MB)<input type="number" min="1" max="100" value={maxSize} onChange={(event) => setMaxSize(event.target.value)} className="rounded border p-3" /></label><label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} /> Required</label></div><div className="flex flex-wrap gap-2"><button type="button" disabled={busy !== null} onClick={() => void createRequirement(false)} className="rounded bg-[#315db4] px-4 py-2 font-semibold text-white">Save draft</button><button type="button" disabled={busy !== null} onClick={() => void createRequirement(true)} className="rounded bg-[#176b66] px-4 py-2 font-semibold text-white">Publish requirement</button></div></div>}
      </section>
      {groupState === "loading" && <p className="mt-6 rounded-xl border bg-white p-5 text-sm">Loading groups for {selectedCycle.display_name || selectedCycle.name}...</p>}
      {groupState === "error" && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">Groups could not be loaded.</p>}
      {groupState === "ready" && !groups.length && <p className="mt-6 rounded-xl border border-dashed bg-white p-6 text-sm text-slate-600">This academic cycle has no groups.</p>}
      {groupState === "ready" && groups.length > 0 && <section className="mt-6 rounded-xl border border-[#dce4de] bg-white p-5"><h2 className="text-lg font-semibold">Groups in {selectedCycle.display_name || selectedCycle.name}</h2><div className="mt-4 overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-sm"><thead className="border-b text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-3">Group code</th><th className="px-3 py-3">Project title</th><th className="px-3 py-3">Members</th><th className="px-3 py-3">Supervisor</th><th className="px-3 py-3">Completion</th><th className="px-3 py-3">Last submission</th><th className="px-3 py-3">Action</th></tr></thead><tbody className="divide-y">{groups.map((group) => <tr key={group.group_id}><td className="px-3 py-3 font-semibold">{group.group_code}</td><td className="px-3 py-3">{display(group.project_title || group.project?.title, "No project assigned")}</td><td className="px-3 py-3">{group.members.length ? group.members.map((member) => <span key={member.id} className="mr-1 inline-block rounded bg-slate-100 px-2 py-1 text-xs">{member.name}</span>) : "No members"}</td><td className="px-3 py-3">{display(group.supervisor?.name)}</td><td className="px-3 py-3"><span className="font-semibold">{group.completion_percentage}%</span><span className="ml-1 text-xs text-slate-500">({group.submitted_requirement_count}/{group.requirement_count})</span></td><td className="px-3 py-3">{dateText(group.last_submission_at)}</td><td className="px-3 py-3"><button type="button" onClick={() => openGroup(group.group_id)} className="rounded border border-[#315db4] px-3 py-2 text-xs font-semibold text-[#315db4]">Open archive</button></td></tr>)}</tbody></table></div></section>}
      {selectedGroupId !== null && <section className="mt-6 rounded-xl border border-[#dce4de] bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Group archive</p><h2 className="text-xl font-bold text-[#17324d]">{archive?.group_code || groups.find((item) => item.group_id === selectedGroupId)?.group_code}</h2><p className="text-sm text-slate-600">{display(archive?.project_title || archive?.project?.title, "No project assigned")} · {display(archive?.supervisor?.name, "No supervisor assigned")}</p></div><button type="button" onClick={() => { setSelectedGroupId(null); setArchive(null); }} className="rounded-lg border px-3 py-2 text-sm font-semibold">Back to groups</button></div>
        {detailState === "loading" && <p className="mt-5 text-sm text-slate-600">Loading group archive...</p>}
        {detailState === "error" && <p role="alert" className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-700">The group archive could not be loaded.</p>}
        {detailState === "ready" && archive && <><div className="mt-5 grid gap-3 sm:grid-cols-4"><div className="rounded-lg bg-slate-50 p-3"><span className="block text-xs uppercase text-slate-500">Cycle</span><strong>{archive.cycle_name}</strong></div><div className="rounded-lg bg-slate-50 p-3"><span className="block text-xs uppercase text-slate-500">Project</span><strong>{display(archive.project_title || archive.project?.title, "No project assigned")}</strong></div><div className="rounded-lg bg-slate-50 p-3"><span className="block text-xs uppercase text-slate-500">Members</span><strong>{archive.members.length}</strong></div><div className="rounded-lg bg-slate-50 p-3"><span className="block text-xs uppercase text-slate-500">Completion</span><strong>{archive.completion_percentage}%</strong></div></div><form onSubmit={submitFilters} className="mt-5 grid gap-3 rounded-lg border bg-slate-50 p-4 sm:grid-cols-2 lg:grid-cols-4"><label className="grid gap-1 text-xs font-semibold">Search<input value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} placeholder="Group, project, student, file..." className="rounded border bg-white p-2 text-sm font-normal" /></label><label className="grid gap-1 text-xs font-semibold">Section<input value={filters.section} onChange={(event) => setFilters({ ...filters, section: event.target.value })} className="rounded border bg-white p-2 text-sm font-normal" /></label><label className="grid gap-1 text-xs font-semibold">Requirement<input value={filters.requirement} onChange={(event) => setFilters({ ...filters, requirement: event.target.value })} className="rounded border bg-white p-2 text-sm font-normal" /></label><label className="grid gap-1 text-xs font-semibold">Student / registration<input value={filters.student} onChange={(event) => setFilters({ ...filters, student: event.target.value })} className="rounded border bg-white p-2 text-sm font-normal" /></label><label className="grid gap-1 text-xs font-semibold">Status<select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })} className="rounded border bg-white p-2 text-sm font-normal"><option value="">All statuses</option>{statuses.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</select></label><label className="grid gap-1 text-xs font-semibold">From<input type="date" value={filters.date_from} onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} className="rounded border bg-white p-2 text-sm font-normal" /></label><label className="grid gap-1 text-xs font-semibold">To<input type="date" value={filters.date_to} onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} className="rounded border bg-white p-2 text-sm font-normal" /></label><div className="flex items-end gap-2"><button type="submit" className="rounded bg-[#315db4] px-3 py-2 text-sm font-semibold text-white">Apply filters</button><button type="button" onClick={resetFilters} className="rounded border px-3 py-2 text-sm font-semibold">Reset</button></div></form><p className="mt-4 text-sm text-slate-600">Showing {archive.filtered_requirements} of {archive.total_requirements} requirements.</p><div className="mt-3 overflow-x-auto"><table className="w-full min-w-[1900px] text-left text-xs"><thead className="border-b bg-slate-50 uppercase tracking-wide text-slate-500"><tr><th className="px-2 py-3">Cycle</th><th className="px-2 py-3">Group</th><th className="px-2 py-3">Project</th><th className="px-2 py-3">Section</th><th className="px-2 py-3">Requirement</th><th className="px-2 py-3">Student / uploader</th><th className="px-2 py-3">Registration</th><th className="px-2 py-3">File</th><th className="px-2 py-3">Submitted</th><th className="px-2 py-3">Version</th><th className="px-2 py-3">Status</th><th className="px-2 py-3">Reviewer</th><th className="px-2 py-3">Review date</th><th className="px-2 py-3">Comments</th><th className="px-2 py-3">Actions</th></tr></thead><tbody className="divide-y">{archive.requirements.map((row) => <tr key={row.id} className="align-top"><td className="px-2 py-3">{row.cycle_name}</td><td className="px-2 py-3 font-semibold">{row.group_code}</td><td className="px-2 py-3">{display(row.project_title, "No project")}</td><td className="px-2 py-3">{row.requirement_section}</td><td className="px-2 py-3"><strong>{row.requirement_name}</strong><span className="block text-slate-500">{row.is_required ? "Required" : "Optional"}</span></td><td className="px-2 py-3">{display(row.student_name, "Not submitted")}<span className="block text-slate-500">Uploader: {display(row.uploader_name, "-")}</span></td><td className="px-2 py-3">{display(row.registration_number, "-")}</td><td className="px-2 py-3">{display(row.submitted_file_name, "No file")}</td><td className="px-2 py-3">{dateText(row.submitted_at)}</td><td className="px-2 py-3">{row.version_number ? `v${row.version_number}` : "-"}</td><td className="px-2 py-3"><span className={`inline-flex rounded-full px-2 py-1 font-semibold ${statusClass(row.current_status)}`}>{statusLabel(row.current_status)}</span></td><td className="px-2 py-3">{display(row.reviewer_name || row.reviewer?.name, "-")}</td><td className="px-2 py-3">{row.reviewed_at ? dateText(row.reviewed_at) : "-"}</td><td className="max-w-[220px] whitespace-pre-wrap px-2 py-3">{display(row.reviewer_comments, "-")}</td><td className="px-2 py-3"><div className="flex min-w-[230px] flex-wrap gap-1">{row.submission_id && row.versions.length > 0 && <><button type="button" disabled={busy !== null} onClick={() => void openPreview(row)} className="rounded border border-[#315db4] px-2 py-1 font-semibold text-[#315db4]">View</button><button type="button" disabled={busy !== null} onClick={() => void download(row)} className="rounded border border-[#315db4] px-2 py-1 font-semibold text-[#315db4]">Download</button></>}{row.submission_id && <><button type="button" disabled={busy !== null} onClick={() => void review(row, "under-review")} className="rounded border px-2 py-1">Under review</button><button type="button" disabled={busy !== null} onClick={() => void review(row, "approve")} className="rounded border border-emerald-300 px-2 py-1 text-emerald-700">Approve</button><button type="button" disabled={busy !== null} onClick={() => void review(row, "request-replacement")} className="rounded border border-amber-300 px-2 py-1 text-amber-800">Request changes</button><button type="button" disabled={busy !== null} onClick={() => void review(row, "reject")} className="rounded border border-red-300 px-2 py-1 text-red-700">Reject</button></>}</div>{row.versions.length > 1 && <details className="mt-2 rounded border bg-slate-50 p-2"><summary className="cursor-pointer font-semibold">Version history ({row.versions.length})</summary><div className="mt-2 grid gap-1">{row.versions.slice(0, -1).reverse().map((version) => <div key={version.id} className="flex items-center justify-between gap-2"><span>v{version.version_number} · {version.original_filename}</span><span className="flex gap-1"><button type="button" onClick={() => void openPreview(row, version)} className="underline">View</button><button type="button" onClick={() => void download(row, version)} className="underline">Download</button></span></div>)}</div></details>}</td></tr>)}</tbody></table></div></>}
        {archive && archive.requirements.some((row) => row.review_history.length > 0) && <section className="mt-6 rounded-lg border bg-slate-50 p-4"><h3 className="font-semibold">Review history</h3><div className="mt-3 grid gap-3">{archive.requirements.map((row) => row.review_history.length ? <article key={`history-${row.id}`} className="rounded border bg-white p-3 text-sm"><strong>{row.requirement_name}</strong><div className="mt-2 grid gap-2">{row.review_history.map((event) => <div key={event.id}><strong>{statusLabel(event.status)}</strong> · {display(event.reviewer?.name, "Reviewer")} · {event.reviewed_at ? dateText(event.reviewed_at) : "No date"}{event.comment && <p className="text-slate-600">{event.comment}</p>}</div>)}</div></article> : null)}</div></section>}
      </section>}
    </>}
    {preview && <div role="dialog" aria-modal="true" aria-label={`Preview ${preview.title}`} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4"><div className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"><div className="flex items-center justify-between gap-3 border-b p-4"><div><h2 className="font-semibold">{preview.title}</h2><p className="text-xs text-slate-500">Inline document preview · Download is a separate action.</p></div><button type="button" onClick={() => { if (preview.url) URL.revokeObjectURL(preview.url); setPreview(null); }} className="rounded bg-slate-800 px-3 py-2 text-sm font-semibold text-white">Close</button></div><div className="min-h-0 flex-1 bg-slate-100 p-3">{preview.error ? <p role="alert" className="p-6 text-sm text-red-700">{preview.error}</p> : preview.url ? <iframe title={`Preview of ${preview.title}`} src={`${preview.url}#page=1`} className="h-full w-full rounded border bg-white" /> : <p className="p-6 text-sm">Generating preview...</p>}</div></div></div>}
  </section>;
}
