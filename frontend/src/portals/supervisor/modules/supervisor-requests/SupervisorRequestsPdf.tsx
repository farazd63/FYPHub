import { useCallback, useEffect, useState } from "react";
import { RequestConversation } from "./RequestConversation";
import { GroupDetailsContent, type GroupWorkspace, date } from "../../SupervisorGroupDetails";

type RequestRecord = { id: number; title: string | null; summary: string | null; requester_name: string; group_email: string | null; academic_cycle_name: string; status: string; revision: number; capacity_used: number; capacity_limit: number | null; capacity_remaining: number | null; submitted_at: string | null; submission_note: string | null; workspace: GroupWorkspace | null };
export function SupervisorRequestsPdf({ api }: { api: string }) {
  const [rows, setRows] = useState<RequestRecord[]>([]), [selectedId, setSelectedId] = useState<number | null>(null), [comment, setComment] = useState(""), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const selected = rows.find(r => r.id === selectedId);
  const load = useCallback(async () => { try { const response = await fetch(`${api}/api/v1/supervisor/requests`, { credentials: "include" }); if (!response.ok) throw new Error("Supervisor requests could not be loaded."); setRows(await response.json() as RequestRecord[]); } catch (e) { setMessage(e instanceof Error ? e.message : "Supervisor requests could not be loaded."); } finally { setLoading(false); } }, [api]);
  useEffect(() => { const initial = window.setTimeout(() => void load(), 0); const timer = window.setInterval(() => void load(), 10000); return () => { window.clearTimeout(initial); window.clearInterval(timer); }; }, [load]);
  const decide = async (action: "accept" | "reject" | "request-changes") => {
    if (!selected || busy) return;
    if (action !== "accept" && !comment.trim()) { setMessage("Enter a reason for rejection or requested changes."); return; }
    setBusy(true); setMessage("");
    try { const response = await fetch(`${api}/api/v1/supervisor/requests/${selected.id}/${action}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ comment: comment.trim() || null, revision: selected.revision }) }); const body = await response.json(); if (!response.ok) throw new Error(body.detail?.message || body.detail || "Decision could not be saved."); setSelectedId(null); setComment(""); await load(); setMessage(action === "accept" ? "Request accepted. The group is now available in Assigned Students & Teams." : action === "reject" ? "Request rejected. The reason is saved in the group's request history." : "Changes requested. Your comments are available to the group."); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Decision could not be saved."); }
    finally { setBusy(false); }
  };
  return <section className="supervisor-page" aria-labelledby="supervisor-requests-heading"><div className="supervisor-page-heading"><h1 id="supervisor-requests-heading">Supervisor Requests</h1><span>Review complete group details and discuss the proposal before deciding.</span></div>
    {message && <p className="supervisor-alert" role="status">{message} <button type="button" onClick={() => void load()}>Refresh</button></p>}
    {loading ? <div className="supervisor-card">Loading requests…</div> : !rows.length ? <div className="supervisor-card">No pending supervisor requests.</div> : <div className="grid gap-4">
      <div className="supervisor-card"><h2>Pending requests</h2><div className="mt-3 grid gap-3 sm:grid-cols-2">{rows.map(row => <button type="button" key={row.id} onClick={() => { setSelectedId(row.id); setComment(""); }} className="rounded-xl border p-4 text-left" aria-pressed={row.id === selectedId}><strong className="block">{row.workspace?.group.name || row.requester_name}</strong><span className="block text-sm">{row.group_email}</span><span className="block text-sm">{row.title || "Proposal not submitted yet"}</span><small>{row.academic_cycle_name} · {row.status}</small><span className="mt-2 block text-sm underline">View complete details</span></button>)}</div></div>
      {selected && <article className="supervisor-card"><h2>{selected.workspace?.group.name || selected.requester_name}</h2><p>{selected.workspace?.group.email || selected.group_email}</p><p className="my-3 text-sm">Requested {date(selected.submitted_at)} · Capacity {selected.capacity_used} / {selected.capacity_limit ?? "Not configured"} · {selected.capacity_remaining ?? "Unknown"} remaining slots</p>{selected.submission_note && <div className="mb-4 rounded-lg border p-3"><strong>Request message</strong><p className="whitespace-pre-wrap">{selected.submission_note}</p></div>}
        {selected.workspace ? <GroupDetailsContent key={selected.id} api={api} data={selected.workspace} /> : <p>No group is linked to this request.</p>}
        <div className="mt-5"><RequestConversation api={api} requestId={selected.id} /></div><label className="mt-4 grid gap-2">Decision comment<textarea rows={4} maxLength={2000} value={comment} onChange={e => setComment(e.target.value)} className="rounded border p-3" placeholder="Feedback, required changes, or rejection reason" /></label><div className="supervisor-actions mt-4"><button type="button" disabled={busy} onClick={() => void decide("request-changes")}>Request changes</button><button type="button" disabled={busy} onClick={() => void decide("reject")}>Reject request</button><button type="button" disabled={busy || !selected.workspace || selected.capacity_remaining === 0} onClick={() => void decide("accept")}>Accept request</button></div>
      </article>}
    </div>}
  </section>;
}
