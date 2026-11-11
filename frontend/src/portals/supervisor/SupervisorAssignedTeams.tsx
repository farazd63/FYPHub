import { useCallback, useEffect, useState } from "react";
import { SupervisorGroupDetails, type GroupWorkspace, type GroupTab, date } from "./SupervisorGroupDetails";

export function SupervisorAssignedTeams({ api }: { api: string }) {
  const [groups, setGroups] = useState<GroupWorkspace[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [selected, setSelected] = useState<{ id: number; tab: GroupTab } | null>(() => {
    const match = window.location.pathname.match(/\/supervisor\/groups\/(\d+)/);
    return match ? { id: Number(match[1]), tab: "overview" } : null;
  });
  const load = useCallback(async () => {
    try { const response = await fetch(`${api}/api/v1/supervisor/assigned-groups`, { credentials: "include" }); if (!response.ok) throw new Error("Assigned groups could not be loaded."); setGroups(await response.json() as GroupWorkspace[]); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Assigned groups could not be loaded."); }
    finally { setLoading(false); }
  }, [api]);
  useEffect(() => { const initial = window.setTimeout(() => void load(), 0); const timer = window.setInterval(() => void load(), 10000); const focus = () => void load(); window.addEventListener("focus", focus); return () => { window.clearTimeout(initial); window.clearInterval(timer); window.removeEventListener("focus", focus); }; }, [load]);
  const open = (id: number, tab: GroupTab) => { setSelected({ id, tab }); window.history.replaceState(window.history.state, "", `/supervisor/groups/${id}`); };
  if (selected) return <SupervisorGroupDetails key={selected.id} api={api} groupId={selected.id} initialTab={selected.tab} onBack={() => { setSelected(null); window.history.replaceState(window.history.state, "", "/supervisor/assigned-groups"); void load(); }} />;
  return <section className="supervisor-page" aria-labelledby="supervisor-assigned-heading">
    <div className="supervisor-page-heading"><h1 id="supervisor-assigned-heading">Assigned Students &amp; Teams</h1><span>Group members, proposals, documents and project progress for your active assignments.</span></div>
    {error && <p role="alert">{error} <button type="button" onClick={() => void load()}>Retry</button></p>}
    {loading ? <div className="supervisor-card">Loading assigned groups…</div> : !groups.length ? <div className="supervisor-card">No active assignments. Accepted groups will appear here.</div> : <div className="grid gap-4">{groups.map(data => <article key={data.group.id} className="supervisor-card">
      <h2>{data.group.name}</h2><p>{data.group.email}</p><p>{data.group.academic_cycle.name} · {data.group.academic_cycle.year} · {data.group.academic_cycle.session}</p>
      <dl className="my-4 grid gap-3 sm:grid-cols-3">{[
        ["Group status", data.group.status], ["Assignment", data.assignment?.status], ["Assigned", date(data.assignment?.assigned_at)],
        ["Supervisor", data.supervisor.name], ["Members", data.members.length], ["Project title", data.project?.title || data.proposal?.title || "Not submitted yet"],
        ["Proposal", data.proposal?.status || "Not submitted yet"], ["Project", data.project?.status || "Not started yet"],
        ["Completion", data.project?.completion_percentage == null ? "No progress recorded" : `${data.project.completion_percentage}%`], ["Last activity", date(data.group.last_activity_at)]
      ].map(([label, value]) => <div key={label}><dt className="text-xs font-semibold uppercase text-slate-500">{label}</dt><dd className="text-sm">{value}</dd></div>)}</dl>
      <div className="flex flex-wrap gap-2">{([["overview", "View full details"], ["proposal", "Open proposal"], ["project", "Open project"], ["members", "View members"], ["documents", "View documents"], ["discussion", "Open group discussion"]] as [GroupTab, string][]).map(([tab, label]) => <button key={tab} type="button" onClick={() => open(data.group.id, tab)} className="rounded-lg border px-3 py-2 text-sm">{label}</button>)}</div>
    </article>)}</div>}
  </section>;
}
