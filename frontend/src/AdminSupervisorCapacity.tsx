import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Pencil, Trash2, X } from "lucide-react";
import { AdminAddButton } from "./ui/AdminAddButton";
import { IconButton } from "./ui/IconButton";

type Supervisor = { id: number; full_name: string; email: string };
type Cycle = { id: number; academic_year: number | null; session: "FALL" | "SPRING" | null };
type CapacityStatus = "AVAILABLE" | "NEARLY_FULL" | "FULL" | "OVER_CAPACITY" | "INACTIVE";
type Policy = { id: number; supervisor_id: number; supervisor_name: string; supervisor_email: string; supervisor_is_eligible: boolean; academic_cycle_id: number | null; academic_year: number | null; maximum_groups: number; fall_assigned: number; spring_assigned: number; total_assigned: number; remaining_capacity: number; status: CapacityStatus };
type State = "loading" | "ready" | "error";

const input = "w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm text-[#243746] focus:border-[#176b66] disabled:cursor-not-allowed disabled:bg-[#f4f6f4]";
const detail = (body: unknown) => { const value = body as { detail?: { message?: string } | string }; return typeof value.detail === "object" && value.detail ? value.detail.message ?? "Could not save capacity." : typeof value.detail === "string" ? value.detail : "Could not save capacity."; };

export function AdminSupervisorCapacity({ api }: { api: string }) {
  const [state, setState] = useState<State>("loading");
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [form, setForm] = useState({ supervisor_id: "", academic_year: "", maximum_groups: "" });
  const [editing, setEditing] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Policy | null>(null);
  const [supervisorSearch, setSupervisorSearch] = useState("");
  const [cycleFilter, setCycleFilter] = useState("");

  const currentYear = new Date().getFullYear();
  const years = Array.from(new Set([...cycles.map((cycle) => cycle.academic_year).filter((year): year is number => year !== null), ...Array.from({ length: 11 }, (_, index) => currentYear - 5 + index)])).sort((a, b) => b - a);
  const hasRepeatedName = (person: Supervisor) => supervisors.filter((candidate) => candidate.full_name === person.full_name).length > 1;
  const cycleOptions = useMemo(() => [...cycles].sort((left, right) => (right.academic_year ?? 0) - (left.academic_year ?? 0) || (left.session || "").localeCompare(right.session || "")), [cycles]);
  const filteredPolicies = useMemo(() => {
    const nameQuery = supervisorSearch.trim().toLocaleLowerCase();
    const cycle = cycles.find((item) => String(item.id) === cycleFilter);
    return policies.filter((policy) => {
      const matchesName = !nameQuery || policy.supervisor_name.toLocaleLowerCase().includes(nameQuery) || policy.supervisor_email.toLocaleLowerCase().includes(nameQuery);
      const matchesCycle = !cycle || policy.academic_cycle_id === cycle.id || (policy.academic_cycle_id === null && policy.academic_year === cycle.academic_year);
      return matchesName && matchesCycle;
    });
  }, [policies, cycles, supervisorSearch, cycleFilter]);

  const cycleLabel = (cycle: Cycle) => `${cycle.academic_year ?? "Unspecified year"}${cycle.session ? ` · ${cycle.session}` : ""}`;

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [people, configuredCycles, configuredPolicies] = await Promise.all([
        fetch(`${api}/api/v1/admin/users?role=SUPERVISOR&is_active=true&page_size=100`, { credentials: "include" }),
        fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" }),
        fetch(`${api}/api/v1/admin/supervisor-capacities`, { credentials: "include" }),
      ]);
      if (!people.ok || !configuredCycles.ok || !configuredPolicies.ok) throw new Error();
      setSupervisors(((await people.json()) as { items: Supervisor[] }).items);
      setCycles((await configuredCycles.json()) as Cycle[]);
      setPolicies((await configuredPolicies.json()) as Policy[]);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [api]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const reset = () => { setEditing(null); setShowCreate(false); setForm({ supervisor_id: "", academic_year: "", maximum_groups: "" }); };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (saving) return;
    const maximum = Number(form.maximum_groups);
    if (!form.supervisor_id || !form.academic_year || !Number.isInteger(maximum) || maximum <= 0) {
      setMessage("Choose a supervisor and academic year, then enter a positive whole-number annual maximum.");
      return;
    }
    setSaving(true); setMessage("");
    try {
      const isEdit = editing !== null;
      const response = await fetch(`${api}/api/v1/admin/supervisor-capacities${isEdit ? `/${editing}` : ""}`, { method: isEdit ? "PUT" : "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ supervisor_id: Number(form.supervisor_id), academic_year: Number(form.academic_year), maximum_groups: maximum }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) { setMessage(detail(body)); return; }
      reset(); setMessage(isEdit ? "Capacity policy updated." : "Capacity policy created."); await load();
    } catch {
      setMessage("The capacity service is unavailable.");
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!confirmDelete || saving || deleting !== null) return;
    const policy = confirmDelete;
    setDeleting(policy.id); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/admin/supervisor-capacities/${policy.id}`, { method: "DELETE", credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) { setMessage(detail(body)); return; }
      if (editing === policy.id) reset();
      setConfirmDelete(null); setMessage("Capacity policy deleted."); await load();
    } catch {
      setMessage("The capacity service is unavailable.");
    } finally { setDeleting(null); }
  };

  const startEdit = (policy: Policy) => { setEditing(policy.id); setShowCreate(true); setForm({ supervisor_id: String(policy.supervisor_id), academic_year: String(policy.academic_year ?? ""), maximum_groups: String(policy.maximum_groups) }); setMessage(""); };
  const clearFilters = () => { setSupervisorSearch(""); setCycleFilter(""); };
  const statusClass = (status: CapacityStatus) => status === "AVAILABLE" ? "supervisor-capacity-status supervisor-capacity-status--available" : status === "FULL" ? "supervisor-capacity-status supervisor-capacity-status--full" : status === "OVER_CAPACITY" || status === "NEARLY_FULL" ? "supervisor-capacity-status supervisor-capacity-status--warning" : "supervisor-capacity-status";
  const statusLabel = (status: CapacityStatus) => status === "OVER_CAPACITY" ? "Over capacity" : status === "NEARLY_FULL" ? "Nearly full" : status === "INACTIVE" ? "Inactive" : status === "FULL" ? "Full" : "Available";

  return <section aria-labelledby="capacity-heading">
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><h1 id="capacity-heading" className="text-2xl font-bold tracking-tight">Supervisor Capacity</h1><p className="mt-1 text-sm text-[#60716b]">Set the annual maximum groups an active supervisor may be allocated. Fall and Spring assignments share the same yearly limit.</p></div><AdminAddButton open={showCreate || editing !== null} label="capacity policy" onClick={() => { if (showCreate || editing !== null) reset(); else { setEditing(null); setForm({ supervisor_id: "", academic_year: "", maximum_groups: "" }); setShowCreate(true); } }} /></div>
    {message && <p role="status" className="mb-4 rounded-lg bg-[#e4eee7] px-3 py-2 text-sm text-[#176b66]">{message}</p>}
    {state === "loading" && <div className="rounded-xl border border-[#dce4de] bg-white p-5 text-sm text-[#60716b]">Loading capacity configuration...</div>}
    {state === "error" && <div role="alert" className="rounded-xl border border-[#e6c8c3] bg-[#fff3f0] p-5 text-sm text-[#a43a33]">Capacity configuration could not be loaded. <button type="button" className="underline" onClick={() => void load()}>Try again</button>.</div>}
    {state === "ready" && <div className={`admin-capacity-layout grid min-w-0 gap-5 ${showCreate || editing !== null ? "has-editor" : ""}`}>
      <div className="min-w-0">
        {!policies.length ? <div className="rounded-xl border border-dashed border-[#cbd6d0] bg-white p-5 text-sm text-[#60716b]">No supervisor capacity policies have been configured.</div> : <>
          <div className="mb-4 grid gap-3 rounded-xl border border-[#dce4de] bg-white p-4 md:grid-cols-[minmax(0,1fr)_minmax(220px,280px)_auto] md:items-end">
            <label className="grid gap-1 text-sm font-semibold">Search supervisor<input type="search" className={input} value={supervisorSearch} onChange={(event) => setSupervisorSearch(event.target.value)} placeholder="Search by name or email" /></label>
            <label className="grid gap-1 text-sm font-semibold">Academic cycle<select className={input} value={cycleFilter} onChange={(event) => setCycleFilter(event.target.value)}><option value="">All cycles</option>{cycleOptions.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycleLabel(cycle)}</option>)}</select></label>
            <IconButton type="button" label="Clear supervisor filters" size="sm" variant="secondary" onClick={clearFilters} disabled={!supervisorSearch && !cycleFilter}><X size={15} strokeWidth={1.8} aria-hidden /></IconButton>
            <p className="text-xs text-[#60716b] md:col-span-3">Showing {filteredPolicies.length} of {policies.length} capacity policies.</p>
          </div>
          {!filteredPolicies.length ? <div className="rounded-xl border border-dashed border-[#cbd6d0] bg-white p-5 text-sm text-[#60716b]">No capacity policies match the selected filters.</div> : <div className="admin-table-scroll overflow-x-auto rounded-xl border border-[#dce4de] bg-white"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-[#fbfcfa] text-xs uppercase tracking-wide text-[#60716b]"><tr><th className="px-4 py-3">Supervisor</th><th className="px-3 py-3">Academic year</th><th className="px-3 py-3">Annual maximum</th><th className="px-3 py-3">Fall assigned</th><th className="px-3 py-3">Spring assigned</th><th className="px-3 py-3">Total assigned</th><th className="px-3 py-3">Remaining</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Actions</th></tr></thead><tbody className="divide-y divide-[#e8ede9]">{filteredPolicies.map((policy) => <tr key={policy.id}><td className="px-4 py-3"><p className="font-semibold">{policy.supervisor_name}</p><p className="text-xs text-[#60716b]">{policy.supervisor_email}</p></td><td className="px-3 py-3">{policy.academic_year ?? "-"}</td><td className="px-3 py-3 font-semibold">{policy.maximum_groups}</td><td className="px-3 py-3">{policy.fall_assigned}</td><td className="px-3 py-3">{policy.spring_assigned}</td><td className="px-3 py-3">{policy.total_assigned}</td><td className="px-3 py-3">{policy.remaining_capacity}</td><td className="px-3 py-3"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(policy.status)}`}>{statusLabel(policy.status)}</span></td><td className="px-3 py-3"><div className="flex flex-wrap gap-1.5" aria-label={`Actions for ${policy.supervisor_name} ${policy.academic_year ?? ""}`}><IconButton label={`Edit capacity for ${policy.supervisor_name}`} size="sm" variant="secondary" onClick={() => startEdit(policy)}><Pencil size={15} strokeWidth={1.8} aria-hidden /></IconButton><IconButton label={`Delete capacity for ${policy.supervisor_name}`} size="sm" variant="danger" disabled={deleting === policy.id || saving} onClick={() => setConfirmDelete(policy)}><Trash2 size={15} strokeWidth={1.8} aria-hidden /></IconButton></div></td></tr>)}</tbody></table></div>}
        </>}
      </div>
      {(showCreate || editing !== null) && <form onSubmit={submit} className="h-fit rounded-xl border border-[#dce4de] bg-white p-5 shadow-[0_2px_12px_rgba(36,55,70,0.035)]"><h2 className="font-bold">{editing ? "Update capacity policy" : "Add capacity policy"}</h2><p className="mt-1 text-sm text-[#60716b]">One policy per supervisor and academic year.</p><div className="mt-4 grid gap-3"><label className="grid gap-1 text-sm font-semibold">Supervisor<select required className={input} value={form.supervisor_id} onChange={(event) => setForm({ ...form, supervisor_id: event.target.value })}><option value="">Select active supervisor</option>{supervisors.map((person) => <option key={person.id} value={person.id}>{person.full_name} ({person.email}){hasRepeatedName(person) ? ` - ID ${person.id}` : ""}</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Academic year<select required className={input} value={form.academic_year} onChange={(event) => setForm({ ...form, academic_year: event.target.value })}><option value="">Select academic year</option>{years.map((year) => <option key={year} value={year}>{year}</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Annual maximum groups<input required min="1" step="1" inputMode="numeric" type="number" className={input} value={form.maximum_groups} onChange={(event) => setForm({ ...form, maximum_groups: event.target.value })} /><span className="font-normal text-[#60716b]">{form.maximum_groups && Number.isInteger(Number(form.maximum_groups)) && Number(form.maximum_groups) > 0 ? `${form.maximum_groups} maximum groups across Fall and Spring` : "Enter a positive whole number."}</span></label><div className="flex gap-3"><button disabled={saving || !form.supervisor_id || !form.academic_year || !form.maximum_groups} className="fy-btn fy-btn--primary">{saving ? "Saving..." : editing ? "Save changes" : "Save capacity"}</button>{editing && <button type="button" disabled={saving} onClick={reset} className="fy-btn fy-btn--secondary">Cancel</button>}</div></div></form>}
    </div>}
    {confirmDelete && <div role="dialog" aria-modal="true" aria-labelledby="capacity-delete-heading" className="fixed inset-0 grid place-items-center bg-[#243746]/35 p-4"><div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl"><h2 id="capacity-delete-heading" className="text-lg font-bold">Confirm capacity deletion</h2><p className="mt-2 text-sm text-[#60716b]">Delete the {confirmDelete.academic_year ?? "annual"} capacity policy for {confirmDelete.supervisor_name}?</p><div className="mt-5 flex justify-end gap-3"><button type="button" disabled={deleting !== null} onClick={() => setConfirmDelete(null)} className="rounded-lg border border-[#dce4de] px-3 py-2 text-sm font-semibold">Cancel</button><button type="button" disabled={deleting !== null} onClick={() => void remove()} className="rounded-lg bg-red-700 px-3 py-2 text-sm font-semibold text-white">{deleting !== null ? "Deleting…" : "Delete"}</button></div></div></div>}
  </section>;
}
