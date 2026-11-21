import { Bell, Check, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Announcement } from "./AnnouncementSection";
import "./announcement-bell.css";

type Props = { api: string };

const priorityLabel = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
const dateLabel = (value: string | null) => value ? new Date(value).toLocaleString() : "Not published";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error("Announcements could not be loaded.");
  return response.json() as Promise<T>;
}

export function AnnouncementBell({ api }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Announcement[]>([]);
  const [loadedAll, setLoadedAll] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (all: boolean) => {
    setLoading(true);
    setError("");
    try {
      const endpoint = all ? "/api/v1/announcements?limit=100" : "/api/v1/announcements/latest?limit=100";
      const data = await readJson<Announcement[]>(await fetch(`${api}${endpoint}`, { credentials: "include" }));
      setRows(Array.isArray(data) ? data : []);
      setLoadedAll(all);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Announcements could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { void load(false); }, [load]);

  useEffect(() => {
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", closeOnEscape); };
  }, []);

  const unread = rows.filter((row) => !row.is_read).length;
  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !loadedAll) void load(true);
  };

  const markRead = async (row: Announcement) => {
    if (row.is_read) return;
    setRows((current) => current.map((item) => item.id === row.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item));
    try { await fetch(`${api}/api/v1/announcements/${row.id}/read`, { method: "POST", credentials: "include" }); } catch { /* Reading remains available if the marker request fails. */ }
  };

  return <div className="announcement-bell" ref={rootRef}>
    <button type="button" className="announcement-bell__button" aria-label={unread ? `${unread} unread announcements` : "Announcements"} aria-expanded={open} aria-haspopup="dialog" onClick={toggle}>
      <Bell size={17} strokeWidth={1.8} aria-hidden="true" />
      {unread > 0 && <span className="announcement-bell__badge" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <div className="announcement-bell__popover" role="dialog" aria-label="Announcements">
      <div className="announcement-bell__header"><div><strong>Announcements</strong><span>{unread ? `${unread} unread` : "All caught up"}</span></div><button type="button" className="announcement-bell__close" aria-label="Close announcements" onClick={() => setOpen(false)}><X size={16} aria-hidden="true" /></button></div>
      {loading && <p className="announcement-bell__state">Loading announcements…</p>}
      {!loading && error && <p className="announcement-bell__state announcement-bell__state--error">{error}</p>}
      {!loading && !error && !rows.length && <p className="announcement-bell__state">No announcements yet.</p>}
      {!loading && !error && rows.length > 0 && <div className="announcement-bell__list">{rows.map((row) => <button type="button" key={row.id} className={`announcement-bell__item ${row.is_read ? "" : "announcement-bell__item--unread"}`} onClick={() => void markRead(row)}><span className={`announcement-priority announcement-priority--${row.priority.toLowerCase()}`}>{priorityLabel(row.priority)}</span><strong>{row.title}</strong><span>{row.message}</span><small>{dateLabel(row.published_at ?? row.created_at)}{!row.is_read && <><Check size={12} aria-hidden="true" /> New</>}</small></button>)}</div>}
      {loadedAll && rows.length > 0 && <p className="announcement-bell__footer">Showing your latest accessible announcement history.</p>}
    </div>}
  </div>;
}
