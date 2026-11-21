import { useEffect, useState } from "react";
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
type Group = { group_name: string; group_email: string | null; academic_cycle: string | null; status: string; project?: { title: string; status: string; updated_at: string } | null; supervisor?: { name: string } | null };

const notificationText = (notification: Notification) => {
  const payload = notification.payload;
  const message = payload && typeof payload.message === "string" ? payload.message : null;
  return message || notification.kind.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
};

export function StudentOverview({ api }: Props) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [group, setGroup] = useState<Group | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

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

  return <section className="student-overview min-w-0" aria-labelledby="student-overview-heading">
    <PageHeader className="student-overview__hero" eyebrow="Student workspace" title="Your FYP workspace" description="Important updates for your group appear here." />
    <AnnouncementSection api={api} />
    {group && <section className="student-overview__context mt-6 grid min-w-0 gap-3 sm:grid-cols-3" aria-label="Group project overview"><StatCard label="Project" value={<span className="student-stat-value-clamp" title={group.project?.title || group.group_name}>{group.project?.title || group.group_name}</span>} /><StatCard label="Supervisor" value={group.supervisor?.name || "Pending"} /><StatCard label="Academic cycle" value={group.academic_cycle || "Not set"} /></section>}
    {state === "loading" && <p className="mt-6 text-sm text-fy-text-secondary">Loading notifications…</p>}
    {state === "error" && <p role="alert" className="mt-6 rounded-xl border border-fy-danger bg-fy-danger-soft p-4 text-sm text-fy-danger">Notifications could not be loaded.</p>}
    {state === "ready" && notifications.length > 0 && <section className="mt-6 rounded-2xl border border-fy-border bg-fy-surface p-6" aria-labelledby="student-notifications-heading"><div className="flex items-center justify-between gap-3"><h2 id="student-notifications-heading" className="text-xl font-semibold">Notifications</h2><span className="text-sm text-fy-text-secondary">{notifications.length}</span></div><div className="mt-4 grid gap-3">{notifications.map((notification) => <article key={notification.id} className={`rounded-xl border border-fy-border p-4 ${notification.read_at ? "bg-fy-surface" : "bg-fy-success-soft"}`}><div className="flex flex-wrap items-start justify-between gap-3"><p className="font-semibold">{notificationText(notification)}</p>{!notification.read_at && <span className="fy-status-badge fy-status-badge--brand">New</span>}</div><time className="mt-1 block text-xs text-fy-text-secondary">{new Date(notification.created_at).toLocaleString()}</time></article>)}</div></section>}
  </section>;
}

export function StudentOverviewWithDocuments(props: Props) {
  return <StudentOverview {...props} />;
}
