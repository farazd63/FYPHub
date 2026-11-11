import { useEffect, useState } from "react";

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

  return <section className="student-overview" aria-labelledby="student-overview-heading">
    <header className="student-overview__hero"><p className="student-overview__eyebrow">Student workspace</p><h1 id="student-overview-heading">Your FYP workspace</h1><p>Important updates for your group appear here.</p></header>
    {group && <section className="student-overview__summary" aria-label="Group project overview"><div><strong>{group.project?.title || group.group_name}</strong><span>project</span></div><div><strong>{group.supervisor?.name || "Pending"}</strong><span>supervisor</span></div><div><strong>{group.academic_cycle || "Not set"}</strong><span>academic cycle</span></div></section>}
    {state === "loading" && <p className="mt-6 text-sm text-slate-600">Loading notifications…</p>}
    {state === "error" && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Notifications could not be loaded.</p>}
    {state === "ready" && notifications.length > 0 && <section className="mt-6 rounded-2xl border border-[#dce4de] bg-white p-6" aria-labelledby="student-notifications-heading"><div className="flex items-center justify-between gap-3"><h2 id="student-notifications-heading" className="text-xl font-semibold">Notifications</h2><span className="text-sm text-slate-500">{notifications.length}</span></div><div className="mt-4 grid gap-3">{notifications.map((notification) => <article key={notification.id} className={`rounded-xl border p-4 ${notification.read_at ? "border-[#e3e8e5]" : "border-[#b9ddc8] bg-[#f4fbf6]"}`}><div className="flex flex-wrap items-start justify-between gap-3"><p className="font-semibold">{notificationText(notification)}</p>{!notification.read_at && <span className="rounded-full bg-[#176B66] px-2.5 py-1 text-xs font-semibold text-white">New</span>}</div><time className="mt-1 block text-xs text-slate-500">{new Date(notification.created_at).toLocaleString()}</time></article>)}</div></section>}
  </section>;
}

export function StudentOverviewWithDocuments(props: Props) {
  return <StudentOverview {...props} />;
}
