import { useEffect, useState } from "react";

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

  return <section className="student-phase-page" aria-labelledby="supervisor-info-heading">
    <div className="student-page-heading"><p className="student-overview__eyebrow">Group workspace</p><h1 id="supervisor-info-heading">Supervisor information</h1><p>The supervisor assignment is shared across the group and synchronized with the approved university record.</p></div>
    {error && <p role="alert" className="student-request-alert">{error}</p>}
    {!group && !error && <div className="student-placeholder">Loading supervisor information…</div>}
    {group && <div className="student-request-layout">
      <article className="student-request-card"><h2>Assigned supervisor</h2>{group.supervisor ? <><h3 className="mt-4 text-xl font-semibold text-[#19365b]">{group.supervisor.name}</h3><p className="mt-4 text-sm text-[#607087]">Assigned {group.supervisor_assignment?.assigned_at ? new Date(group.supervisor_assignment.assigned_at).toLocaleDateString() : "date not recorded"}.</p><span className="student-status student-status--implemented mt-4">Active assignment</span></> : <><p className="student-request-muted mt-4">No supervisor has been assigned yet.</p><span className="student-status student-status--future mt-4">Pending selection</span></>}</article>
      <article className="student-request-card"><h2>Shared group identity</h2><dl className="mt-4 grid gap-3 text-sm"><div><dt className="font-semibold text-[#607087]">Workspace</dt><dd className="mt-1 font-semibold text-[#19365b]">{group.group_name}</dd></div><div><dt className="font-semibold text-[#607087]">Shared email</dt><dd className="mt-1 text-[#19365b]">{group.group_email || "Not recorded"}</dd></div><div><dt className="font-semibold text-[#607087]">Academic cycle</dt><dd className="mt-1 text-[#19365b]">{group.academic_cycle || "Not recorded"}</dd></div></dl></article>
    </div>}
  </section>;
}
