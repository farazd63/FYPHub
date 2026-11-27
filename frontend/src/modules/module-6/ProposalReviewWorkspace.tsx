import { useEffect, useMemo, useState, type FormEvent } from "react";
import "./module-6.css";
import { InteractiveProposalReview } from "./InteractiveProposalReview";

type Revision = {
  id: number;
  revision_code: string;
  team_id: number;
  proposal_key: string;
  source_submission_id: number;
  source_version: number;
  latest_submission_id: number | null;
  target_level: string;
  target_locator: Record<string, unknown>;
  title: string;
  description: string;
  expected_outcome: string | null;
  priority: string;
  due_at: string | null;
  is_overdue: boolean;
  status: string;
  student_explanation: string | null;
  assessment: Assessment | null;
  created_at: string;
  messages?: Message[];
};

type Assessment = {
  id: number;
  classification: string;
  requirements: Array<{ requirement: string; status: string; evidence?: string; location?: string | null }>;
  evidence: Array<{ requirement: string; status: string; evidence?: string; location?: string | null }>;
  explanation: string;
  manual_verification_required: boolean;
  source: string;
  model?: string | null;
  created_at: string;
};

type Message = { id: number; sender_id: number; sender_name: string; body: string; created_at: string };
type Proposal = { id: number; proposal_key: string; title: string; proposal_type: string; version: number; filename: string; created_at?: string; text?: string };
type Group = { id: number; name: string; group_number: number | null; members: Array<{ id: number; full_name: string; registration_number: string; email: string }>; proposal: Proposal | null; revision_counts: { total: number; open: number; awaiting_verification: number; accepted: number }; revision_requests: Revision[] };
type Feedback = { id: number; submission_id: number; title: string; content: string; feedback_level: string; feedback_type: string; suggested_text: string | null; selected_text: string | null; created_at: string };
type StudentPayload = { team: Group | null; proposal: Proposal | null; feedback: Feedback[]; revision_requests: Revision[] };

function readError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  }
  return fallback;
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: "include", ...init });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(readError(payload, "The proposal review request failed."));
  return payload as T;
}

const prettyStatus = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
const statusClass = (value: string) => value.toLowerCase().replaceAll("_", "-");

export function ProposalReviewWorkspace({ api, role }: { api: string; role: "supervisor" | "student" }) {
  const [groups, setGroups] = useState<Group[]>([]);
  const [student, setStudent] = useState<StudentPayload | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Revision | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [feedbackForm, setFeedbackForm] = useState({ title: "", content: "", level: "FULL_PROPOSAL", type: "GENERAL_COMMENT", suggested: "" });
  const [revisionForm, setRevisionForm] = useState({ title: "", description: "", expected: "", priority: "MEDIUM", level: "FULL_PROPOSAL" });
  const [message, setMessage] = useState("");
  const [studentExplanation, setStudentExplanation] = useState("");
  const [studentFile, setStudentFile] = useState<File | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);

  const selectedGroup = useMemo(() => groups.find((group) => group.id === selectedGroupId) ?? null, [groups, selectedGroupId]);
  const visibleRevisions = role === "student" ? (student?.revision_requests ?? []) : (selectedGroup?.revision_requests ?? []);
  const selectedProposal = role === "student" ? student?.proposal ?? null : selectedGroup?.proposal ?? null;

  const load = async (preferredRevision?: number | null) => {
    setLoading(true);
    setError("");
    try {
      if (role === "supervisor") {
        const rows = await jsonRequest<Group[]>(`${api}/api/v1/supervisor-review/supervisor/groups`);
        setGroups(rows);
        const groupId = selectedGroupId && rows.some((item) => item.id === selectedGroupId) ? selectedGroupId : rows[0]?.id ?? null;
        setSelectedGroupId(groupId);
        const group = rows.find((item) => item.id === groupId);
        const revisionId = preferredRevision ?? selectedRevisionId ?? group?.revision_requests[0]?.id ?? null;
        setSelectedRevisionId(revisionId);
        if (revisionId) setDetail(await jsonRequest<Revision>(`${api}/api/v1/supervisor-review/revision-requests/${revisionId}`));
      } else {
        const payload = await jsonRequest<StudentPayload>(`${api}/api/v1/supervisor-review/student`);
        setStudent(payload);
        const revisionId = preferredRevision ?? selectedRevisionId ?? payload.revision_requests[0]?.id ?? null;
        setSelectedRevisionId(revisionId);
        if (revisionId) setDetail(await jsonRequest<Revision>(`${api}/api/v1/supervisor-review/revision-requests/${revisionId}`));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The proposal review workspace could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const revision = Number(new URLSearchParams(window.location.search).get("revision")) || null;
    const timer = window.setTimeout(() => {
      void load(revision);
    }, 0);
    return () => window.clearTimeout(timer);
    // This workspace owns its initial server synchronization.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, role]);

  const selectGroup = (group: Group) => {
    setSelectedGroupId(group.id);
    const revisionId = group.revision_requests[0]?.id ?? null;
    setSelectedRevisionId(revisionId);
    setDetail(null);
    if (revisionId) void openRevision(revisionId);
  };

  const openRevision = async (revisionId: number) => {
    setSelectedRevisionId(revisionId);
    setError("");
    try { setDetail(await jsonRequest<Revision>(`${api}/api/v1/supervisor-review/revision-requests/${revisionId}`)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The revision request could not be loaded."); }
  };

  const submitFeedback = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedProposal) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await jsonRequest<Feedback>(`${api}/api/v1/supervisor-review/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ submission_id: selectedProposal.id, feedback_level: feedbackForm.level, feedback_type: feedbackForm.type, title: feedbackForm.title, content: feedbackForm.content, suggested_text: feedbackForm.suggested || null }) });
      setFeedbackForm({ title: "", content: "", level: "FULL_PROPOSAL", type: "GENERAL_COMMENT", suggested: "" });
      setNotice("Feedback published for the student group.");
      await load(selectedRevisionId);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Feedback could not be published."); }
    finally { setBusy(false); }
  };

  const submitRevisionRequest = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedProposal) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await jsonRequest<Revision>(`${api}/api/v1/supervisor-review/revision-requests`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_submission_id: selectedProposal.id, target_level: revisionForm.level, title: revisionForm.title, description: revisionForm.description, expected_outcome: revisionForm.expected || null, priority: revisionForm.priority }) });
      setRevisionForm({ title: "", description: "", expected: "", priority: "MEDIUM", level: "FULL_PROPOSAL" });
      setSelectedRevisionId(created.id); setDetail(created); setNotice("Formal revision request sent to the group."); await load(created.id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The revision request could not be created."); }
    finally { setBusy(false); }
  };

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();
    if (!detail || !message.trim()) return;
    setBusy(true); setError("");
    try { await jsonRequest(`${api}/api/v1/supervisor-review/revision-requests/${detail.id}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body: message.trim() }) }); setMessage(""); await openRevision(detail.id); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The discussion message could not be sent."); }
    finally { setBusy(false); }
  };

  const assess = async () => {
    if (!detail) return;
    setBusy(true); setError("");
    try { await jsonRequest(`${api}/api/v1/supervisor-review/revision-requests/${detail.id}/assess`, { method: "POST" }); await openRevision(detail.id); setNotice("AI assessment completed. The supervisor still makes the final decision."); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The revision could not be assessed."); }
    finally { setBusy(false); }
  };

  const decide = async (decision: "ACCEPTED" | "CHANGES_REQUIRED" | "WITHDRAWN" | "REOPENED") => {
    if (!detail) return;
    const reason = decision === "ACCEPTED" ? "" : window.prompt("Reason for this decision:") ?? "";
    if (decision !== "ACCEPTED" && !reason.trim()) return;
    setBusy(true); setError("");
    try { await jsonRequest(`${api}/api/v1/supervisor-review/revision-requests/${detail.id}/decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, reason: reason || null, classification: detail.assessment?.classification ?? null }) }); await load(detail.id); setNotice(`Revision marked ${prettyStatus(decision).toLowerCase()}.`); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The revision decision could not be saved."); }
    finally { setBusy(false); }
  };

  const uploadRevision = async (event: FormEvent) => {
    event.preventDefault();
    if (!detail || !selectedProposal || !studentFile || !studentExplanation.trim()) { setError("Choose a revised proposal and explain the changes before submitting."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const body = new FormData();
      body.append("proposal_type", selectedProposal.proposal_type);
      body.append("title", selectedProposal.title);
      body.append("action", "submit");
      body.append("proposal_key", selectedProposal.proposal_key);
      body.append("proposal_file", studentFile);
      const submission = await jsonRequest<{ submission: { id: number } }>(`${api}/api/v1/proposal-compliance/submissions`, { method: "POST", body });
      await jsonRequest(`${api}/api/v1/supervisor-review/revision-requests/${detail.id}/submit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ submission_id: submission.submission.id, explanation: studentExplanation.trim() }) });
      setStudentFile(null); setStudentExplanation(""); setNotice("Revised proposal submitted for supervisor review."); await load(detail.id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The revised proposal could not be submitted."); }
    finally { setBusy(false); }
  };

  if (loading && !groups.length && !student) return <section className="module6-workspace"><div className="module6-empty">Loading proposal review workspace…</div></section>;
  const feedback = role === "student" ? student?.feedback ?? [] : [];
  return <section className="module6-workspace" aria-labelledby="module6-heading">
    <div className="module6-heading"><div><p className="module6-eyebrow">Module 6 · Supervisor Proposal Review</p><h1 id="module6-heading">{role === "supervisor" ? "Proposal review dashboard" : "Supervisor feedback & revisions"}</h1><p>{role === "supervisor" ? "Review assigned proposals, publish structured feedback, and verify revisions with AI-assisted evidence." : "Review supervisor feedback, discuss each required change, and submit revised proposal versions."}</p></div><button type="button" className="module6-button module6-button--quiet" onClick={() => void load(selectedRevisionId)}>Refresh</button></div>
    {notice && <p className="module6-alert module6-alert--success" role="status">{notice}</p>}{error && <p className="module6-alert module6-alert--error" role="alert">{error}</p>}
    {role === "supervisor" ? <div className="module6-layout">
      <aside className="module6-panel module6-group-list"><div className="module6-panel-title"><span>Assigned groups</span><strong>{groups.length}</strong></div>{groups.length ? groups.map((group) => <button type="button" key={group.id} className={`module6-group-option${group.id === selectedGroupId ? " module6-group-option--selected" : ""}`} onClick={() => selectGroup(group)}><strong>{group.name}</strong><span>{group.proposal ? `${group.proposal.title} · v${group.proposal.version}` : "No submitted proposal"}</span><small>{group.revision_counts.open} open revision{group.revision_counts.open === 1 ? "" : "s"}</small></button>) : <p className="module6-muted">No active supervisor assignments.</p>}</aside>
      <div className="module6-main">{selectedGroup ? <><ProposalCard proposal={selectedGroup.proposal} api={api} onOpenReview={() => setReviewOpen(true)} /><div className="module6-form-grid"><form className="module6-panel module6-form" onSubmit={(event) => void submitFeedback(event)}><div className="module6-panel-title"><span>Publish feedback</span><small>Saved against the selected version</small></div><label>Title<input required value={feedbackForm.title} onChange={(event) => setFeedbackForm({ ...feedbackForm, title: event.target.value })} /></label><div className="module6-inline-fields"><label>Level<select value={feedbackForm.level} onChange={(event) => setFeedbackForm({ ...feedbackForm, level: event.target.value })}><option value="FULL_PROPOSAL">Full proposal</option><option value="SECTION">Section</option><option value="MODULE">Module</option><option value="PARAGRAPH">Paragraph</option></select></label><label>Type<select value={feedbackForm.type} onChange={(event) => setFeedbackForm({ ...feedbackForm, type: event.target.value })}><option value="GENERAL_COMMENT">General comment</option><option value="EDITING_SUGGESTION">Editing suggestion</option><option value="CLARIFICATION_REQUEST">Clarification request</option></select></label></div><label>Feedback<textarea required rows={4} value={feedbackForm.content} onChange={(event) => setFeedbackForm({ ...feedbackForm, content: event.target.value })} /></label><label>Suggested replacement text <span className="module6-muted">(optional)</span><textarea rows={3} value={feedbackForm.suggested} onChange={(event) => setFeedbackForm({ ...feedbackForm, suggested: event.target.value })} /></label><button type="submit" className="module6-button" disabled={busy || !selectedGroup.proposal}>Publish feedback</button></form><form className="module6-panel module6-form" onSubmit={(event) => void submitRevisionRequest(event)}><div className="module6-panel-title"><span>Create formal revision</span><small>Mandatory changes are tracked independently</small></div><label>Revision title<input required value={revisionForm.title} onChange={(event) => setRevisionForm({ ...revisionForm, title: event.target.value })} /></label><label>Instructions<textarea required rows={4} value={revisionForm.description} onChange={(event) => setRevisionForm({ ...revisionForm, description: event.target.value })} /></label><label>Expected outcome<textarea rows={3} value={revisionForm.expected} onChange={(event) => setRevisionForm({ ...revisionForm, expected: event.target.value })} /></label><div className="module6-inline-fields"><label>Priority<select value={revisionForm.priority} onChange={(event) => setRevisionForm({ ...revisionForm, priority: event.target.value })}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label><label>Target<select value={revisionForm.level} onChange={(event) => setRevisionForm({ ...revisionForm, level: event.target.value })}><option value="FULL_PROPOSAL">Full proposal</option><option value="SECTION">Section</option><option value="MODULE">Module</option><option value="PARAGRAPH">Paragraph</option></select></label></div><button type="submit" className="module6-button" disabled={busy || !selectedGroup.proposal}>Send revision request</button></form></div><RevisionList revisions={visibleRevisions} selectedId={selectedRevisionId} onSelect={openRevision} />{detail && <RevisionDetail detail={detail} role={role} busy={busy} message={message} setMessage={setMessage} onMessage={sendMessage} onAssess={assess} onDecision={decide} />}</> : <div className="module6-panel module6-empty">Select an assigned group to begin reviewing.</div>}</div>
    </div> : <div className="module6-main module6-student-main"><ProposalCard proposal={student?.proposal ?? null} api={api} onOpenReview={() => setReviewOpen(true)} /><section className="module6-panel"><div className="module6-panel-title"><span>Published feedback</span><small>{feedback.length} item{feedback.length === 1 ? "" : "s"}</small></div>{feedback.length ? <div className="module6-feedback-list">{feedback.map((item) => <article key={item.id}><div><strong>{item.title}</strong><span className="module6-status module6-status--neutral">{prettyStatus(item.feedback_level)}</span></div><p>{item.content}</p>{item.suggested_text && <blockquote>{item.suggested_text}</blockquote>}<small>{new Date(item.created_at).toLocaleString()}</small></article>)}</div> : <p className="module6-muted">No published supervisor feedback yet.</p>}</section><RevisionList revisions={visibleRevisions} selectedId={selectedRevisionId} onSelect={openRevision} />{detail && <RevisionDetail detail={detail} role={role} busy={busy} message={message} setMessage={setMessage} onMessage={sendMessage} onAssess={assess} onDecision={decide} studentFile={studentFile} setStudentFile={setStudentFile} studentExplanation={studentExplanation} setStudentExplanation={setStudentExplanation} onUpload={uploadRevision} />}</div>}
    {reviewOpen && selectedProposal && <InteractiveProposalReview api={api} submissionId={selectedProposal.id} title={selectedProposal.title} version={selectedProposal.version} role={role} onClose={() => setReviewOpen(false)} />}
  </section>;
}

function ProposalCard({ proposal, api, onOpenReview }: { proposal: Proposal | null; api: string; onOpenReview?: () => void }) {
  if (!proposal) return <section className="module6-panel module6-empty">No submitted proposal is available for review.</section>;
  return <section className="module6-panel module6-proposal-card"><div><p className="module6-eyebrow">Current proposal</p><h2>{proposal.title}</h2><p>{proposal.proposal_type} proposal · Version {proposal.version} · {proposal.filename}</p></div><div className="module6-proposal-actions"><button type="button" className="module6-button" onClick={onOpenReview}>Open review workspace</button><a className="module6-button module6-button--quiet" href={`${api}/api/v1/proposal-compliance/reports/${proposal.id}/original`} target="_blank" rel="noreferrer">Download original</a></div></section>;
}

function RevisionList({ revisions, selectedId, onSelect }: { revisions: Revision[]; selectedId: number | null; onSelect: (id: number) => void }) {
  return <section className="module6-panel"><div className="module6-panel-title"><span>Formal revision requests</span><small>{revisions.length} total</small></div>{revisions.length ? <div className="module6-revision-list">{revisions.map((item) => <button type="button" key={item.id} className={`module6-revision-row${item.id === selectedId ? " module6-revision-row--selected" : ""}`} onClick={() => onSelect(item.id)}><span><strong>{item.revision_code}</strong><b>{item.title}</b><small>v{item.source_version} source · {item.target_level}</small></span><span className={`module6-status module6-status--${statusClass(item.status)}`}>{prettyStatus(item.status)}{item.is_overdue ? " · Overdue" : ""}</span></button>)}</div> : <p className="module6-muted">No formal revision requests have been created.</p>}</section>;
}

function RevisionDetail({ detail, role, busy, message, setMessage, onMessage, onAssess, onDecision, studentFile, setStudentFile, studentExplanation, setStudentExplanation, onUpload }: { detail: Revision; role: "supervisor" | "student"; busy: boolean; message: string; setMessage: (value: string) => void; onMessage: (event: FormEvent) => void; onAssess: () => void; onDecision: (decision: "ACCEPTED" | "CHANGES_REQUIRED" | "WITHDRAWN" | "REOPENED") => void; studentFile?: File | null; setStudentFile?: (value: File | null) => void; studentExplanation?: string; setStudentExplanation?: (value: string) => void; onUpload?: (event: FormEvent) => void }) {
  return <section className="module6-panel module6-detail"><div className="module6-detail-head"><div><p className="module6-eyebrow">{detail.revision_code}</p><h2>{detail.title}</h2><p>{detail.description}</p></div><span className={`module6-status module6-status--${statusClass(detail.status)}`}>{prettyStatus(detail.status)}</span></div>{detail.expected_outcome && <div className="module6-evidence-box"><strong>Expected outcome</strong><p>{detail.expected_outcome}</p></div>}{detail.assessment && <div className="module6-assessment"><div className="module6-panel-title"><span>AI revision assessment</span><span className={`module6-status module6-status--${statusClass(detail.assessment.classification)}`}>{prettyStatus(detail.assessment.classification)}</span></div><p>{detail.assessment.explanation}</p><div className="module6-requirements">{detail.assessment.requirements.map((item, index) => <div key={`${item.requirement}-${index}`}><span className={`module6-status module6-status--${statusClass(item.status)}`}>{prettyStatus(item.status)}</span><p><strong>{item.requirement}</strong>{item.evidence && <small>{item.evidence}</small>}</p></div>)}</div><small className="module6-muted">Source: {detail.assessment.source}. AI output is advisory; supervisor verification is required.</small></div>}{role === "student" && detail.status !== "ACCEPTED" && detail.status !== "WITHDRAWN" && onUpload && setStudentFile && setStudentExplanation && <form className="module6-submit-form" onSubmit={onUpload}><h3>Submit a revised proposal</h3><p>Upload a new proposal version, then explain how this request was addressed.</p><input type="file" accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setStudentFile(event.target.files?.[0] ?? null)} /><textarea required rows={4} placeholder="Explain the changes made" value={studentExplanation ?? ""} onChange={(event) => setStudentExplanation(event.target.value)} /><button type="submit" className="module6-button" disabled={busy || !studentFile}>Submit revised proposal</button></form>}{role === "supervisor" && <div className="module6-detail-actions"><button type="button" className="module6-button module6-button--quiet" onClick={onAssess} disabled={busy || !detail.latest_submission_id}>Run AI assessment</button><button type="button" className="module6-button module6-button--success" onClick={() => onDecision("ACCEPTED")} disabled={busy}>Accept revision</button><button type="button" className="module6-button module6-button--warning" onClick={() => onDecision("CHANGES_REQUIRED")} disabled={busy}>Request more changes</button>{detail.status === "ACCEPTED" && <button type="button" className="module6-button module6-button--quiet" onClick={() => onDecision("REOPENED")} disabled={busy}>Reopen</button>}</div>}<div className="module6-discussion"><div className="module6-panel-title"><span>Revision discussion</span><small>{detail.messages?.length ?? 0} messages</small></div><div className="module6-messages">{detail.messages?.length ? detail.messages.map((item) => <article key={item.id}><strong>{item.sender_name}</strong><p>{item.body}</p><small>{new Date(item.created_at).toLocaleString()}</small></article>) : <p className="module6-muted">No discussion messages yet.</p>}</div><form className="module6-message-form" onSubmit={onMessage}><textarea required rows={3} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask a question or clarify this revision" /><button type="submit" className="module6-button" disabled={busy || !message.trim()}>Send message</button></form></div></section>;
}
