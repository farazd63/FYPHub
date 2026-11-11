import { useCallback, useEffect, useMemo, useState } from "react";

type Team = { id: number; academic_cycle_id: number };
type Milestone = { id: number; title: string; description: string | null; due_at: string | null; completion_percent: number; overdue: boolean };
type Task = Milestone & { milestone_id: number | null; owner_user_id: number | null };
type Meeting = { id: number; held_at: string; minutes: string; decisions: string | null; action_items: Array<Record<string, string>> };
type Progress = { team_id: number; health: string; milestones: Milestone[]; tasks: Task[]; meetings: Meeting[] };

const input = "progress-input";
const colors = ["progress-bar--violet", "progress-bar--mint", "progress-bar--orange", "progress-bar--pink", "progress-bar--blue"];

function dateLabel(value: string | null) {
  if (!value) return "No due date";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function timelineDays() {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  return Array.from({ length: 14 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function barPosition(dueAt: string | null, days: Date[]) {
  if (!dueAt) return { start: 1, span: 2 };
  const due = new Date(dueAt);
  const index = Math.max(0, Math.min(days.length - 1, Math.round((due.getTime() - days[0].getTime()) / 86400000)));
  return { start: Math.max(1, index + 1), span: Math.min(4, days.length - index) };
}

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
  const days = useMemo(() => timelineDays(), []);

  const loadTeams = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const response = await fetch(`${api}/api/v1/group-channels/teams`, { credentials: "include" });
      if (!response.ok) throw new Error("Your project plan could not be loaded.");
      const rows = await response.json() as Team[];
      setTeams(rows);
      if (rows[0]) setTeamId((current) => current || String(rows[0].id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your project plan could not be loaded.");
    } finally { setLoading(false); }
  }, [api]);

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

  const milestones = data?.milestones ?? [];
  const tasks = data?.tasks ?? [];
  const ganttRows = [...milestones.map((item) => ({ ...item, kind: "Milestone" })), ...tasks.map((item) => ({ ...item, kind: "Task" }))];
  const overdueCount = tasks.filter((item) => item.overdue).length;

  return <section className="student-phase-page progress-page" aria-labelledby="progress-heading">
    <div className="progress-hero"><div><p className="progress-kicker">Planning workspace</p><h1 id="progress-heading">Project progress</h1><p>Keep milestones, tasks, and supervision evidence aligned in one clear project plan.</p></div><div className="progress-hero__badge"><span className="progress-hero__dot" />Live plan</div></div>
    {error && <p role="alert" className="student-request-alert">{error}</p>}
    {loading ? <div className="student-placeholder">Loading project progress…</div> : !teams.length ? <div className="student-placeholder"><h2>Registered team required</h2><p>Create or join a registered team before recording progress.</p></div> : <>
      <div className="progress-summary" aria-label="Project summary"><div className="progress-summary__card progress-summary__card--purple"><span className="progress-summary__label">Project health</span><strong>{data?.health ?? "Pending"}</strong><small>Based on dates and completion</small></div><div className="progress-summary__card progress-summary__card--green"><span className="progress-summary__label">Milestones</span><strong>{milestones.length}</strong><small>Key delivery points</small></div><div className="progress-summary__card progress-summary__card--orange"><span className="progress-summary__label">Overdue tasks</span><strong>{overdueCount}</strong><small>Needs attention</small></div></div>
      {data && <div className="progress-board"><div className="progress-board__heading"><div><p className="progress-kicker">Roadmap</p><h2>Project timeline</h2><span>Two-week view · {ganttRows.length} tracked items</span></div><div className="progress-legend"><span><i className="progress-legend__swatch progress-legend__swatch--violet" />Milestone</span><span><i className="progress-legend__swatch progress-legend__swatch--mint" />Task</span></div></div><div className="progress-gantt"><div className="progress-gantt__labels"><div className="progress-gantt__labels-heading">Workstream <span>Progress</span></div>{ganttRows.length ? ganttRows.map((item) => <div className="progress-gantt__label" key={`${item.kind}-${item.id}`}><span><b>{item.kind}</b>{item.title}</span><strong>{item.completion_percent}%</strong></div>) : <div className="progress-gantt__empty">Add a milestone or task to start your roadmap.</div>}</div><div className="progress-gantt__timeline"><div className="progress-gantt__dates">{days.map((day) => <span key={day.toISOString()}><b>{day.toLocaleDateString(undefined, { weekday: "short" }).slice(0, 1)}</b>{day.getDate()}</span>)}</div>{ganttRows.map((item, index) => { const position = barPosition(item.due_at, days); return <div className="progress-gantt__track" key={`${item.kind}-track-${item.id}`}><span className={`progress-bar ${colors[index % colors.length]}`} style={{ gridColumn: `${position.start} / span ${position.span}` }} title={`${item.title} · ${item.completion_percent}% complete`}><b>{item.title}</b><small>{item.completion_percent}%</small></span></div>; })}</div></div></div>}
      {data && <div className="progress-actions-grid"><article className="progress-card"><div className="progress-card__heading"><span className="progress-card__icon progress-card__icon--violet">✦</span><div><h2>Milestones</h2><p>Define the major delivery points.</p></div></div>{!milestones.length && <p className="progress-muted">No milestones recorded.</p>}{milestones.map((item) => <div className="progress-record" key={item.id}><div><strong>{item.title}</strong><span>{item.completion_percent}% · {item.overdue ? "Overdue" : dateLabel(item.due_at)}</span></div><div className="progress-record__update"><input aria-label={`Completion for ${item.title}`} type="number" min="0" max="100" defaultValue={item.completion_percent} /><button type="button" disabled={busy} onClick={(event) => { const field = event.currentTarget.parentElement?.querySelector("input"); void updateCompletion("milestones", item, field instanceof HTMLInputElement ? field.value : String(item.completion_percent)); }}>Update</button></div></div>)}<form className="progress-form" onSubmit={(event) => { event.preventDefault(); void save("milestones", { title: milestone.title, due_at: milestone.due_at || null, completion_percent: Number(milestone.completion_percent) }, () => setMilestone({ title: "", due_at: "", completion_percent: "0" })); }}><input className={input} required placeholder="Milestone title" value={milestone.title} onChange={(event) => setMilestone({ ...milestone, title: event.target.value })} /><div className="progress-form__row"><input className={input} type="datetime-local" value={milestone.due_at} onChange={(event) => setMilestone({ ...milestone, due_at: event.target.value })} /><input className={input} type="number" min="0" max="100" value={milestone.completion_percent} onChange={(event) => setMilestone({ ...milestone, completion_percent: event.target.value })} /></div><button className="progress-button progress-button--violet" disabled={busy || !milestone.title.trim()}>{busy ? "Saving…" : "Add milestone"}</button></form></article><article className="progress-card"><div className="progress-card__heading"><span className="progress-card__icon progress-card__icon--mint">↗</span><div><h2>Tasks</h2><p>Turn each milestone into action.</p></div></div>{!tasks.length && <p className="progress-muted">No tasks recorded.</p>}{tasks.map((item) => <div className="progress-record" key={item.id}><div><strong>{item.title}</strong><span>{item.completion_percent}% · {item.overdue ? "Overdue" : dateLabel(item.due_at)}</span></div><div className="progress-record__update"><input aria-label={`Completion for ${item.title}`} type="number" min="0" max="100" defaultValue={item.completion_percent} /><button type="button" disabled={busy} onClick={(event) => { const field = event.currentTarget.parentElement?.querySelector("input"); void updateCompletion("tasks", item, field instanceof HTMLInputElement ? field.value : String(item.completion_percent)); }}>Update</button></div></div>)}<form className="progress-form" onSubmit={(event) => { event.preventDefault(); void save("tasks", { title: task.title, due_at: task.due_at || null, completion_percent: Number(task.completion_percent) }, () => setTask({ title: "", due_at: "", completion_percent: "0" })); }}><input className={input} required placeholder="Task title" value={task.title} onChange={(event) => setTask({ ...task, title: event.target.value })} /><div className="progress-form__row"><input className={input} type="datetime-local" value={task.due_at} onChange={(event) => setTask({ ...task, due_at: event.target.value })} /><input className={input} type="number" min="0" max="100" value={task.completion_percent} onChange={(event) => setTask({ ...task, completion_percent: event.target.value })} /></div><button className="progress-button progress-button--mint" disabled={busy || !task.title.trim()}>{busy ? "Saving…" : "Add task"}</button></form></article><article className="progress-card"><div className="progress-card__heading"><span className="progress-card__icon progress-card__icon--orange">◷</span><div><h2>Supervision</h2><p>Capture decisions and next steps.</p></div></div>{!data.meetings.length && <p className="progress-muted">No meeting records yet.</p>}{data.meetings.map((item) => <div className="progress-meeting" key={item.id}><strong>{new Date(item.held_at).toLocaleDateString()}</strong><span>{item.minutes}</span>{item.decisions && <small>{item.decisions}</small>}</div>)}<form className="progress-form" onSubmit={(event) => { event.preventDefault(); void save("meetings", { held_at: meeting.held_at, minutes: meeting.minutes, decisions: meeting.decisions || null, action_items: [] }, () => setMeeting({ held_at: "", minutes: "", decisions: "" })); }}><input className={input} type="datetime-local" required value={meeting.held_at} onChange={(event) => setMeeting({ ...meeting, held_at: event.target.value })} /><textarea className={input} required rows={3} placeholder="Meeting minutes" value={meeting.minutes} onChange={(event) => setMeeting({ ...meeting, minutes: event.target.value })} /><textarea className={input} rows={2} placeholder="Decisions (optional)" value={meeting.decisions} onChange={(event) => setMeeting({ ...meeting, decisions: event.target.value })} /><button className="progress-button progress-button--orange" disabled={busy || !meeting.held_at || !meeting.minutes.trim()}>{busy ? "Saving…" : "Record meeting"}</button></form></article></div>}
    </>}
    {message && <p role="status" className="student-request-success progress-toast">{message}</p>}
  </section>;
}
