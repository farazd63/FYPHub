import { useEffect, useState } from "react";
import { StatusBadge } from "./ui";
import { shortGroupLabel, sortGroupsDesc } from "./lib/displayLabels";
import "./AdminOverview.css";

type Person = { id: number; name: string; full_name?: string; email: string; registration_number?: string | null };
type CycleDetail = {
  cycle: { id: number; code: string; display_name: string; registration_open: boolean; status: string };
  summary: { supervisors: number; students: number; groups: number; projects: number; active_projects: number; completed_projects: number; pending_reviews: number; required_documents: number };
  coordinators: Person[];
  supervisors: Array<Person & { assigned_students: number; assigned_groups: number; active_projects: number; capacity: number | null; capacity_used: number; available_capacity: number | null; assignment_status: string }>;
  groups: Array<{ id: number; name: string; group_number: number | null; leader: Person | null; members: Person[]; assigned_supervisor: Person | null; project_title: string | null; status: string }>;
  projects: Array<{ id: number; title: string; student_or_group: string | number; supervisor: Person | null; proposal_status: string; project_stage: string; last_updated: string | null }>;
  documents: Array<{ id: number; title: string; status: string; due_at: string; submissions: Array<{ id: number; status: string; version_count: number }> }>;
};

const dateText = (value: string | null | undefined) => value ? new Date(value).toLocaleDateString() : "Not recorded";
const personName = (person: Person | null | undefined) => person?.name || person?.full_name || "Not assigned";

export function AdminCycleDetails({ api, cycleId }: { api: string; cycleId: number }) {
  const [detail, setDetail] = useState<CycleDetail | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      setState("loading");
      setDetail(null);
      setError("");
      void fetch(`${api}/api/v1/academic-cycles/${cycleId}/overview`, { credentials: "include" })
        .then(async (response) => {
          const body = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Cycle details could not be loaded.");
          return body as CycleDetail;
        })
        .then((body) => {
          if (!cancelled) { setDetail(body); setState("ready"); }
        })
        .catch((reason: unknown) => {
          if (!cancelled) { setError(reason instanceof Error ? reason.message : "Cycle details could not be loaded."); setState("error"); }
        });
    }, 0);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [api, cycleId]);

  return <section className="cycle-detail-page" aria-labelledby="cycle-detail-page-heading">
    <div className="cycle-detail-page__topbar">
      {detail && <StatusBadge status={detail.cycle.registration_open ? "OPEN" : "CLOSED"} />}
    </div>
    <div className="cycle-detail-page__heading">
      <p className="cycle-detail__eyebrow">Academic cycle details</p>
      <h1 id="cycle-detail-page-heading">{detail?.cycle.display_name || "Cycle details"}</h1>
      <p>Review groups, students, supervisors, coordinators, projects, and required documents in one focused workspace.</p>
    </div>
    {state === "loading" && <div className="cycle-detail cycle-detail--loading">Loading cycle details...</div>}
    {state === "error" && <div role="alert" className="cycle-detail cycle-detail--error">{error}<button type="button" className="cycle-detail-page__retry" onClick={() => window.location.reload()}>Retry</button></div>}
    {state === "ready" && detail && <CycleDetailWorkspace detail={detail} />}
  </section>;
}

function CycleDetailWorkspace({ detail }: { detail: CycleDetail }) {
  const displayGroups = sortGroupsDesc(detail.groups.map((group) => ({ ...group, academic_cycle: detail.cycle.display_name }))).map((group) => ({
    ...group,
    name: shortGroupLabel(group.name, detail.cycle.display_name),
  }));
  return <>
    <div className="cycle-detail__summary">{[["Groups", detail.summary.groups], ["Students", detail.summary.students], ["Supervisors", detail.summary.supervisors], ["Projects", detail.summary.projects], ["Pending reviews", detail.summary.pending_reviews], ["Required documents", detail.summary.required_documents]].map(([label, value]) => <div key={String(label)}><strong>{value}</strong><span>{label}</span></div>)}</div>
    <div className="cycle-detail__columns">
      <article className="cycle-detail__section"><h2>Groups</h2>{!detail.groups.length ? <p className="cycle-detail__empty">No groups are registered in this cycle.</p> : <div className="cycle-detail__list">{displayGroups.map((group) => <div className="cycle-detail__list-item" key={group.id}><div><strong>{group.name}</strong><span>{group.project_title || "Final title not set"}</span><small>{group.members.length} member(s) · Leader: {personName(group.leader)}</small></div><em>{group.assigned_supervisor ? personName(group.assigned_supervisor) : "Unassigned"}</em></div>)}</div>}</article>
      <article className="cycle-detail__section"><h2>Supervisors</h2>{!detail.supervisors.length ? <p className="cycle-detail__empty">No supervisor activity is recorded for this cycle.</p> : <div className="cycle-detail__list">{detail.supervisors.map((supervisor) => <div className="cycle-detail__list-item" key={supervisor.id}><div><strong>{personName(supervisor)}</strong><span>{supervisor.email}</span><small>{supervisor.assigned_groups} group(s) · {supervisor.assigned_students} student(s)</small></div><em>{supervisor.available_capacity == null ? "Capacity not set" : `${supervisor.available_capacity} remaining`}</em></div>)}</div>}</article>
      <article className="cycle-detail__section"><h2>Coordinators</h2>{!detail.coordinators.length ? <p className="cycle-detail__empty">No active coordinator accounts found.</p> : <div className="cycle-detail__list">{detail.coordinators.map((coordinator) => <div className="cycle-detail__list-item" key={coordinator.id}><div><strong>{personName(coordinator)}</strong><span>{coordinator.email}</span></div><em>Cycle access</em></div>)}</div>}</article>
    </div>
    <div className="cycle-detail__columns cycle-detail__columns--lower">
      <article className="cycle-detail__section"><h2>Projects and requests</h2>{!detail.projects.length ? <p className="cycle-detail__empty">No proposal or supervision requests are recorded.</p> : <div className="cycle-detail__list">{detail.projects.map((project) => <div className="cycle-detail__list-item" key={project.id}><div><strong>{project.title}</strong><span>{project.supervisor ? `Supervisor: ${personName(project.supervisor)}` : "Supervisor not assigned"}</span><small>{project.proposal_status} · Updated {dateText(project.last_updated)}</small></div><em>{project.student_or_group}</em></div>)}</div>}</article>
      <article className="cycle-detail__section"><h2>Documents</h2>{!detail.documents.length ? <p className="cycle-detail__empty">No document requirements are configured.</p> : <div className="cycle-detail__list">{detail.documents.map((document) => <div className="cycle-detail__list-item" key={document.id}><div><strong>{document.title}</strong><span>Due {dateText(document.due_at)}</span><small>{document.submissions.length} submission(s) · {document.submissions.reduce((total, item) => total + item.version_count, 0)} version(s)</small></div><em>{document.status}</em></div>)}</div>}</article>
    </div>
  </>;
}
