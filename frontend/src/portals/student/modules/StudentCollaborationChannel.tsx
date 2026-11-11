import { useCallback, useEffect, useRef, useState } from "react";
import { COLLABORATION_MESSAGE_LIMIT, mergeCollaborationMessages, sendsOnEnter, validateCollaborationMessage } from "./collaboration-message";
import "./student-collaboration.css";

type Member = { id: number; name?: string; full_name?: string; registration_number: string; is_active?: boolean };
type Group = { id: number; group_name: string; academic_cycle: string | null; members: Member[]; supervisor: { name: string } | null; supervisor_assignment: { id: number } | null };
type Channel = { id: number; group_id: number; group_name: string; cycle_name: string; status: string; assignment_status: string; members: Member[]; supervisor: { name: string } | null; last_read_message_id: number };
type Message = { id: number; sender_user_id: number; sender_name: string; sender_role: string; message_text: string; created_at: string };

async function read<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...options, credentials: "include" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(item => item.msg).join(" ") : detail?.message || `Collaboration request failed (HTTP ${response.status}).`);
  }
  return body as T;
}

export function StudentCollaborationChannel({ api, userId }: { api: string; userId: number }) {
  const [group, setGroup] = useState<Group | null>(null);
  const [channel, setChannel] = useState<Channel | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [readError, setReadError] = useState("");
  const [olderAvailable, setOlderAvailable] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [messagesReady, setMessagesReady] = useState(false);
  const [messageStatus, setMessageStatus] = useState("");
  const [open, setOpen] = useState(true);
  const history = useRef<HTMLDivElement>(null);
  const stickToLatest = useRef(true);
  const sendPending = useRef(false);
  const lastRead = useRef(0);
  const readPending = useRef(false);
  const initialized = useRef(false);
  const activeChannel = useRef<number | null>(null);

  const refreshChannel = useCallback(async (signal?: AbortSignal) => {
    try {
      const [currentGroup, channels] = await Promise.all([
        read<Group>(`${api}/api/v1/student/group/me`, { signal }),
        read<Channel[]>(`${api}/api/v1/student/collaboration/channels`, { signal }),
      ]);
      setGroup(currentGroup);
      const current = channels.find(item => item.group_id === currentGroup.id) ?? null;
      if ((current?.id ?? null) !== activeChannel.current) {
        activeChannel.current = current?.id ?? null;
        setMessages([]); setDraft(""); setMessagesReady(false); initialized.current = false; stickToLatest.current = true;
        lastRead.current = current?.last_read_message_id ?? 0;
      }
      setChannel(current);
      if (current) lastRead.current = Math.max(lastRead.current, current.last_read_message_id);
      setError("");
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : "The collaboration channel could not be loaded.");
    } finally { if (!signal?.aborted) setLoading(false); }
  }, [api]);

  useEffect(() => {
    const controller = new AbortController();
    const initial = window.setTimeout(() => void refreshChannel(controller.signal), 0);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refreshChannel(controller.signal); }, 10000);
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(timer); };
  }, [refreshChannel]);

  const channelId = channel?.id;
  const markRead = useCallback(async (messageId: number) => {
    if (!channelId || messageId <= lastRead.current || readPending.current || document.visibilityState !== "visible") return;
    const bounds = history.current?.getBoundingClientRect();
    if (!bounds || bounds.top >= window.innerHeight || bounds.bottom <= 0) return;
    readPending.current = true;
    try {
      const result = await read<{ last_read_message_id: number }>(`${api}/api/v1/student/collaboration/channels/${channelId}/read`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message_id: messageId }) });
      lastRead.current = result.last_read_message_id; setReadError("");
    } catch (caught) { setReadError(caught instanceof Error ? caught.message : "Read status could not be saved."); }
    finally { readPending.current = false; }
  }, [api, channelId]);

  const refreshMessages = useCallback(async (signal?: AbortSignal) => {
    if (!channelId) return;
    try {
      const incoming = await read<Message[]>(`${api}/api/v1/student/collaboration/channels/${channelId}/messages?limit=100`, { signal });
      if (signal?.aborted || activeChannel.current !== channelId) return;
      if (!initialized.current) { setOlderAvailable(incoming.length === 100); initialized.current = true; }
      setMessages(previous => mergeCollaborationMessages(previous, incoming)); setMessagesReady(true); setError("");
    } catch (caught) {
      if (!signal?.aborted) { setMessagesReady(true); setError(caught instanceof Error ? caught.message : "Messages could not be loaded."); }
    }
  }, [api, channelId]);

  useEffect(() => {
    if (!channelId || !open) return;
    const controller = new AbortController();
    initialized.current = false; stickToLatest.current = true;
    const initial = window.setTimeout(() => void refreshMessages(controller.signal), 0);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refreshMessages(controller.signal); }, 5000);
    const focus = () => void refreshMessages(controller.signal);
    window.addEventListener("focus", focus);
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(timer); window.removeEventListener("focus", focus); };
  }, [channelId, open, refreshMessages]);

  useEffect(() => {
    if (open && history.current && stickToLatest.current) {
      history.current.scrollTop = history.current.scrollHeight;
      const latest = messages.at(-1);
      if (latest) {
        const timer = window.setTimeout(() => void markRead(latest.id), 0);
        return () => window.clearTimeout(timer);
      }
    }
  }, [messages, open, markRead]);

  const send = async () => {
    if (!channelId || sendPending.current) return;
    const invalid = validateCollaborationMessage(draft);
    if (invalid) { setError(invalid); return; }
    sendPending.current = true; setSending(true); setError(""); setMessageStatus("");
    const text = draft;
    try {
      const message = await read<Message>(`${api}/api/v1/student/collaboration/channels/${channelId}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message_text: text }) });
      if (activeChannel.current !== channelId) return;
      stickToLatest.current = true;
      setMessages(previous => mergeCollaborationMessages(previous, [message]));
      setDraft(current => current === text ? "" : current); setMessageStatus("Message sent.");
      await refreshMessages();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Message could not be sent. Your draft has been kept."); }
    finally { sendPending.current = false; setSending(false); }
  };

  const loadOlder = async () => {
    if (!channelId || !messages[0] || loadingOlder) return;
    setLoadingOlder(true);
    const previousHeight = history.current?.scrollHeight ?? 0;
    try {
      const older = await read<Message[]>(`${api}/api/v1/student/collaboration/channels/${channelId}/messages?limit=100&before_id=${messages[0].id}`);
      if (activeChannel.current !== channelId) return;
      stickToLatest.current = false; setMessages(previous => mergeCollaborationMessages(older, previous)); setOlderAvailable(older.length === 100);
      requestAnimationFrame(() => { if (history.current) history.current.scrollTop += history.current.scrollHeight - previousHeight; });
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Earlier messages could not be loaded."); }
    finally { setLoadingOlder(false); }
  };

  const members = (channel?.members ?? group?.members ?? []).filter(member => member.is_active !== false);
  return <section className="student-collab" aria-labelledby="student-collab-heading">
    <div className="student-collab__heading"><div><h2 id="student-collab-heading">Collaboration Channel</h2><p>Private discussion for your group and accepted supervisor.</p></div><button type="button" aria-expanded={open} aria-controls="student-collab-content" onClick={() => setOpen(value => !value)}>{open ? "Collapse channel" : "Open channel"}</button></div>
    {open && <div id="student-collab-content">
      {loading ? <p role="status">Loading your collaboration channel…</p> : <>
        <dl className="student-collab__details"><div><dt>Group</dt><dd>{channel?.group_name ?? group?.group_name ?? "Not available"}</dd></div><div><dt>Academic cycle</dt><dd>{channel?.cycle_name ?? group?.academic_cycle ?? "Not configured"}</dd></div><div><dt>Assigned supervisor</dt><dd>{channel?.supervisor?.name ?? group?.supervisor?.name ?? "Not assigned"}</dd></div><div><dt>Assignment status</dt><dd>{channel?.assignment_status ?? "Awaiting supervisor acceptance"}</dd></div></dl>
        <div className="student-collab__members"><strong>Group members</strong><ul>{members.map(member => <li key={member.id}>{member.name ?? member.full_name} <span>{member.registration_number}</span></li>)}</ul></div>
        {!channel ? <p className="student-collab__notice">Collaboration channel will be available after a supervisor accepts your request.</p> : <>
          <div className="student-collab__toolbar"><span>Group conversation</span><button type="button" onClick={() => void refreshMessages()}>Refresh messages</button></div>
          <div ref={history} className="student-collab__history" role="region" aria-label="Collaboration message history" tabIndex={0} onScroll={() => { const element = history.current; if (!element) return; stickToLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80; if (stickToLatest.current && messages.at(-1)) void markRead(messages.at(-1)!.id); }}>
            {olderAvailable && <button type="button" disabled={loadingOlder} onClick={() => void loadOlder()}>{loadingOlder ? "Loading…" : "Load earlier messages"}</button>}
            {!messagesReady && !messages.length ? <p role="status">Loading messages…</p> : !messages.length ? <p>No messages yet. Start the conversation with your group.</p> : messages.map(message => <article key={message.id} className={`student-collab__message ${message.sender_user_id === userId ? "student-collab__message--own" : ""}`}><header><strong>{message.sender_name}</strong><span>{message.sender_role === "SUPERVISOR" ? "Supervisor" : "Student group member"}</span><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleString()}</time></header><pre>{message.message_text}</pre></article>)}
          </div>
          <form className="student-collab__composer" onSubmit={event => { event.preventDefault(); void send(); }}><label htmlFor="student-collab-message">Message your group and supervisor</label><textarea id="student-collab-message" rows={4} maxLength={COLLABORATION_MESSAGE_LIMIT} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Write a message…" onKeyDown={event => { if (sendsOnEnter({ key: event.key, shiftKey: event.shiftKey, isComposing: event.nativeEvent.isComposing })) { event.preventDefault(); void send(); } }} /><div><small>Enter to send · Shift + Enter for a new line · {draft.length}/{COLLABORATION_MESSAGE_LIMIT}</small><button type="submit" disabled={sending || !draft.trim()}>{sending ? "Sending…" : "Send message"}</button></div></form>
          {messageStatus && <p role="status">{messageStatus}</p>}{readError && <p role="status">{readError}</p>}
        </>}
      </>}
      {error && <div className="student-collab__error" role="alert">{error} <button type="button" onClick={() => { void refreshChannel(); void refreshMessages(); }}>Try again</button></div>}
    </div>}
  </section>;
}
