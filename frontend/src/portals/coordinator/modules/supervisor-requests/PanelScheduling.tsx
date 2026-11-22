import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { localInputToIso } from "../../../../lib/localInputToIso";

type Option = { id: number; name?: string; email?: string; code?: string; academic_cycle_id?: number; academic_year?: number | null; session?: string | null };
type Schedule = { id: number; team_id: number; academic_cycle_id: number; start_at: string; end_at: string; room: string | null; online_link: string | null; status: string; panel_members: Option[]; conflict_note: string | null };
const input = "fy-input w-full";

function toLocalInput(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function cycleLabel(cycle: Option): string {
  const year = cycle.academic_year ? String(cycle.academic_year) : "";
  const session = cycle.session ? String(cycle.session) : "";
  const code = cycle.code ? ` · ${cycle.code}` : "";
  const base = [session, year].filter(Boolean).join(" ") || cycle.name || `Cycle ${cycle.id}`;
  return `${base}${code} (#${cycle.id})`;
}

export function PanelScheduling({ api }: { api: string }) {
  const [options, setOptions] = useState<{ teams: Option[]; evaluators: Option[]; cycles: Option[] }>({ teams: [], evaluators: [], cycles: [] });
  const [rows, setRows] = useState<Schedule[]>([]);
  const [form, setForm] = useState({ team_id: "", academic_cycle_id: "", start_at: "", end_at: "", room: "", online_link: "", panel_member_ids: [] as number[] });
  const [rescheduleRow, setRescheduleRow] = useState<Schedule | null>(null);
  const [rescheduleForm, setRescheduleForm] = useState({ start_at: "", end_at: "" });
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(true); const [message, setMessage] = useState(""); const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [optionsResponse, schedulesResponse] = await Promise.all([
        fetch(`${api}/api/v1/panel-schedules/options`, { credentials: "include" }),
        fetch(`${api}/api/v1/panel-schedules`, { credentials: "include" }),
      ]);
      const optionsBody = await optionsResponse.json().catch(() => ({}));
      const schedulesBody = await schedulesResponse.json().catch(() => ({}));
      if (!optionsResponse.ok) throw new Error(optionsBody.detail?.message ?? "Scheduling options could not be loaded.");
      if (!schedulesResponse.ok) throw new Error(schedulesBody.detail?.message ?? "Defense schedules could not be loaded.");
      setOptions(optionsBody as typeof options);
      setRows(schedulesBody as Schedule[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Defense schedules could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [load]);

  const selectedTeam = useMemo(() => options.teams.find((item) => item.id === Number(form.team_id)), [options.teams, form.team_id]);
  const cycleOptions = useMemo(() => {
    if (!selectedTeam?.academic_cycle_id) return options.cycles;
    return options.cycles.filter((cycle) => cycle.id === selectedTeam.academic_cycle_id);
  }, [options.cycles, selectedTeam]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (form.start_at && form.end_at && new Date(form.end_at) <= new Date(form.start_at)) {
      setError("End date/time must be after the start date/time.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/panel-schedules`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          team_id: Number(form.team_id),
          academic_cycle_id: Number(form.academic_cycle_id),
          start_at: localInputToIso(form.start_at),
          end_at: localInputToIso(form.end_at),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail?.message ?? "Defense schedule could not be saved.");
      setMessage("Defense schedule saved.");
      setForm({ team_id: "", academic_cycle_id: "", start_at: "", end_at: "", room: "", online_link: "", panel_member_ids: [] });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Defense schedule could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  const openReschedule = (row: Schedule) => {
    setRescheduleRow(row);
    setRescheduleForm({ start_at: toLocalInput(row.start_at), end_at: toLocalInput(row.end_at) });
    setError("");
  };

  const submitReschedule = async (event: FormEvent) => {
    event.preventDefault();
    if (!rescheduleRow || busy) return;
    if (!rescheduleForm.start_at || !rescheduleForm.end_at) {
      setError("Start and end date/time are required.");
      return;
    }
    if (new Date(rescheduleForm.end_at) <= new Date(rescheduleForm.start_at)) {
      setError("End date/time must be after the start date/time.");
      return;
    }
    setBusy(true); setError("");
    try {
      const response = await fetch(`${api}/api/v1/panel-schedules/${rescheduleRow.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_at: localInputToIso(rescheduleForm.start_at),
          end_at: localInputToIso(rescheduleForm.end_at),
          room: rescheduleRow.room,
          online_link: rescheduleRow.online_link,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail?.message ?? "Defense schedule could not be rescheduled.");
      setMessage("Defense schedule rescheduled.");
      setRescheduleRow(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Defense schedule could not be rescheduled.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="student-phase-page" aria-labelledby="panel-scheduling-heading">
      <div className="student-page-heading">
        <p className="student-overview__eyebrow">Coordinator workspace</p>
        <h1 id="panel-scheduling-heading">Panel Scheduling &amp; Defense</h1>
        <p>Assign active Evaluators and schedule conflict-checked defense sessions. Conflicts are rejected transactionally by the backend.</p>
      </div>
      {message && <p role="status" className="student-request-alert">{message}</p>}
      {error && <p role="alert" className="student-request-alert">{error}</p>}
      {loading ? (
        <div className="student-placeholder">Loading defense scheduling…</div>
      ) : (
        <div className="student-overview__grid">
          <form className="student-request-card grid gap-3" onSubmit={(event) => void save(event)}>
            <h2>Schedule a defense</h2>
            <label className="student-upload-label">
              Team
              <select
                className={input}
                required
                value={form.team_id}
                onChange={(event) => {
                  const team = options.teams.find((item) => item.id === Number(event.target.value));
                  setForm({
                    ...form,
                    team_id: event.target.value,
                    academic_cycle_id: team?.academic_cycle_id ? String(team.academic_cycle_id) : "",
                  });
                }}
              >
                <option value="">Select team</option>
                {options.teams.map((team) => (
                  <option key={team.id} value={team.id}>Team {team.id}{team.name ? ` · ${team.name}` : ""}</option>
                ))}
              </select>
            </label>
            <label className="student-upload-label">
              Academic cycle
              <select
                className={input}
                required
                value={form.academic_cycle_id}
                disabled={!form.team_id}
                onChange={(event) => setForm({ ...form, academic_cycle_id: event.target.value })}
              >
                <option value="">{form.team_id ? "Select cycle" : "Select a team first"}</option>
                {cycleOptions.map((cycle) => (
                  <option key={cycle.id} value={cycle.id}>{cycleLabel(cycle)}</option>
                ))}
              </select>
            </label>
            <label className="student-upload-label">
              Start
              <input className={input} required type="datetime-local" value={form.start_at} onChange={(event) => setForm({ ...form, start_at: event.target.value })} />
            </label>
            <label className="student-upload-label">
              End
              <input className={input} required type="datetime-local" value={form.end_at} onChange={(event) => setForm({ ...form, end_at: event.target.value })} />
            </label>
            <label className="student-upload-label">
              Room
              <input className={input} value={form.room} onChange={(event) => setForm({ ...form, room: event.target.value })} />
            </label>
            <label className="student-upload-label">
              Online link
              <input className={input} type="url" value={form.online_link} onChange={(event) => setForm({ ...form, online_link: event.target.value })} />
            </label>
            <fieldset className="panel-scheduling-fieldset">
              <legend className="panel-scheduling-legend">Evaluator panel</legend>
              <div className="panel-scheduling-checklist">
                {options.evaluators.map((item) => (
                  <label key={item.id} className="panel-scheduling-check">
                    <input
                      type="checkbox"
                      checked={form.panel_member_ids.includes(item.id)}
                      onChange={(event) => setForm({
                        ...form,
                        panel_member_ids: event.target.checked
                          ? [...form.panel_member_ids, item.id]
                          : form.panel_member_ids.filter((id) => id !== item.id),
                      })}
                    />
                    <span>{item.name} ({item.email})</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <button type="submit" className="fy-btn fy-btn--primary module3-primary-button panel-scheduling-submit" disabled={busy || !form.team_id || !form.start_at || !form.end_at}>
              {busy ? "Saving…" : "Create defense schedule"}
            </button>
          </form>

          <div className="student-request-card">
            <h2>Scheduled defenses</h2>
            {!rows.length && <p className="student-request-muted">No defense schedules have been created.</p>}
            {rows.map((row) => (
              <article key={row.id} className="border-b border-[#e8ede9] py-3">
                <strong>Team {row.team_id}</strong>
                <p>{new Date(row.start_at).toLocaleString()} – {new Date(row.end_at).toLocaleString()}</p>
                <small>{row.room ?? row.online_link ?? "Location pending"} · {row.panel_members.map((item) => item.name).join(", ") || "No Evaluators assigned"}</small>
                <div>
                  <button type="button" className="fy-btn fy-btn--secondary" disabled={busy || row.status === "CANCELLED"} onClick={() => openReschedule(row)}>
                    Reschedule
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}

      {rescheduleRow && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-fy-page/75 p-4" role="dialog" aria-modal="true" aria-labelledby="reschedule-heading">
          <form className="w-full max-w-md rounded-2xl border border-fy-border bg-fy-surface p-5 shadow-xl grid gap-3" onSubmit={(event) => void submitReschedule(event)}>
            <h2 id="reschedule-heading" className="text-lg font-bold text-fy-text">Reschedule Team {rescheduleRow.team_id}</h2>
            <label className="student-upload-label">
              New start
              <input className={input} required type="datetime-local" value={rescheduleForm.start_at} onChange={(event) => setRescheduleForm({ ...rescheduleForm, start_at: event.target.value })} />
            </label>
            <label className="student-upload-label">
              New end
              <input className={input} required type="datetime-local" value={rescheduleForm.end_at} onChange={(event) => setRescheduleForm({ ...rescheduleForm, end_at: event.target.value })} />
            </label>
            <div className="flex flex-wrap gap-2 justify-end">
              <button type="button" className="fy-btn fy-btn--secondary" disabled={busy} onClick={() => setRescheduleRow(null)}>Cancel</button>
              <button type="submit" className="fy-btn fy-btn--primary" disabled={busy}>{busy ? "Saving…" : "Save schedule"}</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
