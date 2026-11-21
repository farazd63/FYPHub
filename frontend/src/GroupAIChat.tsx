/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useRef, useState } from "react";
import "./group-ai.css";
import { sendsOnEnter } from "./portals/student/modules/collaboration-message";
import "./portals/shared/conversation-layout.css";

type Message = { id: number; author_kind: string; body: string; created_at: string };

const suggestedQuestions = [
  "Explain this concept in simple language.",
  "Help me write a clear professional email.",
  "Give me a short step-by-step plan for this task.",
  "What are some creative ideas for this topic?",
];

function messageError(response: Response, fallback: string) {
  return response.json().then((body) => {
    if (typeof body?.detail === "string") return body.detail;
    if (body?.detail?.message) return body.detail.message;
    return fallback;
  }).catch(() => fallback);
}

export function GroupAIChat({ api }: { api: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const history = useRef<HTMLDivElement>(null);
  const stickToLatest = useRef(true);
  const temporaryIdRef = useRef(-1);
  const chatUrl = `${api}/api/v1/group-ai`;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(chatUrl, { credentials: "include" });
      if (!response.ok) throw new Error(await messageError(response, "The chatbot history could not be loaded."));
      setMessages(await response.json() as Message[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The chatbot could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [chatUrl]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (loading || !stickToLatest.current) return;
    const frame = window.requestAnimationFrame(() => {
      if (history.current) history.current.scrollTop = history.current.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [loading, messages]);

  const send = async (question = draft) => {
    const body = question.trim();
    if (!body || busy) return;
    const temporaryUserId = temporaryIdRef.current;
    const temporaryAssistantId = temporaryUserId - 1;
    temporaryIdRef.current -= 2;
    const now = new Date().toISOString();
    setBusy(true);
    setError("");
    setDraft("");
    stickToLatest.current = true;
    setMessages((current) => [...current,
      { id: temporaryUserId, author_kind: "USER", body, created_at: now },
      { id: temporaryAssistantId, author_kind: "AI", body: "", created_at: now },
    ]);
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const response = await fetch(chatUrl, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      });
      if (!response.ok) throw new Error(await messageError(response, "Llama 3.1 8B could not answer this question."));
      reader = response.body?.getReader();
      if (!reader) throw new Error("The chatbot stream could not be opened.");
      const decoder = new TextDecoder();
      let buffer = "";
      let complete = false;
      const consume = (eventText: string) => {
        const line = eventText.split("\n").find((item) => item.startsWith("data:"));
        if (!line) return;
        const event = JSON.parse(line.slice(5).trim()) as { type?: string; token?: string; message?: string; question?: Message; answer?: Message };
        if (event.type === "token" && event.token) {
          setMessages((current) => current.map((item) => item.id === temporaryAssistantId ? { ...item, body: item.body + event.token } : item));
        } else if (event.type === "done" && event.question && event.answer) {
          complete = true;
          setMessages((current) => current.map((item) => item.id === temporaryUserId ? event.question! : item.id === temporaryAssistantId ? event.answer! : item));
        } else if (event.type === "error") {
          throw new Error(event.message || "Llama 3.1 8B could not answer this question.");
        }
      };
      while (true) {
        const chunk = await reader.read();
        buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        events.forEach(consume);
        if (chunk.done) break;
      }
      if (buffer.trim()) consume(buffer);
      if (!complete) throw new Error("The chatbot ended before returning a complete answer.");
    } catch (cause) {
      setMessages((current) => current.filter((item) => item.id !== temporaryUserId && item.id !== temporaryAssistantId));
      setError(cause instanceof Error ? cause.message : "Llama 3.1 8B could not answer this question.");
    } finally {
      reader?.releaseLock();
      setBusy(false);
    }
  };

  return <section className="group-ai-page" aria-labelledby="group-ai-heading">
    <div className="group-ai-heading">
      <div>
        <p className="group-ai-eyebrow">Student assistant</p>
        <h1 id="group-ai-heading">AI Chatbot</h1>
        <p>Ask any question and get a direct response from Llama 3.1 8B.</p>
      </div>
    </div>
    {error && <p role="alert" className="group-ai-alert">{error} <button type="button" onClick={() => void load()}>Retry</button></p>}
    <div className="group-ai-card group-ai-conversation">
      <div className="group-ai-card__header">
        <div><h2>Chat with Llama 3.1 8B</h2><p>Recent chatbot messages may be used to keep the conversation coherent.</p></div>
        <span className="group-ai-status">Online assistant</span>
      </div>
      <div ref={history} className="group-ai-messages" aria-live="polite" onScroll={() => {
        const element = history.current;
        if (!element) return;
        stickToLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
      }}>
        {loading && <p className="group-ai-empty">Loading chat history…</p>}
        {!loading && !messages.length && <div className="group-ai-empty"><strong>Start a conversation</strong><p>Ask a question below to get a direct answer.</p></div>}
        {messages.map((message) => <article key={message.id} className={`group-ai-message group-ai-message--${message.author_kind === "AI" ? "assistant" : "user"}`}>
          <div className="group-ai-message__meta"><strong>{message.author_kind === "AI" ? "Llama 3.1 8B" : "You"}</strong><time>{new Date(message.created_at).toLocaleString()}</time></div>
          <p>{message.body}</p>
        </article>)}
      </div>
      <div className="group-ai-prompts">{suggestedQuestions.map((question) => <button key={question} type="button" onClick={() => void send(question)} disabled={busy}>{question}</button>)}</div>
      <form className="group-ai-composer" onSubmit={(event) => { event.preventDefault(); void send(); }}><textarea aria-label="Ask the AI chatbot" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (!busy && sendsOnEnter({ key: event.key, shiftKey: event.shiftKey, isComposing: event.nativeEvent.isComposing })) { event.preventDefault(); void send(); } }} maxLength={4000} placeholder="Ask a question…" rows={3} /><div><span>{draft.length}/4000</span><button type="submit" disabled={busy || !draft.trim()}>{busy ? "Streaming…" : "Ask chatbot"}</button></div></form>
    </div>
  </section>;
}
