import { useEffect, useState } from "react";

type Cycle = { id: number; display_name: string; code: string };
type Policy = { max_group_size?: number } | null;

export function CoordinatorGroupPolicies({ api }: { api: string }) {
  const [rows, setRows] = useState<Array<{ cycle: Cycle; policy: Policy }>>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  useEffect(() => { let active = true; void (async () => { try { const response = await fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" }); if (!response.ok) throw new Error(); const cycles = await response.json() as Cycle[]; const result = await Promise.all(cycles.map(async (cycle) => { const policyResponse = await fetch(`${api}/api/v1/academic-cycles/${cycle.id}/group-policy`, { credentials: "include" }); return { cycle, policy: policyResponse.ok ? await policyResponse.json() as Policy : null }; })); if (active) { setRows(result); setState("ready"); } } catch { if (active) setState("error"); } })(); return () => { active = false; }; }, [api]);
  return <section className="student-phase-page" aria-labelledby="coordinator-group-policy-heading"><div className="student-page-heading"><p className="student-overview__eyebrow">Academic Operations</p><h1 id="coordinator-group-policy-heading">Group Policies</h1><p>Read-only cycle group-size policies from the authorized academic-cycle service.</p></div>{state === "loading" ? <p role="status" className="student-placeholder">Loading group policies…</p> : state === "error" ? <p role="alert" className="student-request-alert">Group policies could not be loaded. Please retry from the Academic Cycles section.</p> : !rows.length ? <p className="student-placeholder">No academic cycles are available.</p> : <div className="mt-5 grid gap-3">{rows.map(({ cycle, policy }) => <article key={cycle.id} className="rounded-xl border bg-white p-5"><h2 className="font-semibold">{cycle.display_name} <span className="text-sm font-normal text-slate-500">({cycle.code})</span></h2><p className="mt-2 text-sm">Maximum group size: <strong>{policy?.max_group_size ?? "Not configured"}</strong></p></article>)}</div>}</section>;
}
