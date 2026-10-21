import { useCallback, useEffect, useState } from "react";

type Supervisor = { id: number; full_name: string; email: string };
type Cycle = { id: number; code: string; display_name: string };
type Policy = { id: number; supervisor_id: number; supervisor_name: string; supervisor_email: string; supervisor_is_eligible: boolean; academic_cycle_id: number; academic_cycle_name: string; max_group_capacity: number; assigned: number; remaining: number; full: boolean };
type State = "loading" | "ready" | "error";
const input = "w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm text-[#243746] focus:border-[#176b66] disabled:cursor-not-allowed disabled:bg-[#f4f6f4]";
const detail = (body: unknown) => { const value = body as { detail?: { message?: string } | string }; return typeof value.detail === "object" ? value.detail.message ?? "Could not save capacity." : typeof value.detail === "string" ? value.detail : "Could not save capacity."; };

export function AdminSupervisorCapacity({ api }: { api: string }) {
  const [state, setState] = useState<State>("loading");
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]), [cycles, setCycles] = useState<Cycle[]>([]), [policies, setPolicies] = useState<Policy[]>([]);
  const [form, setForm] = useState({ supervisor_id: "", academic_cycle_id: "", max_group_capacity: "" });
  const [editing, setEditing] = useState<number | null>(null), [message, setMessage] = useState(""), [saving, setSaving] = useState(false);
  const selectedSupervisor = supervisors.find((person) => person.id === Number(form.supervisor_id));
  const hasRepeatedName = (person: Supervisor) => supervisors.filter((candidate) => candidate.full_name === person.full_name).length > 1;
  const load = useCallback(async () => { setState("loading"); try {
    const [people, configuredCycles, configuredPolicies] = await Promise.all([
      fetch(`${api}/api/v1/admin/users?role=SUPERVISOR&is_active=true&page_size=100`, { credentials: "include" }), fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" }), fetch(`${api}/api/v1/admin/supervisor-capacities`, { credentials: "include" }),
    ]);
    if (!people.ok || !configuredCycles.ok || !configuredPolicies.ok) throw new Error();
    setSupervisors(((await people.json()) as { items: Supervisor[] }).items); setCycles((await configuredCycles.json()) as Cycle[]); setPolicies((await configuredPolicies.json()) as Policy[]); setState("ready");
  } catch { setState("error"); } }, [api]);
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [load]);
  const reset = () => { setEditing(null); setForm({ supervisor_id: "", academic_cycle_id: "", max_group_capacity: "" }); };
  const submit = async (event: React.FormEvent) => { event.preventDefault(); if (saving) return; const maximum = Number(form.max_group_capacity);
    if (!form.supervisor_id || !form.academic_cycle_id || !Number.isInteger(maximum) || maximum <= 0) { setMessage("Choose a supervisor and cycle, then enter a positive whole-number maximum."); return; }
    setSaving(true); setMessage(""); try { const isEdit = editing !== null; const response = await fetch(`${api}/api/v1/admin/supervisor-capacities${isEdit ? `/${editing}` : ""}`, { method: isEdit ? "PUT" : "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ supervisor_id: Number(form.supervisor_id), academic_cycle_id: Number(form.academic_cycle_id), max_group_capacity: maximum }) }); const body = await response.json().catch(() => ({})); if (!response.ok) { setMessage(detail(body)); return; } reset(); setMessage(isEdit ? "Capacity policy updated." : "Capacity policy created."); await load(); } catch { setMessage("The capacity service is unavailable."); } finally { setSaving(false); }
  };
  const startEdit = (policy: Policy) => { setEditing(policy.id); setForm({ supervisor_id: String(policy.supervisor_id), academic_cycle_id: String(policy.academic_cycle_id), max_group_capacity: String(policy.max_group_capacity) }); setMessage(""); };
  return <section aria-labelledby="capacity-heading"><div className="mb-5"><h1 id="capacity-heading" className="text-2xl font-bold tracking-tight">Supervisor Capacity</h1><p className="mt-1 text-sm text-[#60716b]">Set the maximum groups an active supervisor may be allocated in an academic cycle. Assign registered teams within the configured cycle limit.</p></div>
    {message && <p role="status" className="mb-4 rounded-lg bg-[#e4eee7] px-3 py-2 text-sm text-[#176b66]">{message}</p>}
    {state === "loading" && <div className="rounded-xl border border-[#dce4de] bg-white p-5 text-sm text-[#60716b]">Loading capacity configuration…</div>}
    {state === "error" && <div role="alert" className="rounded-xl border border-[#e6c8c3] bg-[#fff3f0] p-5 text-sm text-[#a43a33]">Capacity configuration could not be loaded. <button type="button" className="underline" onClick={() => void load()}>Try again</button>.</div>}
    {state === "ready" && <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_330px]"><div>{!policies.length ? <div className="rounded-xl border border-dashed border-[#cbd6d0] bg-white p-5 text-sm text-[#60716b]">No supervisor capacity policies have been configured.</div> : <div className="overflow-x-auto rounded-xl border border-[#dce4de] bg-white"><table className="w-full text-left text-sm"><thead className="bg-[#fbfcfa] text-xs uppercase tracking-wide text-[#60716b]"><tr><th className="px-4 py-3">Supervisor</th><th className="px-3 py-3">Academic cycle</th><th className="px-3 py-3">Maximum groups</th><th className="px-3 py-3">Assigned</th><th className="px-3 py-3">Remaining</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Action</th></tr></thead><tbody className="divide-y divide-[#e8ede9]">{policies.map((policy) => <tr key={policy.id}><td className="px-4 py-3"><p className="font-semibold">{policy.supervisor_name}</p><p className="text-xs text-[#60716b]">{policy.supervisor_email}{!policy.supervisor_is_eligible ? " · historical account" : ""}</p></td><td className="px-3 py-3">{policy.academic_cycle_name}</td><td className="px-3 py-3 font-semibold">{policy.max_group_capacity}</td><td className="px-3 py-3">{policy.assigned}</td><td className="px-3 py-3">{policy.remaining}</td><td className="px-3 py-3">{policy.full ? "Full" : "Available"}</td><td className="px-3 py-3"><button type="button" onClick={() => startEdit(policy)} className="rounded-lg border border-[#b8cdc1] px-3 py-1.5 text-xs font-semibold text-[#176b66] hover:bg-[#e4eee7]">Edit</button></td></tr>)}</tbody></table></div>}</div>
      <form onSubmit={submit} className="h-fit rounded-xl border border-[#dce4de] bg-white p-5 shadow-[0_2px_12px_rgba(36,55,70,0.035)]"><h2 className="font-bold">{editing ? "Update capacity policy" : "Add capacity policy"}</h2><div className="mt-4 grid gap-3"><label className="grid gap-1 text-sm font-semibold">Supervisor name<select required className={input} value={form.supervisor_id} onChange={(event) => setForm({ ...form, supervisor_id: event.target.value })}><option value="">Select active supervisor</option>{supervisors.map((person) => <option key={person.id} value={person.id}>{person.full_name}{hasRepeatedName(person) ? ` (ID: ${person.id})` : ""}</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Supervisor email<input readOnly aria-readonly="true" className={input} value={selectedSupervisor?.email ?? ""} /></label><label className="grid gap-1 text-sm font-semibold">Academic cycle<select required className={input} value={form.academic_cycle_id} onChange={(event) => setForm({ ...form, academic_cycle_id: event.target.value })}><option value="">Select academic cycle</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name} ({cycle.code})</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Maximum group capacity<input required min="1" step="1" inputMode="numeric" type="number" className={input} value={form.max_group_capacity} onChange={(event) => setForm({ ...form, max_group_capacity: event.target.value })} /></label><div className="flex gap-3"><button disabled={saving} className="rounded-lg bg-[#176b66] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#125650] disabled:opacity-60">{saving ? "Saving…" : editing ? "Save changes" : "Save capacity"}</button>{editing && <button type="button" disabled={saving} onClick={reset} className="rounded-lg border border-[#cbd6d0] px-4 py-2.5 text-sm font-semibold">Cancel</button>}</div></div></form></div>}
    {state !== "error" && <Allocation api={api} cycles={cycles} policies={policies} onChanged={load} />}
  </section>;
}


type Team = { id: number; creator_name: string };
type Assignment = { id: number; team_id: number; supervisor_id: number; ended_at: string | null };
function Allocation({ api, cycles, policies, onChanged }: { api: string; cycles: Cycle[]; policies: Policy[]; onChanged: () => Promise<void> }) {
  const [cycle, setCycle] = useState("");
  const [team, setTeam] = useState("");
  const [supervisor, setSupervisor] = useState("");
  const [teams, setTeams] = useState<Team[]>([]);
  const [history, setHistory] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!cycle) return;
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      try {
        const [a, b] = await Promise.all([fetch(`${api}/api/v1/admin/supervisor-assignments/teams?academic_cycle_id=${cycle}`, { credentials: "include", signal: controller.signal }), fetch(`${api}/api/v1/admin/supervisor-assignments?academic_cycle_id=${cycle}`, { credentials: "include", signal: controller.signal })]);
        if (!a.ok || !b.ok) throw new Error();
        const [t, h] = await Promise.all([a.json() as Promise<Team[]>, b.json() as Promise<Assignment[]>]);
        if (!controller.signal.aborted) { setTeams(t); setHistory(h); setLoading(false); }
      } catch { if (!controller.signal.aborted) { setMessage("Assignments could not be loaded."); setLoading(false); } }
    };
    void run(); return () => controller.abort();
  }, [api, cycle, refresh]);
  const change = async (event: React.FormEvent) => {
    event.preventDefault(); if (saving) return; setSaving(true); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/admin/supervisor-assignments`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ academic_cycle_id: Number(cycle), supervisor_id: Number(supervisor), team_id: Number(team) }) });
      const body = await response.json().catch(() => ({})); if (!response.ok) { setMessage(detail(body)); return; }
      setTeam(""); setMessage("Supervisor assigned."); setRefresh(v => v + 1); await onChanged();
    } catch { setMessage("Assignment service is unavailable."); } finally { setSaving(false); }
  };
  const end = async (id: number) => {
    if (saving) return; setSaving(true); setMessage("");
    try { const response = await fetch(`${api}/api/v1/admin/supervisor-assignments/${id}/end`, { method: "POST", credentials: "include" }); const body = await response.json().catch(() => ({})); if (!response.ok) { setMessage(detail(body)); return; } setMessage("Assignment ended; history retained."); setRefresh(v => v + 1); await onChanged(); }
    catch { setMessage("Assignment service is unavailable."); } finally { setSaving(false); }
  };
  return <div className="mt-5 rounded-xl border border-[#dce4de] bg-white p-5"><h2 className="font-bold">Supervisor assignments</h2><p className="mt-1 text-sm text-[#60716b]">Select a cycle and a registered team. Assignment history is retained.</p>{message && <p role="status" className="mt-3 text-sm">{message}</p>}
    <form onSubmit={change} className="mt-4 grid gap-3 md:grid-cols-3"><label className="grid gap-1 text-sm font-semibold">Academic cycle<select required className={input} value={cycle} onChange={e => { setCycle(e.target.value); setTeam(""); setSupervisor(""); setTeams([]); setHistory([]); }}><option value="">Select cycle</option>{cycles.map(c => <option key={c.id} value={c.id}>{c.display_name} ({c.code})</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Team<select required disabled={!cycle || loading} className={input} value={team} onChange={e => setTeam(e.target.value)}><option value="">Select team</option>{teams.map(t => <option key={t.id} value={t.id}>Team {t.id} ? {t.creator_name}</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Supervisor<select required disabled={!cycle || loading} className={input} value={supervisor} onChange={e => setSupervisor(e.target.value)}><option value="">Select supervisor</option>{policies.filter(p => p.academic_cycle_id === Number(cycle) && p.supervisor_is_eligible).map(p => <option key={p.id} value={p.supervisor_id}>{p.supervisor_name} ({p.supervisor_email}) ? {p.remaining} remaining</option>)}</select></label><button disabled={saving || loading} className="w-fit rounded-lg bg-[#176b66] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving..." : "Assign supervisor"}</button></form>
    {cycle && <div className="mt-5"><h3 className="font-bold">Assignment history</h3>{loading ? <p className="mt-2 text-sm">Loading...</p> : history.length === 0 ? <p className="mt-2 text-sm text-[#60716b]">No assignments for this cycle.</p> : <ul className="mt-2 space-y-2">{history.map(a => <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#e8ede9] p-3 text-sm"><span>Team {a.team_id} ? Supervisor {policies.find(p => p.supervisor_id === a.supervisor_id)?.supervisor_name ?? `ID ${a.supervisor_id}`} ? {a.ended_at ? "Ended" : "Active"}</span>{!a.ended_at && <button type="button" disabled={saving} onClick={() => void end(a.id)} className="rounded-lg border border-[#b8cdc1] px-3 py-1 text-[#176b66]">End assignment</button>}</li>)}</ul>}</div>}
  </div>;
}
