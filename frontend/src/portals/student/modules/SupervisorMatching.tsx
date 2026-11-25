import { useCallback, useEffect, useMemo, useState } from "react";
import "./supervisor-selection/supervisor-selection.css";
import "./supervisor-matching.css";

type Cycle = { id: number; code: string; display_name: string };
type Supervisor = {
  id: number;
  name: string;
  assigned_count: number;
  remaining_capacity: number;
  available: boolean;
};
type History = {
  id: number;
  from_status: string | null;
  to_status: string;
  comment: string | null;
  actor_name: string;
  created_at: string;
};
type RequestRecord = {
  id: number;
  academic_cycle_id: number;
  academic_cycle_name: string;
  supervisor_id: number;
  supervisor_name: string;
  title: string | null;
  summary: string | null;
  submission_note: string | null;
  status: string;
  revision: number;
  updated_at: string;
  status_history: History[];
};
type MatchingLock = { locked: boolean; supervisor_name: string | null; message: string | null };

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body?.detail === "object" ? body.detail?.message : body?.detail;
    throw new Error(typeof detail === "string" ? detail : fallback);
  }
  return body as T;
}

const statusClass = (status: string) =>
  status === "ACCEPTED" ? "student-status--implemented" : status === "CHANGES_REQUESTED" ? "student-status--partial" : "student-status--future";

const activeStatuses = new Set(["DRAFT", "SUBMITTED", "CHANGES_REQUESTED", "ACCEPTED"]);

export function SupervisorMatching({ api }: { api: string }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [cycleId, setCycleId] = useState("");
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [requests, setRequests] = useState<RequestRecord[]>([]);
  const [selected, setSelected] = useState<Supervisor | null>(null);
  const [note, setNote] = useState("");
  const [lock, setLock] = useState<MatchingLock>({ locked: false, supervisor_name: null, message: null });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const cycle = useMemo(() => cycles.find((item) => String(item.id) === cycleId), [cycles, cycleId]);
  const activeRequest = requests.find((item) => activeStatuses.has(item.status));
  const locked = lock.locked;

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [cyclesResponse, requestsResponse, lockResponse] = await Promise.all([
        fetch(`${api}/api/v1/supervisor-requests/cycles`, { credentials: "include" }),
        fetch(`${api}/api/v1/supervisor-requests/mine`, { credentials: "include" }),
        fetch(`${api}/api/v1/supervisor-matching/lock-status`, { credentials: "include" }),
      ]);
      const [availableCycles, mine, currentLock] = await Promise.all([
        readJson<Cycle[]>(cyclesResponse, "Academic cycles could not be loaded."),
        readJson<RequestRecord[]>(requestsResponse, "Supervisor requests could not be loaded."),
        readJson<MatchingLock>(lockResponse, "Supervisor status could not be loaded."),
      ]);
      setCycles(availableCycles);
      setRequests(mine);
      setLock(currentLock);
      setCycleId((current) => current || String(availableCycles[0]?.id ?? ""));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Supervisor selection data could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void loadBase();
  }, [loadBase]);

  useEffect(() => {
    if (!cycleId) {
      setSupervisors([]);
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(`${api}/api/v1/supervisor-requests/supervisors?academic_cycle_id=${cycleId}`, { credentials: "include", signal: controller.signal });
        setSupervisors(await readJson<Supervisor[]>(response, "Eligible supervisors could not be loaded."));
        setSelected(null);
      } catch (reason) {
        if (!controller.signal.aborted) {
          setSupervisors([]);
          setError(reason instanceof Error ? reason.message : "Eligible supervisors could not be loaded.");
        }
      }
    })();
    return () => controller.abort();
  }, [api, cycleId]);

  const generateRequest = async () => {
    if (busy || locked || activeRequest || !cycleId || !selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${api}/api/v1/supervisor-requests/manual`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ academic_cycle_id: Number(cycleId), supervisor_id: selected.id, submission_note: note.trim() || null }),
      });
      const result = await readJson<RequestRecord>(response, "The supervisor request could not be created.");
      setRequests((current) => [result, ...current.filter((item) => item.id !== result.id)]);
      setSelected(null);
      setNote("");
      setNotice(`Request sent to ${result.supervisor_name}. You can follow its status below.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The supervisor request could not be created.");
    } finally {
      setBusy(false);
    }
  };

  return <section className="student-phase-page supervisor-simple-page" aria-labelledby="supervisor-selection-heading">
    <div className="student-page-heading">
      <p className="student-overview__eyebrow">Student research phase</p>
      <h1 id="supervisor-selection-heading">Choose your supervisor</h1>
      <p>Select one available supervisor from the list and generate a request. The selected supervisor will review it from their request queue.</p>
    </div>
    {error && <p className="student-request-alert" role="alert">{error}</p>}
    {notice && <p className="student-request-alert" role="status">{notice}</p>}
    {locked && <div className="matching-lock" role="status"><span className="matching-lock__icon" aria-hidden="true">✓</span><div><strong>Supervisor assignment confirmed</strong><p>{lock.message || `Your request was accepted${lock.supervisor_name ? ` by ${lock.supervisor_name}` : ""}.`}</p></div><span className="matching-lock__badge">LOCKED</span></div>}
    {loading ? <div className="student-placeholder">Loading supervisor selection...</div> : <>
      <div className="student-request-layout">
        <article className="student-request-card">
          <div className="student-request-card__heading">
            <h2>Available supervisors</h2>
            <label>Academic cycle<select className="student-request-input" value={cycleId} onChange={(event) => setCycleId(event.target.value)} disabled={busy || locked || Boolean(activeRequest)}><option value="">Select a cycle</option>{cycles.map((item) => <option key={item.id} value={item.id}>{item.display_name} ({item.code})</option>)}</select></label>
          </div>
          {!cycles.length ? <p className="student-request-muted">No active academic cycles are available.</p> : !supervisors.length ? <p className="student-request-muted">No supervisors are available for this cycle.</p> : <div className="student-supervisor-list">{supervisors.map((item) => <button key={item.id} type="button" className={`student-supervisor-option ${selected?.id === item.id ? "student-supervisor-option--selected" : ""}`} disabled={!item.available || busy || locked || Boolean(activeRequest)} onClick={() => setSelected(item)}><span><strong>{item.name}</strong><small>{item.assigned_count} assigned · {item.remaining_capacity} remaining</small></span><span className={`student-status ${item.available ? "student-status--partial" : "student-status--future"}`}>{item.available ? "Available" : "Full"}</span></button>)}</div>}
        </article>
        <article className="student-request-card">
          <h2>Generate request</h2>
          <p className="student-request-muted">{activeRequest ? `You already have an active request for ${activeRequest.supervisor_name}.` : selected ? `You selected ${selected.name} for ${cycle?.display_name ?? "this cycle"}.` : "Select one available supervisor to continue."}</p>
          <label>Message to supervisor <textarea className="student-request-input" rows={6} maxLength={4000} value={note} onChange={(event) => setNote(event.target.value)} disabled={!selected || busy || locked || Boolean(activeRequest)} placeholder="Optional message" /></label>
          <div className="student-request-actions"><button type="button" disabled={busy || locked || Boolean(activeRequest) || !selected} onClick={() => void generateRequest()}>{busy ? "Sending..." : "Generate request"}</button></div>
        </article>
      </div>
      <article className="student-request-card student-request-card--full">
        <h2>My supervisor requests</h2>
        {!requests.length ? <p className="student-request-muted">No supervisor requests yet.</p> : <div className="student-request-list">{requests.map((item) => <article key={item.id}><div className="student-request-list__top"><div><strong>{item.supervisor_name}</strong><small>{item.academic_cycle_name} · {item.title}</small></div><span className={`student-status ${statusClass(item.status)}`}>{item.status}</span></div>{item.submission_note && <p>{item.submission_note}</p>}{item.status_history?.length > 0 && <div className="student-request-history">{item.status_history.map((entry) => <div key={entry.id}><strong>{entry.to_status}</strong><span>{entry.actor_name} · {new Date(entry.created_at).toLocaleString()}</span>{entry.comment && <q>{entry.comment}</q>}</div>)}</div>}</article>)}</div>}
      </article>
    </>}
  </section>;
}
