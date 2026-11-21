import { useCallback, useEffect, useMemo, useState } from "react";
import "./announcements.css";

export type Announcement = {
  id: number;
  title: string;
  message: string;
  author_id: number;
  author_name: string;
  author_role: string;
  priority: "NORMAL" | "IMPORTANT" | "URGENT" | string;
  status: string;
  target_type: string;
  target_role: string | null;
  cycle_id: number | null;
  group_id: number | null;
  project_id: number | null;
  published_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  read_at: string | null;
  is_read: boolean;
  can_edit: boolean;
  can_archive: boolean;
};

export type AnnouncementPermissions = {
  can_create: boolean;
  can_manage: boolean;
  allowed_target_types: string[];
  allowed_roles: string[];
  cycles: AnnouncementScopeOption[];
  groups: AnnouncementScopeOption[];
  projects: AnnouncementScopeOption[];
};

export type AnnouncementScopeOption = { id: number; label: string; cycle_id: number | null; group_id: number | null; project_id: number | null };

type Props = { api: string; onManage?: () => void; showComposer?: boolean; limit?: number };

const roleLabel = (role: string) => role.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
const targetLabel = (row: Announcement) => {
  if (row.target_type === "ROLE") return row.target_role ? roleLabel(row.target_role) : "Selected role";
  if (row.target_type === "ALL_USERS") return "Everyone";
  if (row.target_type === "ALL_GROUPS") return "All student groups";
  if (row.target_type === "ASSIGNED_STUDENTS") return "Assigned students";
  if (row.target_type === "ASSIGNED_PANEL") return "Assigned panel members";
  if (row.target_type === "CYCLE") return `Academic cycle${row.cycle_id ? ` #${row.cycle_id}` : ""}`;
  if (row.target_type === "GROUP") return `Group${row.group_id ? ` #${row.group_id}` : ""}`;
  if (row.target_type === "PROJECT") return `Project${row.project_id ? ` #${row.project_id}` : ""}`;
  return roleLabel(row.target_type);
};

const dateLabel = (value: string | null) => value ? new Date(value).toLocaleString() : "Not published";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error("Request failed");
  return response.json() as Promise<T>;
}

export function AnnouncementSection({ api, onManage, showComposer = true, limit = 1 }: Props) {
  const [rows, setRows] = useState<Announcement[]>([]);
  const [permissions, setPermissions] = useState<AnnouncementPermissions | null>(null);
  const [selected, setSelected] = useState<Announcement | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [expandedComposer, setExpandedComposer] = useState(false);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [announcementResponse, permissionResponse] = await Promise.all([
        fetch(`${api}/api/v1/announcements/latest?limit=${Math.max(1, limit)}`, { credentials: "include" }),
        fetch(`${api}/api/v1/announcements/permissions`, { credentials: "include" }),
      ]);
      const [announcementRows, permissionData] = await Promise.all([
        readJson<Announcement[]>(announcementResponse),
        readJson<AnnouncementPermissions>(permissionResponse),
      ]);
      setRows(Array.isArray(announcementRows) ? announcementRows : []);
      setPermissions(permissionData);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [api, limit]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  const open = async (row: Announcement) => {
    setSelected(row);
    if (!row.is_read) {
      try {
        await fetch(`${api}/api/v1/announcements/${row.id}/read`, { method: "POST", credentials: "include" });
        setRows((current) => current.map((item) => item.id === row.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item));
        setSelected((current) => current && current.id === row.id ? { ...current, is_read: true, read_at: new Date().toISOString() } : current);
      } catch {
        /* A read marker is helpful but must not prevent reading the announcement. */
      }
    }
  };

  const toggleAll = async () => {
    if (showAll) { setShowAll(false); return; }
    try {
      const all = await readJson<Announcement[]>(await fetch(`${api}/api/v1/announcements?limit=100`, { credentials: "include" }));
      setRows(Array.isArray(all) ? all : []);
      setShowAll(true);
    } catch { setState("error"); }
  };

  return <section className="announcement-section" aria-labelledby="announcements-heading">
    <div className="announcement-section__heading">
      <div><p className="announcement-section__eyebrow">Central updates</p><h2 id="announcements-heading">Announcements</h2><p>Important updates from your FYPHub team, shown only to the people they concern.</p></div>
      <div className="announcement-section__actions">
        {permissions?.can_manage && onManage && <button type="button" className="announcement-button announcement-button--secondary" onClick={onManage}>Manage announcements</button>}
        {permissions?.can_create && !permissions.can_manage && showComposer && <button type="button" className="announcement-button announcement-button--secondary" onClick={() => setExpandedComposer((value) => !value)}>{expandedComposer ? "Close composer" : "Create announcement"}</button>}
        <button type="button" className="announcement-button announcement-button--secondary" onClick={() => void toggleAll()}>{showAll ? "Show latest" : "View all"}</button>
      </div>
    </div>
    {expandedComposer && permissions?.can_create && <AnnouncementComposer api={api} permissions={permissions} onCreated={() => { setExpandedComposer(false); void load(); }} />}
    {state === "loading" && <p className="announcement-section__message">Loading announcements…</p>}
    {state === "error" && <div className="announcement-section__error" role="alert">Announcements could not be loaded. <button type="button" onClick={() => void load()}>Retry</button></div>}
    {state === "ready" && !rows.length && <div className="announcement-section__empty"><strong>No announcements yet.</strong><span>New updates for this dashboard will appear here.</span></div>}
    {state === "ready" && rows.length > 0 && <div className="announcement-list">{rows.map((row) => <article key={row.id} className={`announcement-card ${row.is_read ? "" : "announcement-card--unread"}`}>
      <div className="announcement-card__top"><span className={`announcement-priority announcement-priority--${row.priority.toLowerCase()}`}>{roleLabel(row.priority)}</span>{!row.is_read && <span className="announcement-unread">Unread</span>}</div>
      <h3>{row.title}</h3><p className="announcement-card__preview">{row.message}</p>
      <div className="announcement-card__meta"><span>{row.author_name} · {roleLabel(row.author_role)}</span><time dateTime={row.published_at ?? row.created_at}>{dateLabel(row.published_at ?? row.created_at)}</time><span>{targetLabel(row)}</span></div>
      <button type="button" className="announcement-link" onClick={() => void open(row)}>View details <span aria-hidden="true">→</span></button>
    </article>)}</div>}
    {selected && <div className="announcement-detail" role="dialog" aria-modal="true" aria-labelledby="announcement-detail-title"><div className="announcement-detail__header"><div><span className={`announcement-priority announcement-priority--${selected.priority.toLowerCase()}`}>{roleLabel(selected.priority)}</span><h3 id="announcement-detail-title">{selected.title}</h3></div><button type="button" className="announcement-detail__close" aria-label="Close announcement details" onClick={() => setSelected(null)}>×</button></div><p className="announcement-detail__message">{selected.message}</p><dl><div><dt>Published by</dt><dd>{selected.author_name} · {roleLabel(selected.author_role)}</dd></div><div><dt>Published</dt><dd>{dateLabel(selected.published_at ?? selected.created_at)}</dd></div><div><dt>Audience</dt><dd>{targetLabel(selected)}</dd></div></dl></div>}
  </section>;
}

type ComposerProps = { api: string; permissions: AnnouncementPermissions; onCreated: () => void; publishAfterCreate?: boolean };
export function AnnouncementComposer({ api, permissions, onCreated, publishAfterCreate = true }: ComposerProps) {
  const defaultType = permissions.allowed_target_types[0] ?? "ROLE";
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const [targetType, setTargetType] = useState(defaultType);
  const [targetRole, setTargetRole] = useState(permissions.allowed_roles[0] ?? "");
  const [scopeId, setScopeId] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [error, setError] = useState("");
  const needsScope = useMemo(() => ["CYCLE", "GROUP", "PROJECT"].includes(targetType) || (permissions.can_manage && ["ASSIGNED_STUDENTS", "ASSIGNED_PANEL"].includes(targetType)), [permissions.can_manage, targetType]);
  const scopeOptions = targetType === "CYCLE" ? permissions.cycles : targetType === "PROJECT" ? permissions.projects : permissions.groups;
  const scopeLabel = targetType === "CYCLE" ? "Academic cycle" : targetType === "PROJECT" ? "Project" : "Group";
  const affectedPortals = targetType === "ALL_USERS" ? "Admin, Coordinator, Supervisor, Panel Member, and Student" : targetType === "ALL_GROUPS" ? "All Student group portals" : targetType === "ROLE" ? `All ${roleLabel(targetRole)} portals` : targetType === "ASSIGNED_STUDENTS" ? "Assigned Student portals" : targetType === "ASSIGNED_PANEL" ? "Assigned Panel Member portals" : "Matching Coordinator, Supervisor, Panel Member, and Student portals";

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError("");
    const body: Record<string, unknown> = { title, message, priority, target_type: targetType };
    if (targetType === "ROLE" && targetRole) body.target_role = targetRole;
    if (targetType === "CYCLE") body.cycle_id = Number(scopeId);
    if (targetType === "GROUP" || targetType === "ASSIGNED_STUDENTS" || targetType === "ASSIGNED_PANEL") body.group_id = scopeId ? Number(scopeId) : undefined;
    if (targetType === "PROJECT") body.project_id = Number(scopeId);
    if (expiresAt) body.expires_at = new Date(expiresAt).toISOString();
    try {
      const created = await readJson<Announcement>(await fetch(`${api}/api/v1/announcements`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }));
      if (publishAfterCreate) {
        const published = await fetch(`${api}/api/v1/announcements/${created.id}/publish`, { method: "POST", credentials: "include" });
        if (!published.ok) throw new Error();
      }
      setTitle(""); setMessage(""); setScopeId(""); setExpiresAt(""); onCreated();
    } catch { setError("The announcement could not be published. Check the audience and try again."); }
  };

  return <form className="announcement-composer" onSubmit={submit} aria-label="Create announcement"><div className="announcement-composer__heading"><div><h3>Create announcement</h3><p>Only authorized audiences are available for this account.</p></div></div><div className="announcement-form-grid"><label>Title<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label><label>Priority<select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="NORMAL">Normal</option><option value="IMPORTANT">Important</option><option value="URGENT">Urgent</option></select></label><label className="announcement-form-grid__wide">Message<textarea required rows={4} value={message} onChange={(event) => setMessage(event.target.value)} /></label><label>Audience<select value={targetType} onChange={(event) => { setTargetType(event.target.value); setScopeId(""); }}>{permissions.allowed_target_types.map((item) => <option key={item} value={item}>{roleLabel(item)}</option>)}</select></label>{targetType === "ROLE" && <label>Target role<select required value={targetRole} onChange={(event) => setTargetRole(event.target.value)}>{permissions.allowed_roles.map((item) => <option key={item} value={item}>{roleLabel(item)}</option>)}</select></label>}{needsScope && <label>{scopeLabel}{!permissions.can_manage && ["ASSIGNED_STUDENTS", "ASSIGNED_PANEL"].includes(targetType) ? " (optional)" : ""}<select required={permissions.can_manage || !["ASSIGNED_STUDENTS", "ASSIGNED_PANEL"].includes(targetType)} value={scopeId} onChange={(event) => setScopeId(event.target.value)}><option value="">{["ASSIGNED_STUDENTS", "ASSIGNED_PANEL"].includes(targetType) ? "All assigned groups" : `Select ${scopeLabel.toLowerCase()}`}</option>{scopeOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>{!scopeOptions.length && <small className="announcement-form-hint">No assigned {scopeLabel.toLowerCase()}s are available.</small>}</label>}<label>Expiry (optional)<input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} /></label></div><p className="announcement-audience-preview"><strong>Affected portals preview:</strong> {affectedPortals}</p>{error && <p className="announcement-form-error" role="alert">{error}</p>}<button type="submit" className="announcement-button announcement-button--primary">{publishAfterCreate ? "Publish announcement" : "Save draft"}</button></form>;
}
