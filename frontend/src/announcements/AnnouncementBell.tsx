import { Bell, Check, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Announcement } from "./AnnouncementSection";
import "./announcement-bell.css";
import { appPathname } from "../platform-path";

type Props = { api: string; role?: string };
type Source = "announcement" | "notification" | "collaboration" | "document";
type HeaderNotification = {
  id: string;
  source: Source;
  title: string;
  message: string;
  createdAt: string;
  unread: boolean;
  priority: "normal" | "important" | "urgent" | "info";
  announcementId?: number;
  notificationId?: number;
  channelId?: number;
  messageId?: number;
  href?: string;
  author_name?: string;
  author_role?: string;
};
type AppNotification = { id: number; kind: string; payload?: Record<string, unknown> | null; read_at?: string | null; created_at: string };
type CollaborationChannel = { id: number; group_id: number; group_name: string; unread_count: number };
type CollaborationMessage = { id: number; sender_name: string; message_text: string; attachment_reference?: string | null; created_at: string };
type Requirement = { id: number; title: string; due_at: string; is_required?: boolean; created_at: string };
type Submission = { status: string; review_comment?: string | null; updated_at?: string };

const priorityLabel = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
const kindLabel = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
const dateLabel = (value?: string | null) => value ? new Date(value).toLocaleString() : "Not recorded";
const mostRecentUnreadId = (rows: HeaderNotification[]) => rows.filter((row) => row.unread).sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())[0]?.id ?? null;
const roleFromPath = () => appPathname().startsWith("/student") ? "STUDENT" : appPathname().startsWith("/supervisor") ? "SUPERVISOR" : "";

async function readJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new Error("Notifications could not be loaded.");
  return response.json() as Promise<T>;
}

function resultValue<T>(result: PromiseSettledResult<unknown>, fallback: T): T {
  return result.status === "fulfilled" ? result.value as T : fallback;
}

function notificationPath(row: AppNotification): string | undefined {
  const payload = row.payload ?? {};
  const payloadPath = typeof payload.path === "string" && payload.path.startsWith("/") ? payload.path : undefined;
  if (row.kind === "COLLABORATION_PASSWORD_RESET_REQUESTED") {
    const cycleId = Number(payload.cycle_id);
    const groupId = Number(payload.group_id);
    const memberId = Number(payload.member_id);
    if (Number.isInteger(cycleId) && cycleId > 0 && Number.isInteger(groupId) && groupId > 0) {
      const params = new URLSearchParams({ cycle_id: String(cycleId), group_id: String(groupId), focus: "collaboration-reset" });
      if (Number.isInteger(memberId) && memberId > 0) params.set("member_id", String(memberId));
      return `/admin/student-groups?${params.toString()}`;
    }
  }
  return payloadPath;
}

function appNotification(row: AppNotification): HeaderNotification {
  const payload = row.payload ?? {};
  const payloadTitle = typeof payload.title === "string" ? payload.title : "";
  const payloadMessage = typeof payload.message === "string" ? payload.message : "";
  return {
    id: `notification:${row.id}`,
    source: "notification",
    title: payloadTitle || kindLabel(row.kind),
    message: payloadMessage || kindLabel(row.kind),
    createdAt: row.created_at,
    unread: !row.read_at,
    priority: "normal",
    notificationId: row.id,
    href: notificationPath(row),
  };
}

export function AnnouncementBell({ api, role }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const loadedAllRef = useRef(false);
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<HeaderNotification[]>([]);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const highlightInitialized = useRef(false);
  const [loadedAll, setLoadedAll] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [readOverrides, setReadOverrides] = useState<Record<string, boolean>>({});

  const load = useCallback(async (all: boolean) => {
    setLoading(true);
    setError("");
    try {
      const normalizedRole = role?.trim().toUpperCase() || roleFromPath();
      const collaborationRole = normalizedRole === "STUDENT" || normalizedRole === "SUPERVISOR" ? normalizedRole.toLowerCase() : null;
      const results = await Promise.allSettled([
        readJson<Announcement[]>(`${api}${all ? "/api/v1/announcements?limit=100" : "/api/v1/announcements/latest?limit=10"}`),
        readJson<AppNotification[]>(`${api}/api/v1/notifications`),
        collaborationRole ? readJson<CollaborationChannel[]>(`${api}/api/v1/${collaborationRole}/collaboration/channels`) : Promise.resolve([] as CollaborationChannel[]),
        normalizedRole === "STUDENT" ? readJson<Requirement[]>(`${api}/api/v1/student/document-requirements`) : Promise.resolve([] as Requirement[]),
      ]);
      const announcements = resultValue(results[0], [] as Announcement[]);
      const appNotifications = resultValue(results[1], [] as AppNotification[]);
      const channels = resultValue(results[2], [] as CollaborationChannel[]);
      const requirements = resultValue(results[3], [] as Requirement[]);
      const collaborationChannels = channels.filter((channel) => channel.unread_count > 0).slice(0, 20);
      const collaborationMessages = await Promise.allSettled(collaborationChannels.map((channel) => readJson<CollaborationMessage[]>(`${api}/api/v1/${collaborationRole}/collaboration/channels/${channel.id}/messages?limit=1`)));
      const collaborationRows: HeaderNotification[] = collaborationMessages.flatMap((result, index) => {
        const message = resultValue(result, [] as CollaborationMessage[]).at(-1);
        const channel = collaborationChannels[index];
        if (!message || !channel || !collaborationRole) return [];
        return [{
          id: `collaboration:${channel.id}:${message.id}`,
          source: "collaboration",
          title: `Collaboration · ${channel.group_name}`,
          message: `${message.sender_name}: ${message.message_text || (message.attachment_reference ? "Shared an attachment." : "New message.")}`,
          createdAt: message.created_at,
          unread: true,
          priority: "info",
          channelId: channel.id,
          messageId: message.id,
            href: normalizedRole === "STUDENT" ? "/student/collaboration" : `/supervisor/groups/${channel.group_id}?tab=discussion`,
        }];
      });
      const requiredRequirements = requirements.filter((requirement) => requirement.is_required !== false);
      const submissionResults = await Promise.allSettled(requiredRequirements.map((requirement) => readJson<Submission>(`${api}/api/v1/document-requirements/${requirement.id}/submission`)));
      const requiredDocumentRows: HeaderNotification[] = requiredRequirements.flatMap((requirement, index) => {
        const submission = resultValue(submissionResults[index], null as Submission | null);
        const due = new Date(requirement.due_at).getTime();
        if (!submission) {
          const overdue = Number.isFinite(due) && due < Date.now();
          return [{
            id: `document:${requirement.id}`,
            source: "document" as const,
            title: "Required document",
            message: `${requirement.title} is ${overdue ? "overdue" : "due"} ${dateLabel(requirement.due_at)}.`,
            createdAt: requirement.created_at,
            unread: true,
            priority: overdue ? "urgent" as const : "important" as const,
            href: `/student/documents?requirement_id=${requirement.id}&focus=requirement`,
          }];
        }
        if (["CHANGES_REQUESTED", "RESUBMISSION_REQUIRED"].includes(submission.status)) {
          return [{
            id: `document:${requirement.id}:${submission.status}`,
            source: "document" as const,
            title: "Required document update",
            message: `${requirement.title} needs changes before it can be accepted.${submission.review_comment ? ` ${submission.review_comment}` : ""}`,
            createdAt: submission.updated_at || requirement.created_at,
            unread: true,
            priority: "urgent" as const,
            href: `/student/documents?requirement_id=${requirement.id}&focus=requirement`,
          }];
        }
        return [];
      });
      const announcementRows: HeaderNotification[] = announcements.map((row) => ({
        id: `announcement:${row.id}`,
        source: "announcement",
        title: row.title,
        message: row.message,
        createdAt: row.published_at ?? row.created_at,
        unread: !row.is_read,
        priority: row.priority.toLowerCase() === "urgent" ? "urgent" : row.priority.toLowerCase() === "important" ? "important" : "normal",
        announcementId: row.id,
        author_name: row.author_name,
        author_role: row.author_role,
      }));
      const nextRows = [...announcementRows, ...appNotifications.map(appNotification), ...collaborationRows, ...requiredDocumentRows]
        .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime());
      setRows(nextRows);
      setHighlightedId((current) => {
        if (highlightInitialized.current) return current;
        highlightInitialized.current = true;
        return mostRecentUnreadId(nextRows);
      });
      loadedAllRef.current = all;
      setLoadedAll(all);
      if (results.every((result) => result.status === "rejected") && !nextRows.length) setError("Notifications could not be loaded.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Notifications could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [api, role]);

  useEffect(() => {
    const initial = window.setTimeout(() => void load(false), 0);
    const timer = window.setInterval(() => void load(loadedAllRef.current), 30000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, [load]);

  useEffect(() => {
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", closeOnEscape); };
  }, []);

  const displayRows = rows.map((row) => ({ ...row, unread: row.unread && !readOverrides[row.id] }));
  const unread = displayRows.filter((row) => row.unread).length;
  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !loadedAll) void load(true);
  };

  const persistRead = useCallback(async (row: HeaderNotification) => {
    if (row.source === "announcement" && row.announcementId) {
      await fetch(`${api}/api/v1/announcements/${row.announcementId}/read`, { method: "POST", credentials: "include" });
    }
    if (row.source === "notification" && row.notificationId) {
      await fetch(`${api}/api/v1/notifications/${row.notificationId}/read`, { method: "POST", credentials: "include" });
    }
    if (row.source === "collaboration" && row.channelId && row.messageId) {
      const collaborationRole = (role?.trim().toUpperCase() || roleFromPath()) === "SUPERVISOR" ? "supervisor" : "student";
      await fetch(`${api}/api/v1/${collaborationRole}/collaboration/channels/${row.channelId}/read`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message_id: row.messageId }) });
    }
  }, [api, role]);

  const markRead = async (row: HeaderNotification) => {
    setReadOverrides((current) => ({ ...current, [row.id]: true }));
    setRows((current) => current.map((item) => item.id === row.id ? { ...item, unread: false } : item));
    setHighlightedId((current) => current === row.id ? null : current);
    try {
      await persistRead(row);
    } catch { /* The item remains locally dismissed until the next refresh. */ }
    if (row.href) window.location.assign(row.href);
  };

  const markVisibleRead = useCallback(async (visibleRows: HeaderNotification[]) => {
    if (!visibleRows.length) return;
    const visibleIds = new Set(visibleRows.map((row) => row.id));
    setReadOverrides((current) => ({ ...current, ...Object.fromEntries(visibleRows.map((row) => [row.id, true])) }));
    setRows((current) => current.map((row) => visibleIds.has(row.id) ? { ...row, unread: false } : row));
    setHighlightedId((current) => current && visibleIds.has(current) ? null : current);
    await Promise.allSettled(visibleRows.map((row) => persistRead(row)));
  }, [persistRead]);

  useEffect(() => {
    if (!open || loading) return;
    const visibleUnreadRows = displayRows.filter((row) => row.unread);
    if (!visibleUnreadRows.length) return;
    const timer = window.setTimeout(() => void markVisibleRead(visibleUnreadRows), 0);
    return () => window.clearTimeout(timer);
  }, [displayRows, loading, markVisibleRead, open]);

  return <div className="announcement-bell" ref={rootRef}>
    <button type="button" className="announcement-bell__button" aria-label={unread ? `${unread} unread notifications` : "Notifications"} aria-expanded={open} aria-haspopup="dialog" onClick={toggle}>
      <Bell size={17} strokeWidth={1.8} aria-hidden="true" />
      {unread > 0 && <span className="announcement-bell__badge" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <div className="announcement-bell__popover" role="dialog" aria-label="Notifications">
      <div className="announcement-bell__header"><div><strong>Notifications</strong><span>{unread ? `${unread} unread` : "All caught up"}</span></div><button type="button" className="announcement-bell__close" aria-label="Close notifications" onClick={() => setOpen(false)}><X size={16} aria-hidden="true" /></button></div>
      {loading && <p className="announcement-bell__state">Loading notifications…</p>}
      {!loading && error && <p className="announcement-bell__state announcement-bell__state--error">{error}</p>}
      {!loading && !error && !displayRows.length && <p className="announcement-bell__state">No new notifications.</p>}
      {!loading && !error && displayRows.length > 0 && <div className="announcement-bell__list">{displayRows.map((row) => <button type="button" key={row.id} className={`announcement-bell__item ${highlightedId === row.id && row.unread ? "announcement-bell__item--unread" : ""}`} onClick={() => void markRead(row)}><span className={`announcement-priority announcement-priority--${row.priority}`}>{row.source === "announcement" ? priorityLabel(row.priority) : row.source === "collaboration" ? "Collaboration" : row.source === "document" ? "Required document" : "Update"}</span><strong>{row.title}</strong><span>{row.message}</span><small>{dateLabel(row.createdAt)}{row.unread && <><Check size={12} aria-hidden="true" /> New</>}</small></button>)}</div>}
      {loadedAll && displayRows.length > 0 && <p className="announcement-bell__footer">Showing announcements, updates, collaboration messages, and required-document alerts.</p>}
    </div>}
  </div>;
}
