import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Alert } from "../../ui";
import { IconButton } from "../../ui/IconButton";
import { SupervisorGroupDetails, type GroupWorkspace, type GroupTab, date } from "./SupervisorGroupDetails";
import { pushPortalRoute, replacePortalRoute } from "../shared/portal-history";

const projectStatusLabel = (value?: string | null) => ({
  IN_PROGRESS: "In progress",
  NOT_STARTED: "Not started",
  COMPLETED: "Completed",
}[value || ""] || (value ? value.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : "Not started yet"));

const projectTitleLabel = (data: GroupWorkspace) => {
  const proposalTitle = data.proposal?.title?.trim();
  const projectTitle = data.project?.title?.trim();
  if (proposalTitle) return proposalTitle;
  if (projectTitle && !/'s project$/i.test(projectTitle) && projectTitle !== data.group.name) return projectTitle;
  return "No project title yet";
};

const validGroupTabs: GroupTab[] = ["overview", "members", "proposal", "project", "documents", "discussion"];
const groupSelectionFromLocation = () => {
  const match = window.location.pathname.match(/\/supervisor\/groups\/(\d+)/);
  if (!match) return null;
  const requestedTab = new URLSearchParams(window.location.search).get("tab") as GroupTab | null;
  return { id: Number(match[1]), tab: requestedTab && validGroupTabs.includes(requestedTab) ? requestedTab : "overview" };
};

export function SupervisorAssignedTeams({ api }: { api: string }) {
  const [groups, setGroups] = useState<GroupWorkspace[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [selected, setSelected] = useState<{ id: number; tab: GroupTab } | null>(groupSelectionFromLocation);
  const load = useCallback(async () => {
    try { const response = await fetch(`${api}/api/v1/supervisor/assigned-groups`, { credentials: "include" }); if (!response.ok) throw new Error("Assigned groups could not be loaded."); setGroups(await response.json() as GroupWorkspace[]); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Assigned groups could not be loaded."); }
    finally { setLoading(false); }
  }, [api]);
  useEffect(() => { const initial = window.setTimeout(() => void load(), 0); const timer = window.setInterval(() => void load(), 10000); const focus = () => void load(); window.addEventListener("focus", focus); return () => { window.clearTimeout(initial); window.clearInterval(timer); window.removeEventListener("focus", focus); }; }, [load]);
  useEffect(() => { const syncFromHistory = () => { const selection = groupSelectionFromLocation(); setSelected(selection); if (!selection) void load(); }; window.addEventListener("popstate", syncFromHistory); return () => window.removeEventListener("popstate", syncFromHistory); }, [load]);
  const open = (id: number, tab: GroupTab) => { setSelected({ id, tab }); pushPortalRoute(`/supervisor/groups/${id}?tab=${tab}`); };
  if (selected) return <SupervisorGroupDetails key={selected.id} api={api} groupId={selected.id} initialTab={selected.tab} onBack={() => { setSelected(null); replacePortalRoute("/supervisor/assigned-groups"); void load(); }} />;
  return <section className="supervisor-page" aria-labelledby="supervisor-assigned-heading">
    <div className="supervisor-page-heading"><h1 id="supervisor-assigned-heading">Assigned Students &amp; Teams</h1><span>Group members, proposals, documents and project progress for your active assignments.</span></div>
    {error && (
      <Alert tone="danger" title="Assigned groups unavailable" role="alert">
        <p className="m-0">{error}</p>
        <IconButton label="Retry assigned groups" size="sm" variant="secondary" className="mt-3" onClick={() => void load()}><RefreshCw size={15} strokeWidth={1.8} aria-hidden /></IconButton>
      </Alert>
    )}
    {loading ? <div className="supervisor-card">Loading assigned groups…</div> : error ? null : !groups.length ? <div className="supervisor-card">No active assignments. Accepted groups will appear here.</div> : <div className="supervisor-assignment-list">{groups.map(data => <article key={data.group.id} className="supervisor-card supervisor-assignment-card">
      <div className="supervisor-assignment-card__header"><div><span className="supervisor-section-kicker">ACTIVE ASSIGNMENT</span><h2>{data.group.name}</h2><p>{data.group.email} <span aria-hidden="true">·</span> {data.group.academic_cycle.name}</p></div><div className="supervisor-assignment-card__status"><span className="supervisor-status-pill supervisor-status-pill--neutral">{data.group.status.replaceAll("_", " ")}</span><span className="supervisor-status-pill supervisor-status-pill--blue">{data.assignment?.status?.replaceAll("_", " ") || "Awaiting decision"}</span></div></div>
      <div className="supervisor-assignment-highlights"><div><span>Supervisor</span><strong>{data.supervisor.name}</strong></div><div><span>Members</span><strong>{data.members.length} member{data.members.length === 1 ? "" : "s"}</strong></div><div><span>Completion</span><strong>{data.project?.completion_percentage == null ? "Not started" : `${data.project.completion_percentage}%`}</strong></div></div>
      <dl className="supervisor-assignment-details">{[
        ["Academic cycle", `${data.group.academic_cycle.name} · ${data.group.academic_cycle.year || "Year not set"} · ${data.group.academic_cycle.session || "Session not set"}`], ["Project title", projectTitleLabel(data)],
        ["Proposal", data.proposal?.status || "Not submitted yet"], ["Project", projectStatusLabel(data.project?.status)],
        ["Assigned", date(data.assignment?.assigned_at)], ["Last activity", date(data.group.last_activity_at)]
      ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <div className="supervisor-assignment-actions"><button type="button" onClick={() => open(data.group.id, "overview")} className="supervisor-assignment-primary">Open group workspace <span aria-hidden="true">→</span></button><div className="supervisor-assignment-secondary">{([["proposal", "Proposal"], ["project", "Project"], ["members", "Members"], ["documents", "Documents"], ["discussion", "Discussion"]] as [GroupTab, string][]).map(([tab, label]) => <button key={tab} type="button" onClick={() => open(data.group.id, tab)}>{label}</button>)}</div></div>
    </article>)}</div>}
  </section>;
}
