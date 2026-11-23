import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import {
  CalendarDays,
  Camera,
  Contact,
  FileText,
  Headphones,
  Image as ImageIcon,
  ListChecks,
  MapPin,
  Mic,
  Paperclip,
  Pencil,
  RefreshCw,
  Send,
  Smile,
  Square,
  Sticker,
  Store,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { COLLABORATION_MESSAGE_LIMIT, mergeCollaborationMessages, sendsOnEnter, validateCollaborationMessage } from "./collaboration-message";
import { IconButton } from "../../../ui/IconButton";
import { CollaborationAttachment } from "../../shared/CollaborationAttachment";
import "./student-collaboration.css";
import "../../shared/conversation-layout.css";

type Member = { id: number; name?: string; full_name?: string; registration_number: string; email?: string | null; is_active?: boolean };
type MemberIdentity = { member_id: number; name: string; registration_number: string; password_set: boolean; is_verified: boolean; reset_requested: boolean };
type Group = { id: number; group_name: string; academic_cycle: string | null; members: Member[]; supervisor: { name: string } | null; supervisor_assignment: { id: number } | null };
type Channel = { id: number; group_id: number; group_name: string; cycle_name: string; status: string; assignment_status: string; members: Member[]; supervisor: { name: string } | null; last_read_message_id: number };
type MessageKind = "TEXT" | "DOCUMENT" | "MEDIA" | "AUDIO" | "CONTACT" | "POLL" | "EVENT" | "STICKER" | "CATALOGUE" | "QUICK_REPLY";
type Message = {
  id: number;
  sender_user_id: number;
  sender_member_id?: number | null;
  sender_member_name?: string | null;
  sender_member_registration_number?: string | null;
  sender_name: string;
  sender_role: string;
  message_text: string;
  message_kind?: MessageKind;
  message_payload?: Record<string, unknown>;
  attachment_reference?: string | null;
  created_at: string;
  updated_at?: string;
  deleted_at?: string | null;
};
type StructuredKind = "CONTACT" | "POLL" | "EVENT" | "CATALOGUE" | "QUICK_REPLY";
type StructuredDraft = { question: string; optionOne: string; optionTwo: string; optionThree: string; title: string; date: string; time: string; location: string; details: string; link: string };
type FileAction = { id: string; label: string; kind: "DOCUMENT" | "MEDIA" | "AUDIO" | "STICKER"; accept: string; capture?: "environment" };
type PendingAttachment = { file: File; kind: FileAction["kind"]; previewUrl: string; confirmed: boolean };
export type CollaborationRole = "student" | "supervisor";
type CollaborationChannelProps = { api: string; userId?: number; role?: CollaborationRole; groupId?: number; className?: string };

const FILE_ACTIONS: FileAction[] = [
  { id: "document", label: "Document", kind: "DOCUMENT", accept: ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.zip" },
  { id: "media", label: "Photos & videos", kind: "MEDIA", accept: "image/*,video/*" },
  { id: "camera", label: "Camera", kind: "MEDIA", accept: "image/*", capture: "environment" },
  { id: "audio", label: "Audio", kind: "AUDIO", accept: "audio/*" },
  { id: "sticker", label: "New sticker", kind: "STICKER", accept: "image/*" },
];

const QUICK_REPLIES = ["I will review this.", "Let's meet tomorrow.", "The document is uploaded."];
const EMPTY_STRUCTURED_DRAFT: StructuredDraft = { question: "", optionOne: "", optionTwo: "", optionThree: "", title: "", date: "", time: "", location: "", details: "", link: "" };

async function read<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...options, credentials: "include" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(item => item.msg).join(" ") : detail?.message || "Collaboration request failed.");
  }
  return body as T;
}

function stringValue(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === "string" ? value : "";
}

function payloadList(payload: Record<string, unknown>, key: string): string[] {
  return Array.isArray(payload[key]) ? payload[key].filter((value): value is string => typeof value === "string") : [];
}

function fileSizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function voiceDurationLabel(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function collaborationPasswordPolicyError(password: string): string {
  const missing: string[] = [];
  if (password.length < 8) missing.push("8 characters");
  if (!/[A-Z]/.test(password)) missing.push("an uppercase letter");
  if (!/[a-z]/.test(password)) missing.push("a lowercase letter");
  if (!/[0-9]/.test(password)) missing.push("a number");
  if (!/[^A-Za-z0-9]/.test(password)) missing.push("a special character");
  return missing.length ? `Use at least ${missing.join(", ")}.` : "";
}

export function CollaborationChannel({ api, userId, role = "student", groupId, className = "" }: CollaborationChannelProps) {
  const collaborationBase = api + "/api/v1/" + role;
  const supervisorMode = role === "supervisor";
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
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [messageMutationId, setMessageMutationId] = useState<number | null>(null);
  const [open, setOpen] = useState(true);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(() => {
    const requestedMemberId = Number(new URLSearchParams(window.location.search).get("member_id"));
    return Number.isInteger(requestedMemberId) && requestedMemberId > 0 ? requestedMemberId : null;
  });
  const [memberIdentity, setMemberIdentity] = useState<MemberIdentity[]>([]);
  const [identityPassword, setIdentityPassword] = useState("");
  const [identityConfirmPassword, setIdentityConfirmPassword] = useState("");
  const [identityBusy, setIdentityBusy] = useState(false);
  const [identityError, setIdentityError] = useState("");
  const [identityNotice, setIdentityNotice] = useState("");
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [fileAction, setFileAction] = useState<FileAction | null>(null);
  const [pendingAttachment, setPendingAttachment] = useState<PendingAttachment | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [structuredKind, setStructuredKind] = useState<StructuredKind | null>(null);
  const [structuredDraft, setStructuredDraft] = useState<StructuredDraft>(EMPTY_STRUCTURED_DRAFT);
  const history = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const recordingStream = useRef<MediaStream | null>(null);
  const recordingChunks = useRef<Blob[]>([]);
  const recordingTimer = useRef<number | null>(null);
  const stickToLatest = useRef(true);
  const sendPending = useRef(false);
  const lastRead = useRef(0);
  const readPending = useRef(false);
  const initialized = useRef(false);
  const activeChannel = useRef<number | null>(null);
  const channelId = channel?.id;

  const refreshChannel = useCallback(async (signal?: AbortSignal) => {
    try {
      const channelsPromise = read<Channel[]>(collaborationBase + "/collaboration/channels", { signal });
      const [currentGroup, channels] = supervisorMode
        ? [null, await channelsPromise] as const
        : await Promise.all([read<Group>(api + "/api/v1/student/group/me", { signal }), channelsPromise]);
      setGroup(currentGroup);
      const current = channels.find(item => item.group_id === (supervisorMode ? groupId : currentGroup?.id)) ?? null;
      if ((current?.id ?? null) !== activeChannel.current) {
        activeChannel.current = current?.id ?? null;
        if (recorder.current?.state === "recording") recorder.current.stop();
        recordingStream.current?.getTracks().forEach(track => track.stop());
        if (recordingTimer.current !== null) window.clearInterval(recordingTimer.current);
        recorder.current = null;
        recordingStream.current = null;
        recordingTimer.current = null;
        setRecording(false);
        setRecordingSeconds(0);
        setMessages([]);
        setDraft("");
        setPendingAttachment(null);
        setMessagesReady(false);
        setEditingMessageId(null);
        setEditDraft("");
        const requestedMemberId = Number(new URLSearchParams(window.location.search).get("member_id"));
        const requestedMemberIsInChannel = new URLSearchParams(window.location.search).get("focus") === "collaboration-password"
          && Number.isInteger(requestedMemberId)
          && requestedMemberId > 0
          && current?.members.some(member => member.id === requestedMemberId);
        setSelectedMemberId(requestedMemberIsInChannel ? requestedMemberId : null);
        setMemberIdentity([]);
        setIdentityPassword("");
        setIdentityConfirmPassword("");
        setIdentityError("");
        setIdentityNotice("");
        initialized.current = false;
        stickToLatest.current = true;
        lastRead.current = current?.last_read_message_id ?? 0;
      }
      setChannel(current);
      if (!supervisorMode && current) {
        try {
          const identity = await read<{ members: MemberIdentity[] }>(collaborationBase + "/collaboration/channels/" + current.id + "/member-identity", { signal });
          if (!signal?.aborted) setMemberIdentity(identity.members ?? []);
        } catch (caught) {
          if (!signal?.aborted) setIdentityError(caught instanceof Error ? caught.message : "Member identity status could not be loaded.");
        }
      } else {
        setMemberIdentity([]);
      }
      if (current) lastRead.current = Math.max(lastRead.current, current.last_read_message_id);
      setError("");
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : "The collaboration channel could not be loaded.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [api, collaborationBase, groupId, supervisorMode]);

  const refreshMemberIdentity = async () => {
    if (!channelId || supervisorMode) return;
    const identity = await read<{ members: MemberIdentity[] }>(collaborationBase + "/collaboration/channels/" + channelId + "/member-identity");
    setMemberIdentity(identity.members ?? []);
  };

  const verifyMemberIdentity = async () => {
    if (!channelId || selectedMemberId === null || identityBusy) return;
    if (!identityPassword) {
      setIdentityError("Enter the collaboration password.");
      return;
    }
    const selected = memberIdentity.find(item => item.member_id === selectedMemberId);
    const isSetup = !selected?.password_set;
    if (isSetup) {
      const policyError = collaborationPasswordPolicyError(identityPassword);
      if (policyError) {
        setIdentityError(policyError);
        return;
      }
    }
    if (isSetup && identityPassword !== identityConfirmPassword) {
      setIdentityError("Passwords do not match.");
      return;
    }
    setIdentityBusy(true);
    setIdentityError("");
    setIdentityNotice("");
    try {
      await read(collaborationBase + "/collaboration/channels/" + channelId + "/member-identity/" + (isSetup ? "setup" : "verify"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isSetup
          ? { member_id: selectedMemberId, password: identityPassword, confirm_password: identityConfirmPassword }
          : { member_id: selectedMemberId, password: identityPassword }),
      });
      setIdentityPassword("");
      setIdentityConfirmPassword("");
      setIdentityNotice("Identity verified. Future messages will use this member's name.");
      await refreshMemberIdentity();
    } catch (caught) {
      setIdentityError(caught instanceof Error ? caught.message : "The collaboration password could not be verified.");
    } finally {
      setIdentityBusy(false);
    }
  };

  const forgotMemberIdentity = async () => {
    if (!channelId || selectedMemberId === null || identityBusy) return;
    setIdentityBusy(true);
    setIdentityError("");
    setIdentityNotice("");
    try {
      await read(collaborationBase + "/collaboration/channels/" + channelId + "/member-identity/forgot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: selectedMemberId }),
      });
      setIdentityNotice("Reset request sent. An administrator will clear the old password, then you can create a new one here.");
      await refreshMemberIdentity();
    } catch (caught) {
      setIdentityError(caught instanceof Error ? caught.message : "The reset request could not be sent.");
    } finally {
      setIdentityBusy(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    const initial = window.setTimeout(() => void refreshChannel(controller.signal), 0);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refreshChannel(controller.signal); }, 10000);
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(timer); };
  }, [refreshChannel]);

  const markRead = useCallback(async (messageId: number) => {
    if (!channelId || messageId <= lastRead.current || readPending.current || document.visibilityState !== "visible") return;
    const bounds = history.current?.getBoundingClientRect();
    if (!bounds || bounds.top >= window.innerHeight || bounds.bottom <= 0) return;
    readPending.current = true;
    try {
      const result = await read<{ last_read_message_id: number }>(collaborationBase + "/collaboration/channels/" + channelId + "/read", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message_id: messageId }) });
      lastRead.current = result.last_read_message_id;
      setReadError("");
    } catch (caught) {
      setReadError(caught instanceof Error ? caught.message : "Read status could not be saved.");
    } finally {
      readPending.current = false;
    }
  }, [channelId, collaborationBase]);

  const refreshMessages = useCallback(async (signal?: AbortSignal) => {
    if (!channelId) return;
    try {
      const incoming = await read<Message[]>(collaborationBase + "/collaboration/channels/" + channelId + "/messages?limit=100", { signal });
      if (signal?.aborted || activeChannel.current !== channelId) return;
      if (!initialized.current) { setOlderAvailable(incoming.length === 100); initialized.current = true; }
      setMessages(previous => mergeCollaborationMessages(previous, incoming));
      setMessagesReady(true);
      setError("");
    } catch (caught) {
      if (!signal?.aborted) {
        setMessagesReady(true);
        setError(caught instanceof Error ? caught.message : "Messages could not be loaded.");
      }
    }
  }, [channelId, collaborationBase]);

  useEffect(() => {
    if (!channelId || !open) return;
    const controller = new AbortController();
    initialized.current = false;
    stickToLatest.current = true;
    const initial = window.setTimeout(() => void refreshMessages(controller.signal), 0);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refreshMessages(controller.signal); }, 5000);
    const focus = () => void refreshMessages(controller.signal);
    window.addEventListener("focus", focus);
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(timer); window.removeEventListener("focus", focus); };
  }, [channelId, open, refreshMessages]);

  useEffect(() => {
    if (open && history.current && stickToLatest.current) {
      const frame = window.requestAnimationFrame(() => { if (history.current) history.current.scrollTop = history.current.scrollHeight; });
      const latest = messages.at(-1);
      if (latest) {
        const timer = window.setTimeout(() => void markRead(latest.id), 0);
        return () => { window.cancelAnimationFrame(frame); window.clearTimeout(timer); };
      }
      return () => window.cancelAnimationFrame(frame);
    }
  }, [messages, open, markRead]);

  useEffect(() => {
    if (!open) return;
    stickToLatest.current = true;
    const frame = window.requestAnimationFrame(() => { if (history.current) history.current.scrollTop = history.current.scrollHeight; });
    return () => window.cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    const closeMenu = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setAttachmentMenuOpen(false);
        setEmojiOpen(false);
        setStructuredKind(null);
      }
    };
    window.addEventListener("keydown", closeMenu);
    return () => window.removeEventListener("keydown", closeMenu);
  }, []);

  useEffect(() => () => {
    if (pendingAttachment?.previewUrl) URL.revokeObjectURL(pendingAttachment.previewUrl);
  }, [pendingAttachment?.previewUrl]);

  useEffect(() => () => {
    if (recorder.current?.state === "recording") recorder.current.stop();
    recordingStream.current?.getTracks().forEach(track => track.stop());
    if (recordingTimer.current !== null) window.clearInterval(recordingTimer.current);
  }, []);

  const clearRecordingResources = () => {
    recordingStream.current?.getTracks().forEach(track => track.stop());
    recordingStream.current = null;
    recorder.current = null;
    if (recordingTimer.current !== null) {
      window.clearInterval(recordingTimer.current);
      recordingTimer.current = null;
    }
  };

  const stopVoiceRecording = () => {
    if (recorder.current?.state === "recording") {
      recorder.current.stop();
    } else {
      setRecording(false);
      clearRecordingResources();
    }
  };

  const startVoiceRecording = async () => {
    if (recording || sending || pendingAttachment) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Voice recording is not supported in this browser.");
      return;
    }
    try {
      setError("");
      setMessageStatus("");
      setAttachmentMenuOpen(false);
      setEmojiOpen(false);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const supportedType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"]
        .find(type => MediaRecorder.isTypeSupported(type));
      const mediaRecorder = supportedType ? new MediaRecorder(stream, { mimeType: supportedType }) : new MediaRecorder(stream);
      recordingStream.current = stream;
      recordingChunks.current = [];
      recorder.current = mediaRecorder;
      setRecordingSeconds(0);
      setRecording(true);
      mediaRecorder.ondataavailable = event => {
        if (event.data.size) recordingChunks.current.push(event.data);
      };
      mediaRecorder.onerror = () => {
        setRecording(false);
        clearRecordingResources();
        setError("Voice recording could not be started.");
      };
      mediaRecorder.onstop = () => {
        const type = mediaRecorder.mimeType || supportedType || "audio/webm";
        const extension = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : "webm";
        const blob = new Blob(recordingChunks.current, { type });
        setRecording(false);
        setRecordingSeconds(0);
        clearRecordingResources();
        if (!blob.size) {
          setError("No voice audio was recorded.");
          return;
        }
        const file = new File([blob], `voice-message-${Date.now()}.${extension}`, { type });
        setPendingAttachment({ file, kind: "AUDIO", previewUrl: URL.createObjectURL(blob), confirmed: false });
        setDraft("");
        setMessageStatus("Voice message recorded. Review and confirm it before sending.");
      };
      mediaRecorder.start();
      recordingTimer.current = window.setInterval(() => setRecordingSeconds(value => value + 1), 1000);
    } catch (caught) {
      setRecording(false);
      clearRecordingResources();
      setError(caught instanceof DOMException && caught.name === "NotAllowedError"
        ? "Microphone access was denied. Allow microphone access to record a voice message."
        : "Voice recording could not be started.");
    }
  };

  const sendPayload = async (
    payload: { message_text: string; message_kind?: MessageKind; message_payload?: Record<string, unknown> },
    successMessage = "Message sent.",
  ): Promise<boolean> => {
    if (!channelId || sendPending.current) return false;
    if (!supervisorMode && selectedMemberId === null) {
      setError("Select the group member sending this message.");
      return false;
    }
    if (!supervisorMode && !memberIdentity.find(item => item.member_id === selectedMemberId)?.is_verified) {
      setError("Verify the selected member's collaboration password before sending.");
      return false;
    }
    const invalid = validateCollaborationMessage(payload.message_text);
    if (invalid) { setError(invalid); return false; }
    sendPending.current = true;
    setSending(true);
    setError("");
    setMessageStatus("");
    try {
      const message = await read<Message>(collaborationBase + "/collaboration/channels/" + channelId + "/messages", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(supervisorMode ? payload : { ...payload, sender_member_id: selectedMemberId }) });
      if (activeChannel.current !== channelId) return false;
      stickToLatest.current = true;
      setMessages(previous => mergeCollaborationMessages(previous, [message]));
      setMessageStatus(successMessage);
      await refreshMessages();
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Message could not be sent.");
      return false;
    } finally {
      sendPending.current = false;
      setSending(false);
    }
  };

  const send = async () => {
    if (pendingAttachment) {
      if (!pendingAttachment.confirmed) {
        setError("Confirm the attachment before sending it.");
        return;
      }
      const attachment = pendingAttachment;
      if (await uploadFile(attachment.file, attachment.kind, draft)) {
        setPendingAttachment(null);
        setDraft("");
      }
      return;
    }
    const text = draft;
    if (await sendPayload({ message_text: text })) setDraft(current => current === text ? "" : current);
  };

  const beginEdit = (message: Message) => {
    setEditingMessageId(message.id);
    setEditDraft(message.message_text);
    setError("");
    setMessageStatus("");
  };

  const cancelEdit = () => {
    setEditingMessageId(null);
    setEditDraft("");
  };

  const saveEdit = async (messageId: number) => {
    if (!channelId || messageMutationId !== null) return;
    const invalid = validateCollaborationMessage(editDraft);
    if (invalid) { setError(invalid); return; }
    setMessageMutationId(messageId);
    setError("");
    setMessageStatus("");
    try {
      const updated = await read<Message>(collaborationBase + "/collaboration/channels/" + channelId + "/messages/" + messageId, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message_text: editDraft }) });
      setMessages(previous => previous.map(message => message.id === messageId ? updated : message));
      cancelEdit();
      setMessageStatus("Message updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Message could not be updated.");
    } finally {
      setMessageMutationId(null);
    }
  };

  const deleteMessage = async (messageId: number) => {
    if (!channelId || messageMutationId !== null || !window.confirm("Delete this message for everyone in the channel?")) return;
    setMessageMutationId(messageId);
    setError("");
    setMessageStatus("");
    try {
      await read<{ id: number }>(collaborationBase + "/collaboration/channels/" + channelId + "/messages/" + messageId, { method: "DELETE" });
      setMessages(previous => previous.filter(message => message.id !== messageId));
      if (editingMessageId === messageId) cancelEdit();
      setMessageStatus("Message deleted.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Message could not be deleted.");
    } finally {
      setMessageMutationId(null);
    }
  };

  const uploadFile = async (file: File, kind: FileAction["kind"], caption = ""): Promise<boolean> => {
    if (!channelId || sendPending.current) return false;
    if (!supervisorMode && selectedMemberId === null) {
      setError("Select the group member sending this file.");
      return false;
    }
    if (!supervisorMode && !memberIdentity.find(item => item.member_id === selectedMemberId)?.is_verified) {
      setError("Verify the selected member's collaboration password before sharing a file.");
      return false;
    }
    sendPending.current = true;
    setSending(true);
    setError("");
    setMessageStatus("");
    const form = new FormData();
    form.append("upload", file);
    form.append("message_kind", kind);
    form.append("caption", caption.trim());
    if (!supervisorMode && selectedMemberId !== null) form.append("sender_member_id", String(selectedMemberId));
    try {
      const message = await read<Message>(collaborationBase + "/collaboration/channels/" + channelId + "/files", { method: "POST", body: form });
      if (activeChannel.current !== channelId) return false;
      stickToLatest.current = true;
      setMessages(previous => mergeCollaborationMessages(previous, [message]));
      setMessageStatus("Shared " + file.name + ".");
      setAttachmentMenuOpen(false);
      await refreshMessages();
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The file could not be shared.");
      return false;
    } finally {
      sendPending.current = false;
      setSending(false);
    }
  };

  const loadOlder = async () => {
    if (!channelId || !messages[0] || loadingOlder) return;
    setLoadingOlder(true);
    const previousHeight = history.current?.scrollHeight ?? 0;
    try {
      const older = await read<Message[]>(collaborationBase + "/collaboration/channels/" + channelId + "/messages?limit=100&before_id=" + messages[0].id);
      if (activeChannel.current !== channelId) return;
      stickToLatest.current = false;
      setMessages(previous => mergeCollaborationMessages(older, previous));
      setOlderAvailable(older.length === 100);
      requestAnimationFrame(() => { if (history.current) history.current.scrollTop += history.current.scrollHeight - previousHeight; });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Earlier messages could not be loaded.");
    } finally {
      setLoadingOlder(false);
    }
  };

  const openFilePicker = (action: FileAction) => {
    setFileAction(action);
    setAttachmentMenuOpen(false);
    window.setTimeout(() => fileInput.current?.click(), 0);
  };

  const openStructured = (kind: StructuredKind) => {
    setStructuredKind(kind);
    setStructuredDraft(EMPTY_STRUCTURED_DRAFT);
    setAttachmentMenuOpen(false);
  };

  const sendStructured = async () => {
    if (!structuredKind || structuredKind === "CONTACT" || structuredKind === "QUICK_REPLY") return;
    if (structuredKind === "POLL") {
      const options = [structuredDraft.optionOne, structuredDraft.optionTwo, structuredDraft.optionThree].map(value => value.trim()).filter(Boolean);
      if (!structuredDraft.question.trim() || options.length < 2) { setError("Add a poll question and at least two options."); return; }
      if (await sendPayload({ message_text: structuredDraft.question.trim(), message_kind: "POLL", message_payload: { question: structuredDraft.question.trim(), options } }, "Poll sent.")) setStructuredKind(null);
      return;
    }
    if (structuredKind === "EVENT") {
      if (!structuredDraft.title.trim() || !structuredDraft.date) { setError("Add an event title and date."); return; }
      const text = structuredDraft.title.trim() + " · " + structuredDraft.date + (structuredDraft.time ? " at " + structuredDraft.time : "");
      if (await sendPayload({ message_text: text, message_kind: "EVENT", message_payload: { title: structuredDraft.title.trim(), date: structuredDraft.date, time: structuredDraft.time, location: structuredDraft.location.trim(), details: structuredDraft.details.trim() } }, "Event sent.")) setStructuredKind(null);
      return;
    }
    if (!structuredDraft.title.trim() || !structuredDraft.details.trim()) { setError("Add a title and details."); return; }
    const text = structuredDraft.title.trim() + " · " + structuredDraft.details.trim();
    if (await sendPayload({ message_text: text, message_kind: "CATALOGUE", message_payload: { title: structuredDraft.title.trim(), details: structuredDraft.details.trim(), link: structuredDraft.link.trim() } }, "Catalogue item sent.")) setStructuredKind(null);
  };

  const sendContact = async (member: Member) => {
    const name = member.name ?? member.full_name ?? "Group contact";
    if (await sendPayload({ message_text: name, message_kind: "CONTACT", message_payload: { name, registration_number: member.registration_number, email: member.email ?? "" } }, "Contact sent.")) setStructuredKind(null);
  };

  const members = (channel?.members ?? group?.members ?? []).filter(member => member.is_active !== false);
  const selectedIdentity = memberIdentity.find(item => item.member_id === selectedMemberId) ?? null;
  const chooseMember = (memberId: number | null) => {
    setSelectedMemberId(memberId);
    setIdentityPassword("");
    setIdentityConfirmPassword("");
    setIdentityError("");
    setIdentityNotice("");
    setError("");
  };
  useEffect(() => {
    if (supervisorMode || !channelId || !memberIdentity.length) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("focus") !== "collaboration-password" || selectedMemberId === null) return;
    window.requestAnimationFrame(() => document.getElementById("student-collaboration-password")?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }, [channelId, memberIdentity.length, selectedMemberId, supervisorMode]);
  const setDraftValue = (key: keyof StructuredDraft, value: string) => setStructuredDraft(current => ({ ...current, [key]: value }));
  const chatTitle = channel?.group_name ?? group?.group_name ?? "Collaboration Channel";
  const chatInitials = chatTitle.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "C";
  const chatSubtitle = channel?.supervisor?.name
    ? `Supervisor ${channel.supervisor.name} · ${members.length} group member${members.length === 1 ? "" : "s"}`
    : `${members.length} group member${members.length === 1 ? "" : "s"} · Private collaboration`;

  const renderMessageContent = (message: Message) => {
    const kind = message.message_kind ?? (message.attachment_reference ? "DOCUMENT" : "TEXT");
    const payload = message.message_payload ?? {};
    if (message.attachment_reference) {
      return <CollaborationAttachment api={api} reference={message.attachment_reference} kind={kind} payload={payload} caption={message.message_text} />;
    }
    if (kind === "CONTACT") {
      return <div className="student-collab__rich-card student-collab__rich-card--contact"><span className="student-collab__rich-icon"><Contact size={18} aria-hidden /></span><div><strong>{stringValue(payload, "name") || message.message_text}</strong><small>{stringValue(payload, "registration_number") || "Group contact"}</small></div></div>;
    }
    if (kind === "POLL") {
      return <div className="student-collab__rich-card student-collab__rich-card--poll"><strong>{stringValue(payload, "question") || message.message_text}</strong><div className="student-collab__poll-options">{payloadList(payload, "options").map(option => <button type="button" key={option} disabled><span>{option}</span><span>Vote</span></button>)}</div></div>;
    }
    if (kind === "EVENT") {
      return <div className="student-collab__rich-card student-collab__rich-card--event"><span className="student-collab__rich-icon"><CalendarDays size={18} aria-hidden /></span><div><strong>{stringValue(payload, "title") || message.message_text}</strong><small>{stringValue(payload, "date")}{stringValue(payload, "time") ? " · " + stringValue(payload, "time") : ""}</small>{stringValue(payload, "location") && <small><MapPin size={12} aria-hidden /> {stringValue(payload, "location")}</small>}</div></div>;
    }
    if (kind === "CATALOGUE") {
      return <div className="student-collab__rich-card"><strong>{stringValue(payload, "title") || "Shared catalogue item"}</strong><p>{stringValue(payload, "details")}</p>{stringValue(payload, "link") && <a href={stringValue(payload, "link")} target="_blank" rel="noreferrer">{stringValue(payload, "link")}</a>}</div>;
    }
    return null;
  };

  return <section className={`student-collab ${className}`.trim()} aria-labelledby="student-collab-heading">
    <div className="student-collab__heading">
      <div className="student-collab__identity">
        <span className="student-collab__avatar" aria-hidden="true">{chatInitials}</span>
        <div>
          <span className="student-collab__eyebrow">Group collaboration</span>
          <h2 id="student-collab-heading">{chatTitle}</h2>
          <p>{chatSubtitle}</p>
        </div>
      </div>
      <div className="student-collab__heading-actions">
        <IconButton label="Refresh messages" size="sm" variant="secondary" onClick={() => { void refreshChannel(); void refreshMessages(); }}><RefreshCw size={15} strokeWidth={1.8} aria-hidden /></IconButton>
        <button type="button" aria-expanded={open} aria-controls="student-collab-content" onClick={() => setOpen(value => !value)}>{open ? "Collapse channel" : "Open channel"}</button>
      </div>
    </div>
    {open && <div id="student-collab-content">
      {loading ? <p role="status">Loading the collaboration channel…</p> : <>
        {!channel ? <p className="student-collab__notice">{supervisorMode ? "This group's collaboration channel is not available yet. Ask an administrator to configure this cycle's year and session." : group?.supervisor_assignment || group?.supervisor ? "Your supervisor is assigned, but the collaboration channel could not be opened yet. Ask an administrator to set this cycle's year and session." : "Collaboration channel will be available after a supervisor is assigned."}</p> : <>
          <div ref={history} className="student-collab__history" role="region" aria-label="Collaboration message history" tabIndex={0} onScroll={() => { const element = history.current; if (!element) return; stickToLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80; if (stickToLatest.current && messages.at(-1)) void markRead(messages.at(-1)!.id); }}>
            {olderAvailable && <button type="button" disabled={loadingOlder} onClick={() => void loadOlder()}>{loadingOlder ? "Loading…" : "Load earlier messages"}</button>}
            {!messagesReady && !messages.length ? <p role="status">Loading messages…</p> : !messages.length ? <p>No messages yet. Start the conversation with your group.</p> : messages.map(message => {
              const kind = message.message_kind ?? (message.attachment_reference ? "DOCUMENT" : "TEXT");
              const isRich = ["CONTACT", "POLL", "EVENT", "CATALOGUE"].includes(kind);
              const hasAttachment = Boolean(message.attachment_reference);
              const isOwn = message.sender_user_id === userId;
              const isEditing = editingMessageId === message.id;
              const isMutating = messageMutationId === message.id;
              return <article key={message.id} className={"student-collab__message " + (isOwn ? "student-collab__message--own" : "")}>
                <header>
                  <strong>{message.sender_name}</strong>
                  {message.sender_member_registration_number && <small> · {message.sender_member_registration_number}</small>}
                  <span>{message.sender_role === "SUPERVISOR" ? "Supervisor" : "Student group member"}</span>
                  <time dateTime={message.created_at}>{new Date(message.created_at).toLocaleString()}</time>
                  {isOwn && <div className="student-collab__message-actions" aria-label="Message actions">
                    <button type="button" className="student-collab__message-action student-collab__message-action--edit" aria-label="Edit message" title="Edit message" disabled={messageMutationId !== null} onClick={() => beginEdit(message)}><Pencil size={13} aria-hidden /></button>
                    <button type="button" className="student-collab__message-action student-collab__message-action--delete" aria-label="Delete message" title="Delete message" disabled={messageMutationId !== null} onClick={() => void deleteMessage(message.id)}><Trash2 size={13} aria-hidden /></button>
                  </div>}
                </header>
                {isEditing ? <form className="student-collab__message-edit" onSubmit={event => { event.preventDefault(); void saveEdit(message.id); }}>
                  <textarea aria-label="Edit message text" value={editDraft} maxLength={COLLABORATION_MESSAGE_LIMIT} onChange={event => setEditDraft(event.target.value)} autoFocus />
                  <div className="student-collab__message-edit-actions">
                    <button type="submit" disabled={isMutating}>{isMutating ? "Savingâ€¦" : "Save"}</button>
                    <button type="button" disabled={isMutating} onClick={cancelEdit}>Cancel</button>
                  </div>
                </form> : <>{!isRich && !hasAttachment && <pre>{message.message_text}</pre>}{renderMessageContent(message)}{message.updated_at && message.updated_at !== message.created_at && <small className="student-collab__message-edited">Edited</small>}</>}
              </article>;
            })}
          </div>
          <div className="student-collab__composer">
            {attachmentMenuOpen && <div className="student-collab__attachment-menu" role="menu" aria-label="Share something">
              <div className="student-collab__attachment-menu-head"><strong>Share in channel</strong><button type="button" aria-label="Close share menu" onClick={() => setAttachmentMenuOpen(false)}><X size={16} aria-hidden /></button></div>
              {FILE_ACTIONS.slice(0, 4).map(action => <button type="button" role="menuitem" key={action.id} onClick={() => openFilePicker(action)}><span className="student-collab__menu-icon"><FileActionIcon action={action} /></span><span>{action.label}</span></button>)}
              <div className="student-collab__attachment-menu-divider" />
              <button type="button" role="menuitem" onClick={() => openStructured("CONTACT")}><span className="student-collab__menu-icon student-collab__menu-icon--contact"><Contact size={18} aria-hidden /></span><span>Contact</span></button>
              <button type="button" role="menuitem" onClick={() => openStructured("POLL")}><span className="student-collab__menu-icon student-collab__menu-icon--poll"><ListChecks size={18} aria-hidden /></span><span>Poll</span></button>
              <button type="button" role="menuitem" onClick={() => openStructured("EVENT")}><span className="student-collab__menu-icon student-collab__menu-icon--event"><CalendarDays size={18} aria-hidden /></span><span>Event</span></button>
              <button type="button" role="menuitem" onClick={() => openFilePicker(FILE_ACTIONS[4])}><span className="student-collab__menu-icon student-collab__menu-icon--sticker"><Sticker size={18} aria-hidden /></span><span>New sticker</span></button>
              <div className="student-collab__attachment-menu-divider" />
              <button type="button" role="menuitem" onClick={() => openStructured("CATALOGUE")}><span className="student-collab__menu-icon student-collab__menu-icon--catalogue"><Store size={18} aria-hidden /></span><span>Catalogue</span></button>
              <button type="button" role="menuitem" onClick={() => openStructured("QUICK_REPLY")}><span className="student-collab__menu-icon student-collab__menu-icon--quick"><Zap size={18} aria-hidden /></span><span>Quick replies</span></button>
            </div>}
            {structuredKind && <div className="student-collab__structured-composer">
              <div className="student-collab__structured-head"><strong>{structuredKind === "POLL" ? "Create poll" : structuredKind === "EVENT" ? "Create event" : structuredKind === "CATALOGUE" ? "Share catalogue item" : structuredKind === "QUICK_REPLY" ? "Quick replies" : "Share contact"}</strong><button type="button" aria-label="Close structured composer" onClick={() => setStructuredKind(null)}><X size={16} aria-hidden /></button></div>
              {structuredKind === "CONTACT" && <div className="student-collab__contact-picker">{members.length ? members.map(member => <button key={member.id} type="button" onClick={() => void sendContact(member)}><span><Contact size={16} aria-hidden /><strong>{member.name ?? member.full_name}</strong></span><small>{member.registration_number}</small></button>) : <p>No group contacts are available.</p>}</div>}
              {structuredKind === "QUICK_REPLY" && <div className="student-collab__quick-replies">{QUICK_REPLIES.map(reply => <button key={reply} type="button" onClick={() => void sendPayload({ message_text: reply, message_kind: "QUICK_REPLY", message_payload: { text: reply } }, "Quick reply sent.")}>{reply}</button>)}</div>}
              {structuredKind === "POLL" && <div className="student-collab__structured-fields"><label>Question<input value={structuredDraft.question} onChange={event => setDraftValue("question", event.target.value)} placeholder="What should we work on next?" /></label><label>Option 1<input value={structuredDraft.optionOne} onChange={event => setDraftValue("optionOne", event.target.value)} /></label><label>Option 2<input value={structuredDraft.optionTwo} onChange={event => setDraftValue("optionTwo", event.target.value)} /></label><label>Option 3 <span>(optional)</span><input value={structuredDraft.optionThree} onChange={event => setDraftValue("optionThree", event.target.value)} /></label><button type="button" onClick={() => void sendStructured()}>Send poll <Send size={14} aria-hidden /></button></div>}
              {structuredKind === "EVENT" && <div className="student-collab__structured-fields"><label>Event title<input value={structuredDraft.title} onChange={event => setDraftValue("title", event.target.value)} placeholder="Proposal review meeting" /></label><div className="student-collab__field-row"><label>Date<input type="date" value={structuredDraft.date} onChange={event => setDraftValue("date", event.target.value)} /></label><label>Time<input type="time" value={structuredDraft.time} onChange={event => setDraftValue("time", event.target.value)} /></label></div><label>Location<input value={structuredDraft.location} onChange={event => setDraftValue("location", event.target.value)} placeholder="Online or campus room" /></label><label>Details<textarea rows={2} value={structuredDraft.details} onChange={event => setDraftValue("details", event.target.value)} /></label><button type="button" onClick={() => void sendStructured()}>Send event <Send size={14} aria-hidden /></button></div>}
              {structuredKind === "CATALOGUE" && <div className="student-collab__structured-fields"><label>Item title<input value={structuredDraft.title} onChange={event => setDraftValue("title", event.target.value)} placeholder="Recommended research resource" /></label><label>Details<textarea rows={3} value={structuredDraft.details} onChange={event => setDraftValue("details", event.target.value)} placeholder="Describe the resource or item." /></label><label>Link <span>(optional)</span><input type="url" value={structuredDraft.link} onChange={event => setDraftValue("link", event.target.value)} placeholder="https://" /></label><button type="button" onClick={() => void sendStructured()}>Share item <Send size={14} aria-hidden /></button></div>}
            </div>}
            {emojiOpen && <div className="student-collab__emoji-panel" role="dialog" aria-label="Quick emoji"><button type="button" onClick={() => { setDraft(value => value + "👍"); setEmojiOpen(false); }}>👍</button><button type="button" onClick={() => { setDraft(value => value + "✅"); setEmojiOpen(false); }}>✅</button><button type="button" onClick={() => { setDraft(value => value + "🎉"); setEmojiOpen(false); }}>🎉</button><button type="button" onClick={() => { setDraft(value => value + "📌"); setEmojiOpen(false); }}>📌</button><button type="button" onClick={() => { setDraft(value => value + "💡"); setEmojiOpen(false); }}>💡</button></div>}
             {!supervisorMode && <div className="student-collab__sender-picker"><label htmlFor="student-collab-sender">Sending as</label><select id="student-collab-sender" value={selectedMemberId ?? ""} onChange={event => chooseMember(event.target.value ? Number(event.target.value) : null)} disabled={sending || recording}><option value="">Choose your name</option>{(channel?.members ?? []).map(member => <option key={member.id} value={member.id}>{member.name ?? member.full_name} · {member.registration_number}</option>)}</select><small>Choose your name, then verify its collaboration password.</small></div>}
            {!supervisorMode && selectedMemberId !== null && !selectedIdentity?.is_verified && <div id="student-collaboration-password" className="student-collab__identity-check" role="region" aria-label="Member identity verification">
              {selectedIdentity?.is_verified ? <p className="student-collab__identity-success">Verified as <strong>{selectedIdentity.name}</strong>. Messages are saved under this member until the session expires.</p> : <form onSubmit={event => { event.preventDefault(); void verifyMemberIdentity(); }}>
                <label htmlFor="student-collab-member-password">{selectedIdentity?.password_set ? "Enter collaboration identity password" : "Create collaboration identity password"}</label>
                <div className="student-collab__identity-fields"><input id="student-collab-member-password" type="password" autoComplete={selectedIdentity?.password_set ? "current-password" : "new-password"} value={identityPassword} onChange={event => setIdentityPassword(event.target.value)} placeholder="At least 8 characters" disabled={identityBusy} />{!selectedIdentity?.password_set && <input type="password" autoComplete="new-password" value={identityConfirmPassword} onChange={event => setIdentityConfirmPassword(event.target.value)} placeholder="Confirm password" disabled={identityBusy} />}<button type="submit" disabled={identityBusy}>{identityBusy ? "Checking…" : selectedIdentity?.password_set ? "Verify name" : "Save password"}</button></div>
                {!selectedIdentity?.password_set && <small className="student-collab__identity-hint">Use 8+ characters with uppercase, lowercase, number, and special character.</small>}
                <small className="student-collab__identity-hint">This is separate from the group sign-in password and is used only to identify you in this collaboration channel.</small>
                {selectedIdentity?.password_set && <button type="button" className="student-collab__identity-link" onClick={() => void forgotMemberIdentity()} disabled={identityBusy}>Forgot password? Request reset</button>}
              </form>}
              {identityError && <p className="student-collab__identity-error" role="alert">{identityError}</p>}
              {identityNotice && <p className="student-collab__identity-success" role="status">{identityNotice}</p>}
            </div>}
            <label className="student-collab__composer-label" htmlFor="student-collab-message">Message your collaboration channel</label>
            {pendingAttachment && <div className="student-collab__attachment-draft" role="region" aria-label="Attachment ready to send">
              <div className="student-collab__attachment-draft-preview">
                {(pendingAttachment.kind === "MEDIA" || pendingAttachment.kind === "STICKER") && pendingAttachment.file.type.startsWith("image/") && <img src={pendingAttachment.previewUrl} alt="Attachment preview" />}
                {pendingAttachment.kind === "MEDIA" && pendingAttachment.file.type.startsWith("video/") && <video controls preload="metadata" src={pendingAttachment.previewUrl} />}
                {pendingAttachment.kind === "AUDIO" && <audio controls preload="metadata" src={pendingAttachment.previewUrl} />}
                {!pendingAttachment.file.type.startsWith("image/") && !pendingAttachment.file.type.startsWith("video/") && !pendingAttachment.file.type.startsWith("audio/") && <FileText size={24} aria-hidden />}
              </div>
              <div className="student-collab__attachment-draft-info">
                <strong title={pendingAttachment.file.name}>{pendingAttachment.file.name}</strong>
                <small>{pendingAttachment.kind.toLowerCase()} · {fileSizeLabel(pendingAttachment.file.size)}</small>
                <span>{pendingAttachment.confirmed ? "Ready to send" : "Review and confirm this attachment"}</span>
              </div>
              <div className="student-collab__attachment-draft-actions">
                {!pendingAttachment.confirmed && <button type="button" className="student-collab__attachment-confirm" onClick={() => { setPendingAttachment(current => current ? { ...current, confirmed: true } : current); setError(""); }}>Confirm attachment</button>}
                <button type="button" className="student-collab__attachment-remove" aria-label="Remove attachment" onClick={() => { setPendingAttachment(null); setError(""); }}>Remove</button>
              </div>
            </div>}
            <textarea id="student-collab-message" rows={4} value={draft} disabled={recording} onChange={event => setDraft(event.target.value.slice(0, COLLABORATION_MESSAGE_LIMIT + 1))} placeholder="Write a message…" onKeyDown={event => { if (sendsOnEnter({ key: event.key, shiftKey: event.shiftKey, isComposing: event.nativeEvent.isComposing })) { event.preventDefault(); void send(); } }} />
            <input ref={fileInput} type="file" hidden accept={fileAction?.accept} capture={fileAction?.capture} onChange={(event: ChangeEvent<HTMLInputElement>) => { const file = event.target.files?.[0]; if (file && fileAction) { setPendingAttachment({ file, kind: fileAction.kind, previewUrl: URL.createObjectURL(file), confirmed: false }); setFileAction(null); setAttachmentMenuOpen(false); setError(""); setMessageStatus(""); } event.target.value = ""; }} />
             <div className="student-collab__composer-bottom"><div className="student-collab__composer-tools"><button type="button" className="student-collab__tool-button" aria-label="Share document, media, or more" aria-expanded={attachmentMenuOpen} disabled={recording || sending || (!supervisorMode && selectedMemberId === null)} onClick={() => { setAttachmentMenuOpen(value => !value); setEmojiOpen(false); }}><Paperclip size={20} aria-hidden /></button><button type="button" className="student-collab__tool-button" aria-label="Add emoji" aria-expanded={emojiOpen} disabled={recording || sending} onClick={() => { setEmojiOpen(value => !value); setAttachmentMenuOpen(false); }}><Smile size={20} aria-hidden /></button><button type="button" className={`student-collab__tool-button ${recording ? "student-collab__tool-button--recording" : ""}`} aria-label={recording ? "Stop voice recording" : "Record voice message"} title={recording ? "Stop voice recording" : "Record voice message"} aria-pressed={recording} disabled={sending || (!recording && Boolean(pendingAttachment)) || (!supervisorMode && selectedMemberId === null)} onClick={() => { if (recording) stopVoiceRecording(); else void startVoiceRecording(); }}>{recording ? <Square size={15} aria-hidden /> : <Mic size={17} aria-hidden />}</button>{recording && <span className="student-collab__voice-status" role="status">Recording {voiceDurationLabel(recordingSeconds)}</span>}<small>Enter to send · Shift + Enter for a new line · {draft.length}/{COLLABORATION_MESSAGE_LIMIT}{draft.length > COLLABORATION_MESSAGE_LIMIT ? " · Too long" : ""}</small></div><button type="button" className="student-collab__send-button" disabled={recording || sending || (!supervisorMode && selectedMemberId === null) || Boolean(pendingAttachment && !pendingAttachment.confirmed) || (!pendingAttachment && Boolean(validateCollaborationMessage(draft)))} onClick={() => void send()}><Send size={16} aria-hidden />{sending ? "Sending…" : pendingAttachment ? "Send attachment" : "Send"}</button></div>
          </div>
          {messageStatus && <p role="status">{messageStatus}</p>}{readError && <p role="status">{readError}</p>}
        </>}
      </>}
      {error && <div className="student-collab__error" role="alert">{error} <button type="button" onClick={() => { void refreshChannel(); void refreshMessages(); }}>Try again</button></div>}
    </div>}
  </section>;
}

export const StudentCollaborationChannel = CollaborationChannel;

function FileActionIcon({ action }: { action: FileAction }) {
  if (action.id === "document") return <FileText size={18} aria-hidden />;
  if (action.id === "media") return <ImageIcon size={18} aria-hidden />;
  if (action.id === "camera") return <Camera size={18} aria-hidden />;
  return <Headphones size={18} aria-hidden />;
}
