import { useCallback, useEffect, useState } from "react";

type Message = { id: number; sender_name: string; sender_role: string; body: string; created_at: string };

export function RequestConversation({ api, requestId, readOnly = false }: { api: string; requestId: number; readOnly?: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [body, setBody] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const response = await fetch(`${api}/api/v1/supervisor-requests/${requestId}/conversation`, { credentials: "include" });
      if (!response.ok) throw new Error();
      setMessages(await response.json() as Message[]);
    } catch {
      setMessage("Conversation is not available for this request.");
    }
  }, [api, requestId]);
  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!body.trim() || busy) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/supervisor-requests/${requestId}/conversation`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      });
      if (!response.ok) throw new Error();
      setBody("");
      await load();
    } catch {
      setMessage("Message could not be sent.");
    } finally {
      setBusy(false);
    }
  };
  return <section className="student-request-conversation" aria-labelledby={`request-conversation-${requestId}`}>
    <h3 id={`request-conversation-${requestId}`}>Request conversation</h3>
    {message && <p role="alert">{message}</p>}
    <div className="student-conversation-list">
      {messages.length ? messages.map((item) => <article key={item.id}><strong>{item.sender_name}</strong><small>{item.sender_role} · {new Date(item.created_at).toLocaleString()}</small><p>{item.body}</p></article>) : <p>No messages yet.</p>}
    </div>
    {readOnly ? <p className="student-request-muted">Read-only conversation access for this role.</p> : <form onSubmit={send}><textarea value={body} maxLength={4000} onChange={(event) => setBody(event.target.value)} placeholder="Write an authorized request message" /><button type="submit" disabled={busy || !body.trim()}>Send message</button></form>}
  </section>;
}
