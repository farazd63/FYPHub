import { useCallback, useEffect, useState } from "react";
import { Archive, Pencil, Send, Trash2 } from "lucide-react";
import { AnnouncementComposer, type Announcement, type AnnouncementPermissions } from "./announcements/AnnouncementSection";
import { PageHeader } from "./ui";
import { IconButton } from "./ui/IconButton";
import { AdminAddButton } from "./ui/AdminAddButton";
import "./AdminAnnouncements.css";

type Props = { api: string };
type EditValues = { title: string; message: string; priority: string; target_type: string; target_role: string; cycle_id: string; group_id: string; project_id: string; published_at: string; expires_at: string };
const label = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
const localDate = (value: string | null) => value ? new Date(value).toISOString().slice(0, 16) : "";
const valuesFrom = (row: Announcement): EditValues => ({ title: row.title, message: row.message, priority: row.priority, target_type: row.target_type, target_role: row.target_role ?? "", cycle_id: row.cycle_id?.toString() ?? "", group_id: row.group_id?.toString() ?? "", project_id: row.project_id?.toString() ?? "", published_at: localDate(row.published_at), expires_at: localDate(row.expires_at) });

export function AdminAnnouncements({ api }: Props) {
  const [rows, setRows] = useState<Announcement[]>([]);
  const [permissions, setPermissions] = useState<AnnouncementPermissions | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState<EditValues | null>(null);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    try {
      const [listResponse, permissionResponse] = await Promise.all([fetch(`${api}/api/v1/announcements/admin?include_archived=true`, { credentials: "include" }), fetch(`${api}/api/v1/announcements/permissions`, { credentials: "include" })]);
      if (!listResponse.ok || !permissionResponse.ok) throw new Error();
      setRows(await listResponse.json() as Announcement[]);
      setPermissions(await permissionResponse.json() as AnnouncementPermissions);
    } catch { setError("Announcements could not be loaded."); }
  }, [api]);
  useEffect(() => { void load(); }, [load]);

  const action = async (id: number, method: string, suffix = "") => {
    setError("");
    const response = await fetch(`${api}/api/v1/announcements/${id}${suffix}`, { method, credentials: "include" });
    if (!response.ok) { setError("The announcement action could not be completed."); return; }
    await load();
  };

  const save = async (id: number) => {
    if (!form) return;
    const body: Record<string, unknown> = { title: form.title, message: form.message, priority: form.priority, target_type: form.target_type, target_role: form.target_role || null, cycle_id: form.cycle_id ? Number(form.cycle_id) : null, group_id: form.group_id ? Number(form.group_id) : null, project_id: form.project_id ? Number(form.project_id) : null, published_at: form.published_at ? new Date(form.published_at).toISOString() : null, expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null };
    const response = await fetch(`${api}/api/v1/announcements/${id}`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!response.ok) { setError("The announcement could not be saved. Check its target scope."); return; }
    setEditing(null); setForm(null); await load();
  };

  return <section className="admin-announcements">
    <PageHeader title="Announcements" actions={<AdminAddButton open={showCreate} label="announcement" onClick={() => setShowCreate((value) => !value)} />} />
    {showCreate && permissions && <AnnouncementComposer api={api} permissions={permissions} publishAfterCreate={false} onCreated={() => { setShowCreate(false); void load(); }} />}
    {error && <p className="admin-announcements__error" role="alert">{error}</p>}
    <div className="admin-announcements__list">
      {rows.map((row) => <article key={row.id} className="admin-announcements__item">
        <div className="admin-announcements__item-head">
          <div><span className={`announcement-priority announcement-priority--${row.priority.toLowerCase()}`}>{label(row.priority)}</span><h2>{row.title}</h2><p>{row.author_name} · {label(row.author_role)} · {label(row.status)}</p></div>
          <div className="admin-announcements__actions" aria-label={`Actions for ${row.title}`}>
            {row.status === "DRAFT" && <IconButton label="Publish announcement" size="sm" variant="primary" onClick={() => void action(row.id, "POST", "/publish")}><Send size={15} strokeWidth={1.8} aria-hidden /></IconButton>}
            {row.status === "PUBLISHED" && <IconButton label="Archive announcement" size="sm" variant="secondary" onClick={() => void action(row.id, "POST", "/archive")}><Archive size={15} strokeWidth={1.8} aria-hidden /></IconButton>}
            <IconButton label="Edit announcement" size="sm" variant="secondary" onClick={() => { setEditing(row.id); setForm(valuesFrom(row)); }}><Pencil size={15} strokeWidth={1.8} aria-hidden /></IconButton>
            <IconButton label="Delete announcement" size="sm" variant="danger" onClick={() => { if (window.confirm("Delete this announcement?")) void action(row.id, "DELETE"); }}><Trash2 size={15} strokeWidth={1.8} aria-hidden /></IconButton>
          </div>
        </div>
        <p className="admin-announcements__message">{row.message}</p>
        <p className="admin-announcements__target">Audience: {label(row.target_type)}{row.target_role ? ` · ${label(row.target_role)}` : ""}</p>
        {editing === row.id && form && <form className="admin-announcements__editor" onSubmit={(event) => { event.preventDefault(); void save(row.id); }}>
          <label>Title<input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
          <label>Priority<select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}><option value="NORMAL">Normal</option><option value="IMPORTANT">Important</option><option value="URGENT">Urgent</option></select></label>
          <label className="admin-announcements__wide">Message<textarea required rows={5} value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} /></label>
          <label>Audience<select value={form.target_type} onChange={(event) => setForm({ ...form, target_type: event.target.value })}>{permissions?.allowed_target_types.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
          {form.target_type === "ROLE" && <label>Target role<select value={form.target_role} onChange={(event) => setForm({ ...form, target_role: event.target.value })}>{permissions?.allowed_roles.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>}
          {form.target_type === "CYCLE" && <label>Academic cycle<select required value={form.cycle_id} onChange={(event) => setForm({ ...form, cycle_id: event.target.value })}><option value="">Select academic cycle</option>{permissions?.cycles.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
          {form.target_type === "GROUP" && <label>Group<select required value={form.group_id} onChange={(event) => setForm({ ...form, group_id: event.target.value })}><option value="">Select group</option>{permissions?.groups.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
          {form.target_type === "PROJECT" && <label>Project<select required value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })}><option value="">Select project</option>{permissions?.projects.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
          <label>Publish at<input type="datetime-local" value={form.published_at} onChange={(event) => setForm({ ...form, published_at: event.target.value })} /></label>
          <label>Expiry<input type="datetime-local" value={form.expires_at} onChange={(event) => setForm({ ...form, expires_at: event.target.value })} /></label>
          <div className="admin-announcements__editor-actions"><button type="submit">Save changes</button><button type="button" onClick={() => { setEditing(null); setForm(null); }}>Cancel</button></div>
        </form>}
      </article>)}
    </div>
    {!rows.length && <p className="admin-announcements__empty">No announcements have been created yet.</p>}
  </section>;
}
