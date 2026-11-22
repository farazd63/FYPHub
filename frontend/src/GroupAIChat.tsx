/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useRef, useState } from "react";
import { History as HistoryIcon, MessageSquarePlus, PanelLeftClose, PanelLeftOpen, Square, Trash2 } from "lucide-react";
import "./group-ai.css";
import { sendsOnEnter } from "./portals/student/modules/collaboration-message";
import "./portals/shared/conversation-layout.css";
import "./group-ai-overrides.css";

type Message = {
  id: number;
  author_kind: string;
  body: string;
  created_at: string;
};

type Conversation = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
};

type GroupAIChatProps = {
  api: string;
  floating?: boolean;
  open?: boolean;
  historyCollapsed?: boolean;
  onClose?: () => void;
  onToggleHistory?: () => void;
};

type StreamEvent = {
  type?: string;
  token?: string;
  message?: string;
  question?: Message;
  answer?: Message;
  conversation?: Conversation;
};

const suggestedQuestions = [
  "Explain this concept in simple language.",
  "Help me write a clear professional email.",
  "Give me a short step-by-step plan for this task.",
  "What are some creative ideas for this topic?",
];

function messageError(response: Response, fallback: string) {
  return response
    .json()
    .then((body) => {
      if (typeof body?.detail === "string") return body.detail;
      if (body?.detail?.message) return body.detail.message;
      return fallback;
    })
    .catch(() => fallback);
}

export function GroupAIChat({
  api,
  floating = false,
  open = true,
  historyCollapsed = false,
  onClose,
  onToggleHistory,
}: GroupAIChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<
    number | null
  >(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(!floating);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deletingConversationId, setDeletingConversationId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [localHistoryCollapsed, setLocalHistoryCollapsed] = useState(false);
  const history = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const activeReader = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const stickToLatest = useRef(true);
  const temporaryIdRef = useRef(-1);
  const chatUrl = `${api}/api/v1/group-ai`;
  const conversationsUrl = `${chatUrl}/conversations`;

  const loadConversations = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(conversationsUrl, {
        credentials: "include",
      });
      if (!response.ok)
        throw new Error(
          await messageError(response, "Chat history could not be loaded."),
        );
      setConversations((await response.json()) as Conversation[]);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Chat history could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [conversationsUrl]);

  const loadConversation = useCallback(
    async (conversationId: number) => {
      setConversationLoading(true);
      setError("");
      setSelectedConversationId(conversationId);
      setMessages([]);
      try {
        const response = await fetch(`${conversationsUrl}/${conversationId}`, {
          credentials: "include",
        });
        if (!response.ok)
          throw new Error(
            await messageError(response, "This chat could not be opened."),
          );
        const body = (await response.json()) as {
          conversation: Conversation;
          messages: Message[];
        };
        setMessages(body.messages);
        setConversations((current) =>
          current.map((item) =>
            item.id === body.conversation.id ? body.conversation : item,
          ),
        );
        stickToLatest.current = true;
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : "This chat could not be opened.",
        );
      } finally {
        setConversationLoading(false);
      }
    },
    [conversationsUrl],
  );

  useEffect(() => {
    if (floating && !open) return;
    void loadConversations();
  }, [floating, loadConversations, open]);

  useEffect(() => {
    if (loading || conversationLoading || selectedConversationId !== null)
      return;
    const frame = window.requestAnimationFrame(() => composer.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [conversationLoading, loading, selectedConversationId]);

  useEffect(() => {
    if (conversationLoading || !stickToLatest.current) return;
    const frame = window.requestAnimationFrame(() => {
      if (history.current)
        history.current.scrollTop = history.current.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [conversationLoading, messages]);

  const startNewChat = () => {
    setSelectedConversationId(null);
    setMessages([]);
    setDraft("");
    setError("");
    setConversationLoading(false);
    stickToLatest.current = true;
  };

  const deleteConversation = async (conversation: Conversation) => {
    if (busy || deletingConversationId !== null) {
      if (busy) setError("Stop the current response before deleting this chat.");
      return;
    }
    if (!window.confirm(`Delete “${conversation.title}”? This cannot be undone.`)) return;
    setDeletingConversationId(conversation.id);
    setError("");
    try {
      const response = await fetch(`${conversationsUrl}/${conversation.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) throw new Error(await messageError(response, "This chat could not be deleted."));
      setConversations((current) => current.filter((item) => item.id !== conversation.id));
      if (selectedConversationId === conversation.id) startNewChat();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "This chat could not be deleted.");
    } finally {
      setDeletingConversationId(null);
    }
  };

  const updateConversation = (conversation: Conversation) => {
    setConversations((current) => [
      conversation,
      ...current.filter((item) => item.id !== conversation.id),
    ]);
  };

  const historyIsCollapsed = onToggleHistory ? historyCollapsed : localHistoryCollapsed;
  const toggleHistory = () => {
    if (onToggleHistory) onToggleHistory();
    else setLocalHistoryCollapsed((current) => !current);
  };

  const stop = () => {
    activeRequest.current?.abort();
    const reader = activeReader.current;
    if (reader) void reader.cancel().catch(() => undefined);
  };

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
    setMessages((current) => [
      ...current,
      { id: temporaryUserId, author_kind: "USER", body, created_at: now },
      {
        id: temporaryAssistantId,
        author_kind: "AI",
        body: "",
        created_at: now,
      },
    ]);
    const requestController = new AbortController();
    activeRequest.current = requestController;
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let activeConversationId = selectedConversationId;
    try {
      if (activeConversationId === null) {
        const createResponse = await fetch(conversationsUrl, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
          signal: requestController.signal,
        });
        if (!createResponse.ok)
          throw new Error(
            await messageError(
              createResponse,
              "A new chat could not be started.",
            ),
          );
        const conversation = (await createResponse.json()) as Conversation;
        activeConversationId = conversation.id;
        setSelectedConversationId(conversation.id);
        updateConversation(conversation);
      }

      const response = await fetch(
        `${conversationsUrl}/${activeConversationId}/messages`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body }),
          signal: requestController.signal,
        },
      );
      if (!response.ok)
        throw new Error(
          await messageError(
            response,
            "Llama 3.1 8B could not answer this question.",
          ),
        );
      reader = response.body?.getReader();
      if (!reader) throw new Error("The chatbot stream could not be opened.");
      activeReader.current = reader;
      const decoder = new TextDecoder();
      let buffer = "";
      let complete = false;
      const consume = (eventText: string) => {
        const line = eventText
          .split("\n")
          .find((item) => item.startsWith("data:"));
        if (!line) return;
        const event = JSON.parse(line.slice(5).trim()) as StreamEvent;
        if (event.type === "token" && event.token) {
          setMessages((current) =>
            current.map((item) =>
              item.id === temporaryAssistantId
                ? { ...item, body: item.body + event.token }
                : item,
            ),
          );
        } else if (event.type === "done" && event.question && event.answer) {
          complete = true;
          setMessages((current) =>
            current.map((item) =>
              item.id === temporaryUserId
                ? event.question!
                : item.id === temporaryAssistantId
                  ? event.answer!
                  : item,
            ),
          );
          if (event.conversation) updateConversation(event.conversation);
        } else if (event.type === "error") {
          throw new Error(
            event.message || "Llama 3.1 8B could not answer this question.",
          );
        }
      };
      while (true) {
        const chunk = await reader.read();
        buffer += decoder.decode(chunk.value || new Uint8Array(), {
          stream: !chunk.done,
        });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        events.forEach(consume);
        if (chunk.done) break;
      }
      if (buffer.trim()) consume(buffer);
      if (!complete)
        throw new Error(
          "The chatbot ended before returning a complete answer.",
        );
    } catch (cause) {
      if (requestController.signal.aborted) {
        setMessages((current) =>
          current.filter(
            (item) => item.id !== temporaryAssistantId || item.body.trim(),
          ),
        );
        setError("");
      } else {
        setMessages((current) =>
          current.filter(
            (item) =>
              item.id !== temporaryUserId && item.id !== temporaryAssistantId,
          ),
        );
        setError(
          cause instanceof Error
            ? cause.message
            : "Llama 3.1 8B could not answer this question.",
        );
      }
    } finally {
      reader?.releaseLock();
      if (activeReader.current === reader) activeReader.current = null;
      if (activeRequest.current === requestController) activeRequest.current = null;
      setBusy(false);
    }
  };

  const historyRail = (
    <aside
      className={`group-ai-history${historyIsCollapsed ? " group-ai-history--collapsed" : ""}`}
      aria-label="Chat history"
    >
      <div className="group-ai-history__header">
        <div>
          <span>Chats</span>
          <strong>History</strong>
        </div>
        <div className="group-ai-history__actions">
          {!historyIsCollapsed && (
            <button
              type="button"
              className="group-ai-new-chat"
              onClick={startNewChat}
              aria-label="Start a new chat"
              title="Start a new chat"
            >
              +
            </button>
          )}
          <button
            type="button"
            className="group-ai-history__toggle"
            onClick={toggleHistory}
            aria-label={historyIsCollapsed ? "Show chat history" : "Hide chat history"}
            title={historyIsCollapsed ? "Show chat history" : "Hide chat history"}
            aria-expanded={!historyIsCollapsed}
          >
            {historyIsCollapsed ? <PanelLeftOpen size={16} strokeWidth={1.8} aria-hidden="true" /> : <PanelLeftClose size={16} strokeWidth={1.8} aria-hidden="true" />}
          </button>
        </div>
      </div>
      {historyIsCollapsed && (
        <nav className="group-ai-history__rail" aria-label="Chat history shortcuts">
          <button
            type="button"
            className={`group-ai-history__rail-button${selectedConversationId === null ? " is-active" : ""}`}
            onClick={startNewChat}
            aria-label="Start a new chat"
            title="Start a new chat"
            aria-pressed={selectedConversationId === null}
          >
            <MessageSquarePlus size={19} strokeWidth={1.8} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="group-ai-history__rail-button"
            onClick={toggleHistory}
            aria-label="Show chat history"
            title="Show chat history"
          >
            <HistoryIcon size={19} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </nav>
      )}
      {!historyIsCollapsed && <button
        type="button"
        className={`group-ai-history__new${selectedConversationId === null ? " is-active" : ""}`}
        onClick={startNewChat}
      >
        <span className="group-ai-history__new-icon">+</span>
        <span>New chat</span>
      </button>}
      {!historyIsCollapsed && <div className="group-ai-history__list">
        {loading && <p className="group-ai-history__empty">Loading chats...</p>}
        {!loading && !conversations.length && (
          <p className="group-ai-history__empty">
            Your previous chats will appear here.
          </p>
        )}
        {conversations.map((conversation) => (
          <div key={conversation.id} className="group-ai-history__item-row">
            <button
              type="button"
              className={`group-ai-history__item${selectedConversationId === conversation.id ? " is-active" : ""}`}
              onClick={() => void loadConversation(conversation.id)}
              aria-current={
                selectedConversationId === conversation.id ? "page" : undefined
              }
            >
              <strong title={conversation.title}>{conversation.title}</strong>
              <span>
                {conversation.message_count
                  ? `${conversation.message_count} messages`
                  : "New chat"}
              </span>
            </button>
            <button
              type="button"
              className="group-ai-history__delete"
              aria-label={`Delete ${conversation.title}`}
              title="Delete chat"
              disabled={busy || deletingConversationId !== null}
              onClick={() => void deleteConversation(conversation)}
            >
              <Trash2 size={15} strokeWidth={1.8} aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>}
    </aside>
  );

  const conversation = (
    <div className="group-ai-card group-ai-conversation">
      <div
        ref={history}
        className="group-ai-messages"
        aria-live="polite"
        onScroll={() => {
          const element = history.current;
          if (!element) return;
          stickToLatest.current =
            element.scrollHeight - element.scrollTop - element.clientHeight <
            80;
        }}
      >
        {conversationLoading && (
          <p className="group-ai-empty">Opening chat...</p>
        )}
        {!conversationLoading && !loading && !messages.length && (
          <div className="group-ai-empty">
            <strong>Start a new conversation</strong>
            <p>Type a question below and press Enter to ask Llama 3.1 8B.</p>
          </div>
        )}
        {messages.map((message) => (
          <article
            key={message.id}
            className={`group-ai-message group-ai-message--${message.author_kind === "AI" ? "assistant" : "user"}`}
          >
            <div className="group-ai-message__meta">
              <strong>
                {message.author_kind === "AI" ? "Llama 3.1 8B" : "You"}
              </strong>
              <time>{new Date(message.created_at).toLocaleString()}</time>
            </div>
            <p>{message.body}</p>
          </article>
        ))}
      </div>
      <div className="group-ai-prompts">
        {suggestedQuestions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => void send(question)}
            disabled={busy}
          >
            {question}
          </button>
        ))}
      </div>
      <form
        className="group-ai-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <textarea
          ref={composer}
          aria-label="Ask the AI chatbot"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (
              !busy &&
              sendsOnEnter({
                key: event.key,
                shiftKey: event.shiftKey,
                isComposing: event.nativeEvent.isComposing,
              })
            ) {
              event.preventDefault();
              void send();
            }
          }}
          maxLength={4000}
          placeholder="Ask a question..."
          rows={3}
        />
        <div>
          <span>{draft.length}/4000</span>
          {busy ? (
            <button
              type="button"
              className="group-ai-stop-button"
              onClick={stop}
              aria-label="Stop chatbot response"
            >
              <Square size={13} strokeWidth={2.2} aria-hidden="true" />
              Stop
            </button>
          ) : (
            <button type="submit" disabled={!draft.trim()}>
              Ask chatbot
            </button>
          )}
        </div>
      </form>
    </div>
  );

  const workspace = (
    <div className="group-ai-workspace">
      {historyRail}
      {conversation}
    </div>
  );

  if (floating) {
    if (!open) return null;
    return (
      <aside className="group-ai-floating-panel" aria-label="AI chatbot">
        <div className="group-ai-floating-panel__header">
          <div className="group-ai-floating-panel__identity">
            <span className="group-ai-floating-panel__avatar" aria-hidden="true">AI</span>
            <div>
              <span className="group-ai-floating-panel__eyebrow">
                FYPHub assistant
              </span>
              <h2>Chatbot</h2>
              <p>Llama 3.1 8B</p>
            </div>
          </div>
          <button
            type="button"
            className="group-ai-floating-panel__close"
            aria-label="Close chatbot"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        {error && (
          <p role="alert" className="group-ai-alert">
            {error}{" "}
            <button
              type="button"
              onClick={() =>
                selectedConversationId === null
                  ? void loadConversations()
                  : void loadConversation(selectedConversationId)
              }
            >
              Retry
            </button>
          </p>
        )}
        {workspace}
      </aside>
    );
  }

  return (
    <section className="group-ai-page" aria-labelledby="group-ai-heading">
      <div className="group-ai-heading">
        <div className="group-ai-heading__identity">
          <span className="group-ai-heading__avatar" aria-hidden="true">AI</span>
          <div>
            <p className="group-ai-eyebrow">FYPHub assistant</p>
            <h1 id="group-ai-heading">AI Chatbot</h1>
            <p>Ask any question and get a direct response from Llama 3.1 8B.</p>
          </div>
        </div>
      </div>
      {error && (
        <p role="alert" className="group-ai-alert">
          {error}{" "}
          <button
            type="button"
            onClick={() =>
              selectedConversationId === null
                ? void loadConversations()
                : void loadConversation(selectedConversationId)
            }
          >
            Retry
          </button>
        </p>
      )}
      {workspace}
    </section>
  );
}
