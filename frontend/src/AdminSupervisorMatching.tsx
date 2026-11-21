import { useEffect, useState } from "react";
import { BadgeCheck, RefreshCw, X } from "lucide-react";
import { IconButton } from "./ui/IconButton";
import "./AdminSupervisorMatching.css";

type Profile = {
  id: number;
  supervisor_id: number;
  supervisor_name?: string;
  department?: string | null;
  program?: string | null;
  profile_status: string;
  visibility_status: string;
  profile_version: number;
  expertise: Array<{ name: string }>;
  research_interests: Array<{ name: string }>;
};

const defaultWeights = { expertise: 0.2, research_interest: 0.15, history: 0.25, methodology: 0.15, technology: 0.1, domain: 0.1, preference: 0.05 };

async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail?.message || data?.detail || "Request failed.");
  return data as T;
}

export function AdminSupervisorMatching({ api }: { api: string }) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [weights, setWeights] = useState(defaultWeights);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = async () => {
    try {
      setError("");
      setProfiles(await read<Profile[]>(await fetch(`${api}/api/v1/supervisor-matching/admin/profiles`, { credentials: "include" })));
      const config = await read<{ weights: typeof defaultWeights }>(await fetch(`${api}/api/v1/supervisor-matching/admin/config`, { credentials: "include" }));
      setWeights({ ...defaultWeights, ...config.weights });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Matching administration could not be loaded.");
    }
  };

  useEffect(() => { void load(); }, [api]);

  const verify = async (id: number, status: "VERIFIED" | "REJECTED") => {
    try {
      await read(await fetch(`${api}/api/v1/supervisor-matching/admin/profiles/${id}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ status }) }));
      setMessage(`Profile ${status.toLowerCase()}.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Profile review failed.");
    }
  };

  const save = async () => {
    try {
      const total = Object.values(weights).reduce((sum, value) => sum + value, 0);
      if (Math.abs(total - 1) > 0.01) throw new Error("Weights must add up to 1.");
      await read(await fetch(`${api}/api/v1/supervisor-matching/admin/config`, { method: "PUT", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ weights, eligibility_rules: {}, algorithm_version: "supervisor-matching-v1" }) }));
      setMessage("Matching configuration saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Configuration could not be saved.");
    }
  };

  return <section className="admin-supervisor-matching">
    <div className="admin-supervisor-matching__heading">
      <h1>Supervisor matching</h1>
      <p>Verify evidence before it becomes public, and keep the ranking policy visible to coordinators.</p>
    </div>

    {error && <p role="alert" className="admin-supervisor-matching__message admin-supervisor-matching__message--error">{error}</p>}
    {message && <p role="status" className="admin-supervisor-matching__message">{message}</p>}

    <article className="admin-supervisor-matching__panel">
      <div className="admin-supervisor-matching__panel-head">
        <div><p className="admin-supervisor-matching__eyebrow">Policy</p><h2>Weighted ranking</h2></div>
        <button type="button" className="fy-btn fy-btn--primary fy-btn--sm" onClick={() => void save()}>Save policy</button>
      </div>
      <div className="admin-supervisor-matching__weights">
        {Object.entries(weights).map(([key, value]) => <label key={key}>{key.replaceAll("_", " ")}<input type="number" min="0" max="1" step=".05" value={value} onChange={(event) => setWeights({ ...weights, [key]: Number(event.target.value) })} /></label>)}
      </div>
    </article>

    <article className="admin-supervisor-matching__panel">
      <div className="admin-supervisor-matching__panel-head">
        <div><p className="admin-supervisor-matching__eyebrow">Review queue</p><h2>Supervisor profiles</h2></div>
        <IconButton label="Refresh supervisor profiles" size="sm" variant="secondary" onClick={() => void load()}><RefreshCw size={18} strokeWidth={1.8} aria-hidden /></IconButton>
      </div>
      <div className="admin-supervisor-matching__profiles">
        {profiles.length ? profiles.map((profile) => <div key={profile.id} className="admin-supervisor-matching__profile">
          <div>
            <strong>{profile.supervisor_name || `Supervisor #${profile.supervisor_id}`}</strong>
            <p>{profile.department || "Department not set"} · {profile.profile_status.replaceAll("_", " ")}</p>
            <small>{profile.expertise.slice(0, 4).map((item) => item.name).join(" · ") || "No expertise evidence yet"}</small>
          </div>
          <div className="admin-supervisor-matching__actions" aria-label={`Review actions for ${profile.supervisor_name || `Supervisor ${profile.supervisor_id}`}`}>
            <IconButton label="Verify supervisor profile" size="sm" variant="primary" disabled={profile.profile_status === "VERIFIED"} onClick={() => void verify(profile.id, "VERIFIED")}><BadgeCheck size={18} strokeWidth={1.8} aria-hidden /></IconButton>
            <IconButton label="Reject supervisor profile" size="sm" variant="danger" disabled={profile.profile_status === "REJECTED"} onClick={() => void verify(profile.id, "REJECTED")}><X size={18} strokeWidth={1.8} aria-hidden /></IconButton>
          </div>
        </div>) : <p className="admin-supervisor-matching__empty">No supervisor profiles are awaiting review.</p>}
      </div>
    </article>
  </section>;
}
