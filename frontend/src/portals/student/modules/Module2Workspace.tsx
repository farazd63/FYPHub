import { useEffect, useState } from "react";
import { GroupChannels } from "../../../GroupChannels";
import { JoinRequestForm } from "../../../JoinRequests";
import { InviteeResponse } from "../../../Invitations";

type Member = { id: number; name: string; registration_number: string; email: string; is_creator: boolean };
type Workspace = { id: number; status: string; min_group_size: number | null; max_group_size: number | null; formation_deadline: string | null; formation_deadline_passed?: boolean; lock_reason: string | null; members: Member[]; channels: Array<{ id: string; label: string }> };

const statusTone: Record<string, string> = { forming: "bg-amber-50 text-amber-800 border-amber-200", complete: "bg-emerald-50 text-emerald-800 border-emerald-200", locked: "bg-slate-100 text-slate-700 border-slate-200", dissolved: "bg-red-50 text-red-700 border-red-200" };

export function Module2Workspace({ api }: { api: string }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => { try { const response = await fetch(`${api}/api/v1/module-2/workspace`, { credentials: "include" }); if (!response.ok) throw new Error(); setWorkspace(await response.json() as Workspace); setError(""); } catch { setError("Team workspace could not be loaded. Create or join a team first."); } };
  useEffect(() => { void load(); }, [api]);
  const dissolve = async () => { if (!workspace || busy || !window.confirm("Dissolve this team? Existing members and pending requests will be deactivated.")) return; setBusy(true); try { const response = await fetch(`${api}/api/v1/module-2/teams/${workspace.id}/dissolve`, { method: "POST", credentials: "include" }); if (!response.ok) throw new Error(); await load(); } catch { setError("The team could not be dissolved."); } finally { setBusy(false); } };
  return <section className="mt-5 rounded-2xl border border-[#dce4de] bg-white p-5" aria-labelledby="module2-workspace-heading">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[#176b66]">Module 2 · Team workspace</p><h2 id="module2-workspace-heading" className="mt-1 text-xl font-bold text-[#17312f]">Verified team and collaboration hub</h2><p className="mt-1 text-sm text-[#4f6470]">Group size rules come from the active academic cycle. Matching is opt-in and advisory; membership is transactionally verified.</p></div>{workspace && <span className={`rounded-full border px-3 py-1 text-xs font-bold uppercase ${statusTone[workspace.status] ?? statusTone.forming}`}>{workspace.status}</span>}</div>
    {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
    {workspace && <><div className="mt-5 grid gap-3 md:grid-cols-3"><div className="rounded-xl border border-[#dce4de] bg-[#f8fbf9] p-4"><p className="text-xs font-semibold uppercase text-[#60716b]">Members</p><p className="mt-1 text-2xl font-bold text-[#17312f]">{workspace.members.length}<span className="text-sm font-medium text-[#60716b]"> / {workspace.max_group_size ?? "—"}</span></p><p className="text-xs text-[#60716b]">Minimum {workspace.min_group_size ?? "not configured"}</p></div><div className="rounded-xl border border-[#dce4de] bg-[#f8fbf9] p-4"><p className="text-xs font-semibold uppercase text-[#60716b]">Formation deadline</p><p className="mt-2 text-sm font-semibold text-[#17312f]">{workspace.formation_deadline ? new Date(workspace.formation_deadline).toLocaleString() : "No deadline configured"}</p></div><div className="rounded-xl border border-[#dce4de] bg-[#f8fbf9] p-4"><p className="text-xs font-semibold uppercase text-[#60716b]">Workspace channels</p><p className="mt-2 text-sm font-semibold text-[#17312f]">{workspace.channels.length} active channels</p></div></div>{workspace.formation_deadline_passed && <p role="alert" className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">The formation deadline has passed while this team is below the required minimum. Contact the coordinator before submitting a proposal.</p>}<div className="mt-4 flex flex-wrap gap-2">{workspace.members.map(member => <span key={member.id} className="rounded-full border border-[#dce4de] bg-white px-3 py-1 text-xs text-[#17312f]">{member.name}{member.is_creator ? " · Leader" : ""}</span>)}</div>{workspace.lock_reason && <p className="mt-3 text-sm text-[#60716b]">Locked because: {workspace.lock_reason}.</p>}{workspace.status !== "locked" && workspace.status !== "dissolved" && <button type="button" onClick={() => void dissolve()} disabled={busy} className="mt-4 rounded-lg border border-red-200 px-3 py-2 text-sm font-semibold text-red-700 disabled:opacity-50">Dissolve team</button>}</>}
    <GroupChannels api={api} role="STUDENT" />
    <JoinRequestForm api={api} />
    <InviteeResponse api={api} />
  </section>;
}
