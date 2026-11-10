import { useEffect, useState } from "react";

type Result = { value: unknown; error: string | null };

const load = async (url: string): Promise<Result> => {
  try {
    const response = await fetch(url, { credentials: "include" });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) return { value: null, error: `HTTP ${response.status}` };
    return { value: body, error: null };
  } catch {
    return { value: null, error: "Network error" };
  }
};

const rows = (value: unknown): unknown[] => Array.isArray(value) ? value : value && typeof value === "object" && Array.isArray((value as { results?: unknown }).results) ? (value as { results: unknown[] }).results : [];

export function CoordinatorOverview({ api }: { api: string }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<Record<string, Result>>({});
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    // Keep the current snapshot visible while a retry is in flight.
    void Promise.all(["/api/v1/academic-cycles", "/api/v1/supervisor-requests/coordinator/monitor", "/api/v1/fyp-registry/coordinator", "/api/v1/dashboard/deadlines", "/api/v1/document-requirements"].map(async (path) => [path, await load(`${api}${path}`)] as const)).then((entries) => {
      if (!active) return;
      setData(Object.fromEntries(entries));
      setLoading(false);
    });
    return () => { active = false; };
  }, [api, retry]);
  const count = (path: string) => data[path]?.error ? "Unavailable" : rows(data[path]?.value).length;
  return <section className="student-phase-page" aria-labelledby="coordinator-overview-heading">
    <div className="student-page-heading"><p className="student-overview__eyebrow">Coordinator workspace</p><h1 id="coordinator-overview-heading">Overview</h1><p>Live operational signals from authorized academic, project, request, deadline, and document services.</p></div>
    {loading ? <p role="status" className="student-placeholder">Loading coordinator overview…</p> : <>
      {Object.values(data).some((item) => item.error) && <div role="alert" className="student-request-alert">Some coordinator data could not be loaded. Individual cards identify unavailable sources.<button type="button" className="ml-3 underline" onClick={() => setRetry((value) => value + 1)}>Retry</button></div>}
      <div className="student-overview__grid">
        {[['Academic cycles', '/api/v1/academic-cycles'], ['Projects in registry', '/api/v1/fyp-registry/coordinator'], ['Supervisor requests', '/api/v1/supervisor-requests/coordinator/monitor'], ['Deadlines & requirements', '/api/v1/dashboard/deadlines'], ['Document requirements', '/api/v1/document-requirements']].map(([label, path]) => <article className="student-phase-card" key={path}><span className="student-status student-status--implemented">Live</span><strong>{label}</strong><span className="text-2xl font-bold">{count(path)}</span><span className="text-sm text-slate-600">Authorized records available</span></article>)}
      </div>
      <div className="mt-6 rounded-xl border bg-white p-5"><h2 className="text-xl font-semibold">Next actions</h2><p className="mt-1 text-sm text-slate-600">Open a workspace section to inspect the underlying records. Counts are not fabricated when an authorized service is unavailable.</p></div>
    </>}
  </section>;
}
