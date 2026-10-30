import { useCallback, useEffect, useState } from "react";

type Team = { id: number; academic_cycle_id: number };
type Milestone = { id: number; title: string; description: string | null; due_at: string | null; completion_percent: number; overdue: boolean };
type Task = Milestone & { milestone_id: number | null; owner_user_id: number | null };
type Meeting = { id: number; held_at: string; minutes: string; decisions: string | null; action_items: Array<Record<string, string>> };
type Progress = { team_id: number; health: string; milestones: Milestone[]; tasks: Task[]; meetings: Meeting[] };

const input = "w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2 text-sm text-[#243746]";

export function StudentProgressDashboard({ api }: { api: string }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState("");
  const [data, setData] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [milestone, setMilestone] = useState({ title: "", due_at: "", completion_percent: "0" });
  const [task, setTask] = useState({ title: "", due_at: "", completion_percent: "0" });
  const [meeting, setMeeting] = useState({ held_at: "", minutes: "", decisions: "" });
  const loadTeams = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const response = await fetch(`${api}/api/v1/group-channels/teams`, { credentials: "include" });
      if (!response.ok) throw new Error("Your team could not be loaded.");
      const rows = await response.json() as Team[];
      setTeams(rows); if (!teamId && rows[0]) setTeamId(String(rows[0].id));
    } catch (err) { setError(err instanceof Error ? err.message : "Your team could not be loaded."); }
    finally { setLoading(false); }
  }, [api, teamId]);
  const load = useCallback(async () => {
    if (!teamId) { setData(null); return; }
    setError("");
    try {
      const response = await fetch(`${api}/api/v1/project-progress/${teamId}`, { credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message ?? "Project progress could not be loaded.");
      setData(body as Progress);
    } catch (err) { setError(err instanceof Error ? err.message : "Project progress could not be loaded."); }
  }, [api, teamId]);
  useEffect(() => { const timer = window.setTimeout(() => { void loadTeams(); }, 0); return () => window.clearTimeout(timer); }, [loadTeams]);
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [load]);
  const save = async (path: string, body: unknown, reset: () => void) => {
    if (!teamId || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/project-progress/${teamId}/${path}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const responseBody = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof responseBody.detail === "string" ? responseBody.detail : responseBody.detail?.message ?? "The record could not be saved.");
      reset(); setMessage("Saved successfully."); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "The record could not be saved."); }
    finally { setBusy(false); }
  };
  const updateCompletion = async (kind: "milestones" | "tasks", item: Milestone | Task, value: string) => {
    if (busy) return;
    const completion = Number(value);
    if (!Number.isInteger(completion) || completion < 0 || completion > 100) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/project-progress/${kind}/${item.id}`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: item.title, description: item.description, due_at: item.due_at, completion_percent: completion, ...(kind === "tasks" ? { milestone_id: (item as Task).milestone_id, owner_user_id: (item as Task).owner_user_id } : {}) }) });
      const responseBody = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof responseBody.detail === "string" ? responseBody.detail : responseBody.detail?.message ?? "The completion update could not be saved.");
      setMessage("Completion updated successfully."); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "The completion update could not be saved."); }
    finally { setBusy(false); }
  };
  return <section className="student-phase-page" aria-labelledby="progress-heading">
    <div className="student-page-heading"><p className="student-overview__eyebrow">Project progress</p><h1 id="progress-heading">Project Progress &amp; Supervision Dashboard</h1><p>Record real milestones, tasks, and supervision evidence for your authorized team. Health is calculated from persisted due dates and completion values.</p></div>
    {error && <p role="alert" className="student-request-alert">{error}</p>}
    {loading ? <div className="student-placeholder">Loading project progress…</div> : !teams.length ? <div className="student-placeholder"><h2>Registered team required</h2><p>Create or join a registered team before recording progress.</p></div> : <>
      <div className="student-request-card"><label className="student-upload-label">Team<select className={input} value={teamId} onChange={(event) => setTeamId(event.target.value)}>{teams.map((team) => <option key={team.id} value={team.id}>Team {team.id}</option>)}</select></label>{data && <div className="student-overview__summary"><div><strong>{data.health}</strong><span>project health</span></div><div><strong>{data.milestones.length}</strong><span>milestones</span></div><div><strong>{data.tasks.filter((item) => item.overdue).length}</strong><span>overdue tasks</span></div></div>}</div>
      {data && <div className="student-overview__grid"><article className="student-request-card"><h2>Milestones</h2>{!data.milestones.length && <p className="student-request-muted">No milestones recorded.</p>}{data.milestones.map((item) => <div key={item.id} className="student-reference-results"><article><strong>{item.title}</strong><small>{item.completion_percent}% complete · {item.overdue ? "Overdue" : item.due_at ? new Date(item.due_at).toLocaleString() : "No due date"}</small><div className="mt-2 flex items-center gap-2"><label className="text-xs font-semibold">Completion <input className="w-20 rounded border px-2 py-1 text-xs" type="number" min="0" max="100" defaultValue={item.completion_percent} aria-label={`Completion for ${item.title}`} /></label><button type="button" disabled={busy} onClick={(event) => { const input = event.currentTarget.parentElement?.querySelector("input"); void updateCompletion("milestones", item, input instanceof HTMLInputElement ? input.value : String(item.completion_percent)); }}>Update</button></div></article></div>)}<form className="mt-4 grid gap-2" onSubmit={(event) => { event.preventDefault(); void save("milestones", { title: milestone.title, due_at: milestone.due_at || null, completion_percent: Number(milestone.completion_percent) }, () => setMilestone({ title: "", due_at: "", completion_percent: "0" })); }}><input className={input} required placeholder="Milestone title" value={milestone.title} onChange={(event) => setMilestone({ ...milestone, title: event.target.value })} /><input className={input} type="datetime-local" value={milestone.due_at} onChange={(event) => setMilestone({ ...milestone, due_at: event.target.value })} /><input className={input} type="number" min="0" max="100" value={milestone.completion_percent} onChange={(event) => setMilestone({ ...milestone, completion_percent: event.target.value })} /><button disabled={busy || !milestone.title.trim()}>{busy ? "Saving…" : "Add milestone"}</button></form></article>
        <article className="student-request-card"><h2>Tasks</h2>{!data.tasks.length && <p className="student-request-muted">No tasks recorded.</p>}{data.tasks.map((item) => <div key={item.id} className="student-reference-results"><article><strong>{item.title}</strong><small>{item.completion_percent}% complete · {item.overdue ? "Overdue" : item.due_at ? new Date(item.due_at).toLocaleString() : "No due date"}</small><div className="mt-2 flex items-center gap-2"><label className="text-xs font-semibold">Completion <input className="w-20 rounded border px-2 py-1 text-xs" type="number" min="0" max="100" defaultValue={item.completion_percent} aria-label={`Completion for ${item.title}`} /></label><button type="button" disabled={busy} onClick={(event) => { const input = event.currentTarget.parentElement?.querySelector("input"); void updateCompletion("tasks", item, input instanceof HTMLInputElement ? input.value : String(item.completion_percent)); }}>Update</button></div></article></div>)}<form className="mt-4 grid gap-2" onSubmit={(event) => { event.preventDefault(); void save("tasks", { title: task.title, due_at: task.due_at || null, completion_percent: Number(task.completion_percent) }, () => setTask({ title: "", due_at: "", completion_percent: "0" })); }}><input className={input} required placeholder="Task title" value={task.title} onChange={(event) => setTask({ ...task, title: event.target.value })} /><input className={input} type="datetime-local" value={task.due_at} onChange={(event) => setTask({ ...task, due_at: event.target.value })} /><input className={input} type="number" min="0" max="100" value={task.completion_percent} onChange={(event) => setTask({ ...task, completion_percent: event.target.value })} /><button disabled={busy || !task.title.trim()}>{busy ? "Saving…" : "Add task"}</button></form></article>
        <article className="student-request-card"><h2>Supervision meetings</h2>{!data.meetings.length && <p className="student-request-muted">No meeting records yet.</p>}{data.meetings.map((item) => <article key={item.id} className="border-b border-[#e8ede9] py-2"><strong>{new Date(item.held_at).toLocaleString()}</strong><p>{item.minutes}</p>{item.decisions && <small>{item.decisions}</small>}</article>)}<form className="mt-4 grid gap-2" onSubmit={(event) => { event.preventDefault(); void save("meetings", { held_at: meeting.held_at, minutes: meeting.minutes, decisions: meeting.decisions || null, action_items: [] }, () => setMeeting({ held_at: "", minutes: "", decisions: "" })); }}><input className={input} type="datetime-local" required value={meeting.held_at} onChange={(event) => setMeeting({ ...meeting, held_at: event.target.value })} /><textarea className={input} required rows={3} placeholder="Meeting minutes" value={meeting.minutes} onChange={(event) => setMeeting({ ...meeting, minutes: event.target.value })} /><textarea className={input} rows={2} placeholder="Decisions (optional)" value={meeting.decisions} onChange={(event) => setMeeting({ ...meeting, decisions: event.target.value })} /><button disabled={busy || !meeting.held_at || !meeting.minutes.trim()}>{busy ? "Saving…" : "Record meeting"}</button></form></article>
      </div>}
    </>}
    {message && <p role="status" className="student-request-alert">{message}</p>}
  </section>;
}
