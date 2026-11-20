import { useEffect, useMemo, useState } from "react";
import { StatusBadge } from "./ui";

type Cycle = { id: number; code: string; display_name: string; academic_year?: number | null; session?: string | null };
type Member = { id: number; full_name: string; registration_number: string; email: string | null; designation?: string };
type Group = { id: number; group_number?: number | null; group_name: string; group_email: string; academic_cycle_id: number; academic_cycle?: string | null; status: string; is_active: boolean; project?: { title?: string | null } | null; supervisor?: { name?: string | null } | null; members: Member[] };
type Version = { id: number; version_number: number; original_filename: string; uploaded_at: string };
type ReviewEvent = { id: number; status: string; reviewer?: { name?: string | null } | null; reviewed_at?: string | null; comment?: string | null };
type Requirement = { id: number; requirement_name: string; requirement_section?: string | null; is_required: boolean; current_status: string; submitted_file_name?: string | null; submitted_at?: string | null; versions: Version[]; review_history: ReviewEvent[] };
type GroupArchive = { id: number; group_id: number; cycle_id: number; group_code: string; project_title?: string | null; project?: { title?: string | null } | null; members: Array<{ id: number; name: string; registration_number?: string | null; email?: string | null; designation?: string | null }>; supervisor?: { name?: string | null } | null; requirements: Requirement[] };
type ErrorBody = { detail?: string | { message?: string } };
type LoadState = "idle" | "loading" | "ready" | "error";

const readPositiveId = (name: string) => {
  const value = Number(new URLSearchParams(window.location.search).get(name));
  return Number.isInteger(value) && value > 0 ? value : null;
};

const writeSelection = (cycleId: number | null, groupId: number | null = null) => {
  const url = new URL(window.location.href);
  if (cycleId === null) {
    url.searchParams.delete("cycle_id");
    url.searchParams.delete("group_id");
  } else {
    url.searchParams.set("cycle_id", String(cycleId));
    if (groupId === null) url.searchParams.delete("group_id");
    else url.searchParams.set("group_id", String(groupId));
  }
  window.history.replaceState({ adminPage: "studentGroups", cycleId, groupId }, "", `${url.pathname}${url.search}${url.hash}`);
};

const errorText = (body: unknown, fallback: string) => {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as ErrorBody).detail;
  return typeof detail === "string" ? detail : detail?.message || fallback;
};

const display = (value: unknown, fallback = "Not assigned") => value === null || value === undefined || String(value).trim() === "" ? fallback : String(value);

export function groupsForCycle(groups: Group[], selectedCycleId: number) {
  return groups.filter((group) => group.academic_cycle_id === selectedCycleId);
}

export function AdminStudentGroups({ api }: { api: string }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [archive, setArchive] = useState<GroupArchive | null>(null);
  const [cycleState, setCycleState] = useState<LoadState>("loading");
  const [groupState, setGroupState] = useState<LoadState>("idle");
  const [detailState, setDetailState] = useState<LoadState>("idle");
  const [notice, setNotice] = useState("");
  const [cycleError, setCycleError] = useState("");
  const [groupError, setGroupError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);
  const [confirm, setConfirm] = useState<{ group: Group; action: "activate" | "deactivate" | "delete" } | null>(null);
  const [busy, setBusy] = useState(false);

  const selectedCycle = useMemo(() => cycles.find((cycle) => cycle.id === selectedCycleId) ?? null, [cycles, selectedCycleId]);
  const selectedGroup = useMemo(() => groups.find((group) => group.id === selectedGroupId) ?? null, [groups, selectedGroupId]);

  useEffect(() => {
    const controller = new AbortController();
    const loadCycles = async () => {
      setCycleState("loading");
      setCycleError("");
      try {
        const response = await fetch(`${api}/api/v1/academic-cycles`, { credentials: "include", signal: controller.signal });
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(errorText(body, "FYP cycles could not be loaded."));
        const available = Array.isArray(body) ? body as Cycle[] : [];
        setCycles(available);
        const requestedCycleId = readPositiveId("cycle_id");
        if (requestedCycleId !== null && available.some((cycle) => cycle.id === requestedCycleId)) setSelectedCycleId(requestedCycleId);
        else {
          setSelectedCycleId(null);
          if (requestedCycleId !== null) writeSelection(null);
        }
        setCycleState("ready");
      } catch (error) {
        if (!controller.signal.aborted) {
          setCycleState("error");
          setCycleError(error instanceof Error ? error.message : "FYP cycles could not be loaded.");
        }
      }
    };
    void loadCycles();
    return () => controller.abort();
  }, [api]);

  useEffect(() => {
    if (selectedCycleId === null) {
      const reset = window.setTimeout(() => {
        setGroups([]); setSelectedGroupId(null); setArchive(null); setGroupState("idle"); setDetailState("idle");
      }, 0);
      return () => window.clearTimeout(reset);
    }
    const controller = new AbortController();
    const loadGroups = async () => {
      setGroupState("loading"); setGroupError(""); setGroups([]); setSelectedGroupId(null); setArchive(null); setDetailState("idle");
      try {
        const query = new URLSearchParams({ cycle_id: String(selectedCycleId) });
        const response = await fetch(`${api}/api/v1/admin/student-groups?${query.toString()}`, { credentials: "include", signal: controller.signal });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(errorText(body, "Groups for this cycle could not be loaded."));
        const items = body && typeof body === "object" && Array.isArray((body as { items?: unknown }).items) ? (body as { items: Group[] }).items : [];
        setGroups(groupsForCycle(items, selectedCycleId));
        setGroupState("ready");
      } catch (error) {
        if (!controller.signal.aborted) {
          setGroupState("error");
          setGroupError(error instanceof Error ? error.message : "Groups for this cycle could not be loaded.");
        }
      }
    };
    void loadGroups();
    return () => controller.abort();
  }, [api, reloadToken, selectedCycleId]);

  useEffect(() => {
    if (selectedCycleId === null || groupState !== "ready") return;
    const requestedGroupId = readPositiveId("group_id");
    if (requestedGroupId !== null && groups.some((group) => group.id === requestedGroupId)) {
      const select = window.setTimeout(() => setSelectedGroupId(requestedGroupId), 0);
      return () => window.clearTimeout(select);
    }
    if (requestedGroupId !== null) writeSelection(selectedCycleId);
  }, [groupState, groups, selectedCycleId]);

  useEffect(() => {
    if (selectedCycleId === null || selectedGroupId === null) return;
    const controller = new AbortController();
    const loadDetail = async () => {
      setDetailState("loading");
      setDetailError("");
      try {
        const response = await fetch(`${api}/api/v1/admin/document-archive/cycles/${selectedCycleId}/groups/${selectedGroupId}`, { credentials: "include", signal: controller.signal });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(errorText(body, "The selected group details could not be loaded."));
        const result = body as { cycle?: { id?: number }; group?: GroupArchive };
        if (result.cycle?.id !== selectedCycleId || result.group?.cycle_id !== selectedCycleId || result.group.group_id !== selectedGroupId) throw new Error("The selected group does not belong to the selected cycle.");
        setArchive(result.group); setDetailState("ready");
      } catch (error) {
        if (!controller.signal.aborted) {
          setArchive(null); setDetailState("error"); setDetailError(error instanceof Error ? error.message : "The selected group details could not be loaded.");
        }
      }
    };
    void loadDetail();
    return () => controller.abort();
  }, [api, selectedCycleId, selectedGroupId]);

  const selectCycle = (cycleId: number | null) => {
    setNotice(""); setCycleError(""); setGroupError(""); setDetailError("");
    setSelectedCycleId(cycleId); setSelectedGroupId(null); setArchive(null); writeSelection(cycleId);
  };

  const openGroup = (groupId: number) => {
    if (selectedCycleId === null || !groups.some((group) => group.id === groupId)) return;
    setNotice(""); setDetailError(""); setSelectedGroupId(groupId); writeSelection(selectedCycleId, groupId);
  };

  const mutate = async () => {
    if (!confirm || busy) return;
    const { group, action } = confirm;
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${api}/api/v1/admin/student-groups/${group.id}${action === "delete" ? "" : `/${action}`}`, { method: action === "delete" ? "DELETE" : "PATCH", credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) { setNotice(errorText(body, "The group change could not be completed.")); return; }
      if (action === "delete" && selectedGroupId === group.id) { setSelectedGroupId(null); setArchive(null); if (selectedCycleId !== null) writeSelection(selectedCycleId); }
      setConfirm(null);
      setNotice(action === "delete" ? "Student group deleted." : "Student group status updated."); setReloadToken((value) => value + 1);
    } catch { setNotice("The student group service is unavailable."); }
    finally { setBusy(false); }
  };

  return (<section aria-labelledby="student-groups-heading">
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm font-semibold uppercase tracking-wide text-fy-text-secondary">{selectedCycle ? "Selected cycle" : "FYP Groups"}</p><h1 id="student-groups-heading" className="text-2xl font-bold tracking-tight">{selectedCycle ? selectedCycle.display_name : "FYP Cycles"}</h1><p className="mt-1 text-sm text-fy-text-secondary">{selectedCycle ? <>Viewing groups and document history for <strong className="text-fy-text">{selectedCycle.code}</strong>{selectedCycle.academic_year ? ` · ${selectedCycle.academic_year}` : ""}{selectedCycle.session ? ` · ${selectedCycle.session}` : ""}.</> : "Select an academic cycle before opening its groups and document history."}</p></div>{selectedCycle && <label className="grid gap-1 text-sm font-semibold text-fy-text">Switch cycle<select value={selectedCycleId ?? ""} onChange={(event) => selectCycle(event.target.value ? Number(event.target.value) : null)} className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2"><option value="">Choose a cycle</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name} ({cycle.code})</option>)}</select></label>}</div>
    {notice && <p role="status" className="mb-4 rounded-lg bg-fy-success-soft px-3 py-2 text-sm text-fy-success">{notice}</p>}
    {cycleState === "loading" && <div className="rounded-xl border border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">Loading FYP cycles...</div>}
    {cycleState === "error" && <div role="alert" className="rounded-xl border border-fy-danger bg-fy-danger-soft p-5 text-sm text-fy-danger">{cycleError || "FYP cycles could not be loaded."}</div>}
    {cycleState === "ready" && selectedCycleId === null && !cycles.length && <div className="rounded-xl border border-dashed border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">No FYP cycles are configured.</div>}
    {cycleState === "ready" && selectedCycleId === null && cycles.length > 0 && <div aria-label="FYP cycles" className="grid gap-3 sm:grid-cols-2">{cycles.map((cycle) => <button type="button" key={cycle.id} onClick={() => selectCycle(cycle.id)} className="rounded-xl border border-fy-border bg-fy-surface p-5 text-left shadow-sm transition hover:border-fy-brand hover:shadow-md"><span className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Academic cycle</span><strong className="mt-1 block text-lg text-fy-text">{cycle.display_name}</strong><span className="mt-1 block text-sm text-fy-text-secondary">{cycle.code}{cycle.academic_year ? ` · ${cycle.academic_year}` : ""}{cycle.session ? ` · ${cycle.session}` : ""}</span><span className="mt-4 block text-sm font-semibold text-fy-brand">View relevant groups</span></button>)}</div>}
    {selectedCycle && <section aria-labelledby="selected-cycle-heading"><div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-fy-border bg-fy-brand-soft p-4"><div><button type="button" onClick={() => selectCycle(null)} className="text-sm font-semibold text-fy-brand">← Back to FYP cycles</button><p className="mt-2 text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Selected cycle</p><h2 id="selected-cycle-heading" className="text-xl font-bold text-fy-text">{selectedCycle.display_name}</h2><p className="text-sm text-fy-text-secondary">{selectedCycle.code}</p></div><p className="text-sm font-semibold text-fy-text-secondary">{groupState === "ready" ? `${groups.length} group${groups.length === 1 ? "" : "s"}` : ""}</p></div>
      {groupState === "loading" && <div className="rounded-xl border border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">Loading groups for {selectedCycle.display_name}...</div>}
      {groupState === "error" && <div role="alert" className="rounded-xl border border-fy-danger bg-fy-danger-soft p-5 text-sm text-fy-danger">{groupError || "Groups for this cycle could not be loaded."}</div>}
      {groupState === "ready" && !groups.length && <div className="rounded-xl border border-dashed border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">No FYP groups belong to {selectedCycle.display_name}.</div>}
      {groupState === "ready" && groups.length > 0 && <div className="grid gap-4">{groups.map((group) => <article key={group.id} className={`rounded-xl border bg-fy-surface p-5 ${selectedGroupId === group.id ? "border-fy-brand shadow-md" : "border-fy-border"}`}><div className="flex flex-wrap items-start justify-between gap-4"><button type="button" onClick={() => openGroup(group.id)} className="text-left"><span className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Group {group.group_number ?? "—"} · {selectedCycle.display_name}</span><h3 className="mt-1 text-lg font-bold text-fy-text">{group.group_name}</h3><p className="text-sm text-fy-text-secondary">{group.group_email}</p><p className="mt-2 text-sm"><strong>Project:</strong> {display(group.project?.title)} · <strong>Supervisor:</strong> {display(group.supervisor?.name)}</p><span className="mt-2 block text-sm font-semibold text-fy-brand">{selectedGroupId === group.id ? "Selected group" : "Open group details"}</span></button><StatusBadge status={group.is_active ? "ACTIVE" : "INACTIVE"} /></div><div className="mt-4 overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="border-b border-fy-border text-xs uppercase tracking-wide text-fy-text-secondary"><tr><th className="px-2 py-2">Member</th><th className="px-2 py-2">Registration</th><th className="px-2 py-2">Email</th><th className="px-2 py-2">Role</th><th className="px-2 py-2">Project Title</th><th className="px-2 py-2">Supervisor</th></tr></thead><tbody className="divide-y divide-fy-border">{group.members.length ? group.members.map((member) => <tr key={member.id}><td className="px-2 py-2 font-semibold">{member.full_name}</td><td className="px-2 py-2">{member.registration_number}</td><td className="px-2 py-2">{member.email || "Not assigned"}</td><td className="px-2 py-2">{member.designation === "LEADER" ? "Leader" : "Member"}</td><td className="px-2 py-2">{group.project?.title?.trim() || "Not assigned"}</td><td className="px-2 py-2">{group.supervisor?.name?.trim() || "Not assigned"}</td></tr>) : <tr><td colSpan={6} className="px-2 py-3 text-fy-text-secondary">No active members assigned.</td></tr>}</tbody></table></div><div className="mt-4 flex flex-wrap justify-end gap-2">{group.is_active ? <button type="button" onClick={() => setConfirm({ group, action: "deactivate" })} className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold text-fy-success">Deactivate</button> : <button type="button" onClick={() => setConfirm({ group, action: "activate" })} className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold text-fy-success">Activate</button>}<button type="button" onClick={() => setConfirm({ group, action: "delete" })} className="rounded-lg border border-fy-danger px-3 py-2 text-sm font-semibold text-fy-danger">Delete permanently</button></div></article>)}</div>}
      {selectedGroup && <section aria-labelledby="selected-group-heading" className="mt-6 rounded-xl border border-fy-border bg-fy-surface p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Selected group · {selectedCycle.display_name}</p><h2 id="selected-group-heading" className="mt-1 text-xl font-bold text-fy-text">{selectedGroup.group_name}</h2><p className="text-sm text-fy-text-secondary">{selectedGroup.group_email}</p></div><button type="button" onClick={() => { setSelectedGroupId(null); setArchive(null); writeSelection(selectedCycle.id); }} className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold">Back to groups</button></div>{detailState === "loading" && <p className="mt-5 text-sm text-fy-text-secondary">Loading project and document details...</p>}{detailState === "error" && <p role="alert" className="mt-5 rounded-lg bg-fy-danger-soft p-3 text-sm text-fy-danger">{detailError || "The selected group details could not be loaded."}</p>}{detailState === "ready" && archive && <><div className="mt-5 grid gap-3 sm:grid-cols-3"><div className="rounded-lg bg-fy-surface-muted px-3 py-3"><p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Project title</p><p className="mt-1 text-sm font-semibold text-fy-text">{display(archive.project?.title || archive.project_title)}</p></div><div className="rounded-lg bg-fy-surface-muted px-3 py-3"><p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Supervisor</p><p className="mt-1 text-sm font-semibold text-fy-text">{display(archive.supervisor?.name)}</p></div><div className="rounded-lg bg-fy-surface-muted px-3 py-3"><p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Requirements</p><p className="mt-1 text-sm font-semibold text-fy-text">{archive.requirements.length}</p></div></div><h3 className="mt-6 text-lg font-bold text-fy-text">Members</h3><div className="mt-2 grid gap-2 sm:grid-cols-2">{archive.members.length ? archive.members.map((member) => <div key={member.id} className="rounded-lg border border-fy-border px-3 py-2"><strong className="text-sm">{member.name}</strong><p className="text-xs text-fy-text-secondary">{member.designation || "Member"} · {member.registration_number || "No registration"} · {member.email || "No email"}</p></div>) : <p className="text-sm text-fy-text-secondary">No members assigned.</p>}</div><h3 className="mt-6 text-lg font-bold text-fy-text">Requirements, submissions, versions, and review history</h3>{!archive.requirements.length ? <p className="mt-2 rounded-lg border border-dashed border-fy-border p-4 text-sm text-fy-text-secondary">No document requirements are configured for this cycle and group.</p> : <div className="mt-2 grid gap-3">{archive.requirements.map((requirement) => <article key={requirement.id} className="rounded-lg border border-fy-border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold text-fy-text">{requirement.requirement_name}</h4><p className="text-xs text-fy-text-secondary">{requirement.requirement_section || "Other"} · {requirement.is_required ? "Required" : "Optional"}</p></div><StatusBadge status={requirement.current_status} /></div><p className="mt-3 text-sm"><strong>Submission:</strong> {requirement.submitted_file_name || "Not submitted"}{requirement.submitted_at ? ` · ${new Date(requirement.submitted_at).toLocaleString()}` : ""}</p><p className="mt-1 text-sm"><strong>Versions:</strong> {requirement.versions.length ? requirement.versions.map((version) => `v${version.version_number} ${version.original_filename}`).join(", ") : "None"}</p>{requirement.review_history.length ? <div className="mt-3 border-t border-fy-border pt-3"><strong className="text-sm">Review history</strong><div className="mt-2 grid gap-2">{requirement.review_history.map((event) => <div key={event.id} className="text-sm"><StatusBadge status={event.status} /> · {event.reviewer?.name || "Not assigned"}{event.reviewed_at ? ` · ${new Date(event.reviewed_at).toLocaleString()}` : ""}{event.comment ? <p className="mt-1 whitespace-pre-wrap text-fy-text-secondary">{event.comment}</p> : null}</div>)}</div></div> : <p className="mt-3 text-sm text-fy-text-secondary">No review history recorded.</p>}</article>)}</div>}</>}</section>}
      </section>}
    {confirm && (
      <div role="dialog" aria-modal="true" aria-labelledby="group-confirm-heading" className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4">
        <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
          <h2 id="group-confirm-heading" className="text-lg font-bold">
            {confirm.action === "delete" ? "Confirm permanent deletion" : confirm.action === "activate" ? "Confirm activation" : "Confirm deactivation"}
          </h2>
          <p className="mt-2 text-sm text-[#60716b]">
            {confirm.action === "delete"
              ? `Permanently delete ${confirm.group.group_name}? This cannot be undone.`
              : `${confirm.action === "activate" ? "Activate" : "Deactivate"} ${confirm.group.group_name}?`}
          </p>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" disabled={busy} onClick={() => setConfirm(null)} className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold">Cancel</button>
            <button type="button" disabled={busy} onClick={() => void mutate()} className={`rounded-lg px-3 py-2 text-sm font-semibold text-white ${confirm.action === "delete" ? "bg-fy-danger" : "bg-fy-brand"}`}>{busy ? "Saving…" : "Confirm"}</button>
          </div>
        </div>
      </div>
    )}
    </section>
  );
}
