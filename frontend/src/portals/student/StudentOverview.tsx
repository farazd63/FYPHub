import { useEffect, useState, type FormEvent } from "react";
import { PageHeader, StatCard } from "../../ui";
import { AnnouncementSection } from "../../announcements/AnnouncementSection";

type Notification = {
  id: number;
  kind: string;
  payload?: Record<string, unknown> | null;
  read_at?: string | null;
  created_at: string;
};

type Props = { api: string };
type Group = { group_name: string; group_email: string | null; academic_cycle: string | null; status: string; final_project_title?: string | null; project?: { title: string | null; status: string; updated_at: string } | null; supervisor?: { name: string } | null };

const notificationText = (notification: Notification) => {
  const payload = notification.payload;
  const message = payload && typeof payload.message === "string" ? payload.message : null;
  return message || notification.kind.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
};

export function StudentOverview({ api }: Props) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [group, setGroup] = useState<Group | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [titleMessage, setTitleMessage] = useState("");
  const [savingTitle, setSavingTitle] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(`${api}/api/v1/notifications`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error();
        const body = await response.json() as unknown;
        if (!controller.signal.aborted) {
          setNotifications(Array.isArray(body) ? body as Notification[] : []);
          setState("ready");
        }
      } catch {
        if (!controller.signal.aborted) setState("error");
      }
    })();
    return () => controller.abort();
  }, [api]);

  useEffect(() => { const controller = new AbortController(); void fetch(`${api}/api/v1/student/group/me`, { credentials: "include", signal: controller.signal }).then((response) => response.ok ? response.json() as Promise<Group> : Promise.reject(new Error())).then((value) => { if (!controller.signal.aborted) setGroup(value); }).catch(() => undefined); return () => controller.abort(); }, [api]);

  const finalTitle = group?.final_project_title?.trim() || "";
  const saveFinalTitle = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = titleDraft.trim().replace(/\s+/g, " ");
    if (!value) { setTitleMessage("Enter the final project title before saving."); return; }
    setSavingTitle(true);
    setTitleMessage("");
    try {
      const response = await fetch(`${api}/api/v1/student/group/final-title`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ final_project_title: value }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "The final project title could not be saved.");
      setGroup(body as Group);
      setTitleDraft(value);
      setEditingTitle(false);
      setTitleMessage("Final project title saved.");
    } catch (error) {
      setTitleMessage(error instanceof Error ? error.message : "The final project title could not be saved.");
    } finally { setSavingTitle(false); }
  };

  return <section className="student-overview min-w-0" aria-labelledby="student-overview-heading">
    <PageHeader className="student-overview__hero" title="Your FYP workspace" />
    <AnnouncementSection api={api} />
    {group && <>
      <section className="student-overview__context mt-6 grid min-w-0 gap-3 sm:grid-cols-3" aria-label="Group project overview"><StatCard label="Final project title" value={<span className="student-stat-value-clamp" title={finalTitle || "Not finalized yet"}>{finalTitle || "Not finalized yet"}</span>} /><StatCard label="Supervisor" value={group.supervisor?.name || "Pending"} /><StatCard label="Academic cycle" value={group.academic_cycle || "Not set"} /></section>
      <section className="mt-4 rounded-2xl border border-fy-border bg-fy-surface p-5" aria-labelledby="final-project-title-heading">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-fy-text-secondary">Confirmed project identity</p><h2 id="final-project-title-heading" className="mt-1 text-lg font-semibold">Final project title</h2><p className="mt-1 max-w-2xl text-sm text-fy-text-secondary">Set the title your group has finalized. The submitted proposal title is kept separately and will never overwrite this field.</p></div>
          {!editingTitle && <button type="button" className="fy-button fy-button--secondary" onClick={() => { setTitleDraft(finalTitle); setTitleMessage(""); setEditingTitle(true); }}>{finalTitle ? "Edit title" : "Set final title"}</button>}
        </div>
        {titleMessage && <p role="status" className="mt-4 rounded-lg border border-fy-border bg-fy-surface-muted p-3 text-sm text-fy-text-secondary">{titleMessage}</p>}
        {editingTitle && <form className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={(event) => void saveFinalTitle(event)}><label className="min-w-0 flex-1"><span className="mb-1 block text-sm font-semibold">Final project title</span><input autoFocus maxLength={255} value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} className="fy-input w-full" placeholder="Enter the finalized project title" /></label><div className="flex gap-2"><button type="button" className="fy-button fy-button--secondary" onClick={() => { setEditingTitle(false); setTitleMessage(""); }}>Cancel</button><button type="submit" className="fy-button fy-button--primary" disabled={savingTitle}>{savingTitle ? "Saving…" : "Save title"}</button></div></form>}
      </section>
    </>}
    {state === "loading" && <p className="mt-6 text-sm text-fy-text-secondary">Loading notifications…</p>}
    {state === "error" && <p role="alert" className="mt-6 rounded-xl border border-fy-danger bg-fy-danger-soft p-4 text-sm text-fy-danger">Notifications could not be loaded.</p>}
    {state === "ready" && notifications.length > 0 && <section className="mt-6 rounded-2xl border border-fy-border bg-fy-surface p-6" aria-labelledby="student-notifications-heading"><div className="flex items-center justify-between gap-3"><h2 id="student-notifications-heading" className="text-xl font-semibold">Notifications</h2><span className="text-sm text-fy-text-secondary">{notifications.length}</span></div><div className="mt-4 grid gap-3">{notifications.map((notification) => <article key={notification.id} className={`rounded-xl border border-fy-border p-4 ${notification.read_at ? "bg-fy-surface" : "bg-fy-success-soft"}`}><div className="flex flex-wrap items-start justify-between gap-3"><p className="font-semibold">{notificationText(notification)}</p>{!notification.read_at && <span className="fy-status-badge fy-status-badge--brand">New</span>}</div><time className="mt-1 block text-xs text-fy-text-secondary">{new Date(notification.created_at).toLocaleString()}</time></article>)}</div></section>}
  </section>;
}

export function StudentOverviewWithDocuments(props: Props) {
  return <StudentOverview {...props} />;
}
