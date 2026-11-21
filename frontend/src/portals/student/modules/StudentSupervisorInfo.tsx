import { useEffect, useState } from "react";
import "../student-supervisor-info.css";

type Group = {
  group_name: string;
  group_email: string | null;
  academic_cycle: string | null;
  supervisor?: { id: number; name: string } | null;
  supervisor_assignment?: { assigned_at: string } | null;
};

async function read<T>(url: string): Promise<T> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new Error("The group workspace could not be loaded.");
  return await response.json() as T;
}

export function StudentSupervisorInfo({ api }: { api: string }) {
  const [group, setGroup] = useState<Group | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void read<Group>(`${api}/api/v1/student/group/me`)
      .then(setGroup)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Supervisor information could not be loaded."));
  }, [api]);

  return <section className="student-phase-page student-supervisor-info" aria-labelledby="supervisor-info-heading">
    <div className="student-page-heading student-supervisor-info__heading">
      <p className="student-overview__eyebrow">Group workspace</p>
      <h1 id="supervisor-info-heading">Supervisor information</h1>
      <p>The supervisor assignment is shared across the group and synchronized with the approved university record.</p>
    </div>
    {error && <p role="alert" className="student-request-alert">{error}</p>}
    {!group && !error && <div className="student-placeholder">Loading supervisor information...</div>}
    {group && <div className="student-supervisor-info__cards">
      <article className="student-request-card student-supervisor-info__card">
        <h2>Assigned supervisor</h2>
        {group.supervisor ? <div className="student-supervisor-info__assignment">
          <h3>{group.supervisor.name}</h3>
          <p>Assigned {group.supervisor_assignment?.assigned_at ? new Date(group.supervisor_assignment.assigned_at).toLocaleDateString() : "date not recorded"}.</p>
          <span className="student-status student-status--implemented">Active assignment</span>
        </div> : <div className="student-supervisor-info__assignment">
          <p className="student-request-muted">No supervisor has been assigned yet.</p>
          <span className="student-status student-status--future">Pending selection</span>
        </div>}
      </article>
      <article className="student-request-card student-supervisor-info__card">
        <h2>Shared group identity</h2>
        <dl className="student-supervisor-info__identity">
          <div><dt>Workspace</dt><dd className="student-stat-value-clamp" title={group.group_name}>{group.group_name}</dd></div>
          <div><dt>Shared email</dt><dd>{group.group_email || "Not recorded"}</dd></div>
          <div><dt>Academic cycle</dt><dd>{group.academic_cycle || "Not recorded"}</dd></div>
        </dl>
      </article>
    </div>}
  </section>;
}
