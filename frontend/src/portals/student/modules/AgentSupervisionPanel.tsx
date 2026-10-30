import { useState } from "react";

type Run = { id: number; state: string; approval_status: string; plan?: { milestones?: Array<{ title: string; due_at: string; tasks?: Array<{ title: string; due_at: string; dependencies?: string[] }> }> }; result?: { created_tasks?: string[] }; error?: string };

export function AgentSupervisionPanel({ api, teamId }: { api: string; teamId?: number }) {
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function generate() {
    if (!teamId) return setError("Your team is not available yet.");
    setBusy(true); setError("");
    try { const response = await fetch(`${api}/api/v1/agent-supervision/${teamId}/runs`, { method: "POST", credentials: "include" }); if (!response.ok) throw new Error("Agent plan unavailable"); setRun(await response.json()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Agent plan unavailable"); }
    finally { setBusy(false); }
  }
  return <section className="student-request-card" aria-label="Agentic supervision"><h2>Agentic supervision</h2><p>Generate a draft plan from the accepted proposal. A Supervisor must approve it before any milestones or tasks are saved.</p><button type="button" onClick={() => void generate()} disabled={busy || !teamId}>{busy ? "Generating project plan..." : "Generate project plan"}</button>{error && <p role="alert">{error}</p>}{run && <div role="status"><p>Run status: {run.state} · Approval: {run.approval_status}</p>{run.plan?.milestones?.map(milestone => <article key={milestone.title}><strong>{milestone.title}</strong><p>Due {new Date(milestone.due_at).toLocaleDateString()}</p>{milestone.tasks?.map(task => <p key={task.title}>Task: {task.title} · Due {new Date(task.due_at).toLocaleDateString()}</p>)}</article>)}{run.result?.created_tasks && <p>Created tasks: {run.result.created_tasks.length}</p>}{run.error && <p role="alert">{run.error}</p>}</div>}</section>;
}
