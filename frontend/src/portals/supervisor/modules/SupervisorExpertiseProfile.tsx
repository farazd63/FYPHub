import { useEffect, useState } from "react";
import "./supervisor-expertise-profile.css";

type Item = { name: string; evidence?: string; confidence?: number; verified?: boolean; category?: string };
type HistoryItem = { id: number; project_title: string; year?: number | null; source_type: string; source_verified: boolean };
type Profile = {
  id: number;
  department?: string | null;
  program?: string | null;
  designation?: string | null;
  biography?: string | null;
  degree?: string | null;
  specialization?: string | null;
  publications: Item[];
  preferred_categories: string[];
  profile_status: string;
  visibility_status: string;
  profile_version: number;
  expertise: Item[];
  skills: Item[];
  research_interests: Item[];
  history: HistoryItem[];
};
type Cycle = { id: number; display_name: string };

async function body<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail?.message || data?.detail || "The request failed.");
  return data as T;
}

const split = (value: string, evidence = "Supervisor-entered current profile information") =>
  value.split(",").map((item) => item.trim()).filter(Boolean).map((name) => ({ name, evidence, confidence: 1, verified: false }));

export function SupervisorExpertiseProfile({ api }: { api: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [cycleId, setCycleId] = useState("");
  const [capacity, setCapacity] = useState("3");
  const [available, setAvailable] = useState(true);
  const [expertise, setExpertise] = useState("");
  const [skills, setSkills] = useState("");
  const [interests, setInterests] = useState("");
  const [publications, setPublications] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [documentId, setDocumentId] = useState<number | null>(null);

  const syncLists = (next: Profile) => {
    setExpertise(next.expertise.map((item) => item.name).join(", "));
    setSkills(next.skills.map((item) => item.name).join(", "));
    setInterests(next.research_interests.map((item) => item.name).join(", "));
    setPublications(next.publications.map((item) => item.name).join(", "));
  };

  const load = async () => {
    try {
      const [nextProfile, nextCycles] = await Promise.all([
        body<Profile>(await fetch(`${api}/api/v1/supervisor-matching/profile`, { credentials: "include" })),
        body<Cycle[]>(await fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" })),
      ]);
      setProfile(nextProfile); syncLists(nextProfile); setCycles(nextCycles);
      if (nextCycles[0]) setCycleId(String(nextCycles[0].id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Profile could not be loaded."); }
  };

  useEffect(() => { void load(); }, [api]);

  const save = async () => {
    if (!profile) return;
    setBusy(true); setError("");
    try {
      const next = await body<Profile>(await fetch(`${api}/api/v1/supervisor-matching/profile`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({
          department: profile.department || null, program: profile.program || null, designation: profile.designation || null,
          biography: profile.biography || null, degree: profile.degree || null, specialization: profile.specialization || null,
          preferred_categories: [], expertise: split(expertise), skills: split(skills), research_interests: split(interests),
          publications: split(publications, "Supervisor-entered publication or project record"),
        }),
      }));
      setProfile(next); syncLists(next); setMessage("Current supervisor profile saved as a private draft.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Profile could not be saved."); }
    finally { setBusy(false); }
  };

  const submit = async () => {
    setBusy(true); setError("");
    try {
      const next = await body<Profile>(await fetch(`${api}/api/v1/supervisor-matching/profile/submit`, { method: "POST", credentials: "include" }));
      setProfile(next); setMessage("Profile submitted for coordinator verification.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Profile could not be submitted."); }
    finally { setBusy(false); }
  };

  const upload = async (file: File) => {
    setBusy(true); setError("");
    try {
      const form = new FormData(); form.append("document", file);
      const result = await body<{ id: number }>(await fetch(`${api}/api/v1/supervisor-matching/profile/documents`, { method: "POST", credentials: "include", body: form }));
      setDocumentId(result.id); setMessage("Document uploaded. Extract facts, review them, then confirm only what is accurate.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Document upload failed."); }
    finally { setBusy(false); }
  };

  const extract = async () => {
    if (!documentId) return;
    setBusy(true); setError("");
    try {
      await body(await fetch(`${api}/api/v1/supervisor-matching/profile/documents/${documentId}/extract`, { method: "POST", credentials: "include" }));
      setMessage("Draft facts extracted. Confirming them will add them to your editable profile.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Extraction failed."); }
    finally { setBusy(false); }
  };

  const confirm = async () => {
    if (!documentId) return;
    setBusy(true); setError("");
    try {
      const next = await body<Profile>(await fetch(`${api}/api/v1/supervisor-matching/profile/documents/${documentId}/confirm`, { method: "POST", credentials: "include" }));
      setProfile(next); syncLists(next); setMessage("Confirmed current facts added to the private draft profile.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Confirmation failed."); }
    finally { setBusy(false); }
  };

  const saveAvailability = async () => {
    if (!cycleId) return;
    setBusy(true); setError("");
    try {
      await body(await fetch(`${api}/api/v1/supervisor-matching/profile/availability/${cycleId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ available, maximum_capacity: Number(capacity) || 0 }),
      }));
      setMessage("Availability saved for the selected cycle.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Availability could not be saved."); }
    finally { setBusy(false); }
  };

  if (!profile) return <section className="expertise-page"><p>Loading expertise profile...</p></section>;

  return <section className="expertise-page">
    <div className="expertise-heading"><div><p className="expertise-eyebrow">SUPERVISOR PROFILE</p><h1>Make your current expertise discoverable</h1><p>Keep only current credentials, skills, research interests, publications, and capacity here. Supervision history is derived from the system.</p></div><div className="expertise-status"><span>{profile.profile_status.replaceAll("_", " ")}</span><small>v{profile.profile_version} · {profile.visibility_status.toLowerCase()}</small></div></div>
    {error && <p className="expertise-alert expertise-alert--error">{error}</p>}{message && <p className="expertise-alert">{message}</p>}
    <div className="expertise-grid">
      <article className="expertise-card expertise-card--wide"><div className="expertise-card__title"><div><p className="expertise-kicker">Current profile</p><h2>Academic credentials</h2></div><button type="button" className="expertise-button" disabled={busy} onClick={() => void save()}>Save draft</button></div><div className="expertise-fields"><label>Department<input value={profile.department || ""} onChange={(event) => setProfile({ ...profile, department: event.target.value })} /></label><label>Program<input value={profile.program || ""} onChange={(event) => setProfile({ ...profile, program: event.target.value })} /></label><label>Designation<input value={profile.designation || ""} onChange={(event) => setProfile({ ...profile, designation: event.target.value })} /></label><label>Degree<input value={profile.degree || ""} onChange={(event) => setProfile({ ...profile, degree: event.target.value })} placeholder="PhD in Computer Science" /></label><label>Specialization<input value={profile.specialization || ""} onChange={(event) => setProfile({ ...profile, specialization: event.target.value })} placeholder="Natural language processing" /></label><label className="expertise-full">Biography<textarea rows={4} value={profile.biography || ""} onChange={(event) => setProfile({ ...profile, biography: event.target.value })} /></label></div></article>
      <div className="expertise-column">
        <article className="expertise-card"><p className="expertise-kicker">Evidence map</p><h2>What you supervise</h2><label>Areas of expertise<textarea rows={3} value={expertise} onChange={(event) => setExpertise(event.target.value)} placeholder="Machine learning, information retrieval" /></label><label>Technical skills<textarea rows={3} value={skills} onChange={(event) => setSkills(event.target.value)} placeholder="Python, NLP, PostgreSQL" /></label><label>Research interests<textarea rows={3} value={interests} onChange={(event) => setInterests(event.target.value)} placeholder="Responsible AI, education technology" /></label></article>
        <article className="expertise-card"><p className="expertise-kicker">Document assist</p><h2>Import a CV or research summary</h2><p className="expertise-help">AI extracts a draft only. Nothing becomes public until you review and confirm it.</p><input type="file" accept=".pdf,.docx,.txt,.md" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} /><div className="expertise-actions"><button type="button" className="expertise-button expertise-button--outline" disabled={!documentId || busy} onClick={() => void extract()}>Extract facts</button><button type="button" className="expertise-button" disabled={!documentId || busy} onClick={() => void confirm()}>Confirm facts</button></div></article>
      </div>
      <div className="expertise-column">
        <article className="expertise-card"><p className="expertise-kicker">Relevant work</p><h2>Publications and projects</h2><p className="expertise-help">Add current, relevant records. The system derives old supervision history separately from project data.</p><label>Publication or project names<textarea rows={5} value={publications} onChange={(event) => setPublications(event.target.value)} placeholder="One publication or project per comma" /></label></article>
        <article className="expertise-card"><p className="expertise-kicker">Capacity signal</p><h2>Availability by cycle</h2><label>Academic cycle<select value={cycleId} onChange={(event) => setCycleId(event.target.value)}>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name}</option>)}</select></label><label className="expertise-check"><input type="checkbox" checked={available} onChange={(event) => setAvailable(event.target.checked)} /> Accept new supervision requests</label><label>Maximum groups<input type="number" min="0" value={capacity} onChange={(event) => setCapacity(event.target.value)} /></label><button type="button" className="expertise-button" disabled={busy || !cycleId} onClick={() => void saveAvailability()}>Save availability</button></article>
      </div>
      <article className="expertise-card expertise-card--wide"><p className="expertise-kicker">System-derived record</p><h2>Previous supervision history</h2><p className="expertise-help">These records are read-only. They are generated from archived projects and completed supervision assignments.</p>{profile.history.length ? <div className="expertise-history">{profile.history.map((item) => <div className="expertise-history__row" key={item.id}><strong>{item.project_title}</strong><span>{item.year || "Year unavailable"} · {item.source_type.replaceAll("_", " ")}</span></div>)}</div> : <p className="expertise-help">No derived supervision history is available yet.</p>}</article>
    </div>
    <div className="expertise-footer"><button type="button" className="expertise-button" disabled={busy || profile.profile_status === "PENDING_VERIFICATION"} onClick={() => void submit()}>Submit for verification</button><span>History records: {profile.history.length}. Only verified current profile evidence is used for matching.</span></div>
  </section>;
}
