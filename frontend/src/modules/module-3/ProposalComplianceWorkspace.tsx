import { useEffect, useState, type FormEvent } from "react";
import "./module-3.css";
import { ProposalVersionComparison } from "./ProposalVersionComparison";

type Submission = { id: number; proposal_key: string; title: string; proposal_type: string; version: number; status: string; processing_status: string; filename: string; page_count: number; score: number | null; report_status: string | null; report_available: boolean; created_at: string };
type Summary = { score: number; status: string; totalIssues: number; deterministicSummary?: string; metrics: { passed: number; failed: number; partial: number; total: number } };
type ReviewCheck = { id: string; name: string; status: string; expected?: unknown; actual?: unknown; difference?: unknown; evidence?: string; location?: unknown };
type Category = { name: string; status: string; detail: string; checks?: ReviewCheck[] };
type Section = { name: string; check1: string; check2: string };
type Violation = { id: string; severity: string; title: string; location: string; requirement: unknown; detected: unknown; difference: unknown; evidence: string; affectedArea: string };
type ChangeSummary = { source: string; model: string; fromVersion: number; toVersion: number; summary: string; changedSections: string[]; advisory: boolean };
type FriendlyRow = { id: string; area: string; requirement: string; studentDocument: string; difference: string; statusCode: string; status: string; priority: string; problem: string; correction: string; evidence: string; affectedPages?: number[] };
type Report = { reportSummary: Summary; categories: Category[]; sectionCompliance: Section[]; violations: Violation[]; missingSections: { issue: string; details: string }[]; comparisonRows?: FriendlyRow[]; whatToFixFirst?: FriendlyRow[]; passedChecks?: FriendlyRow[]; aiSummary?: string | null; aiSummaryStatus?: string; student?: { name: string; email?: string | null; registrationNumber?: string | null }; academicConsistency?: { name: string; status: string; evidence: string }[]; finalResults: { totalChecks: number; passed: number; failed: number; partial: number; totalViolations: number; severityBreakdown: { major: number; minor: number; info: number } }; document: { filename: string; pageCount: number; previewText: string; selectedPage: number }; proposal: { id: number; proposalKey?: string; title: string; type: string; version: number }; versionHistory?: { version: number; filename: string; score: number | null; changeSummary?: ChangeSummary }[] };

const statusClass = (status: string) => status.toLowerCase().replaceAll(" ", "-").replaceAll("_", "-");

function Pill({ status }: { status: string }) { return <span className={`module3-status-pill module3-status-pill--${statusClass(status)}`}>{status}</span>; }

export function ProposalComplianceWorkspace({ api, reviewerMode = false }: { api: string; reviewerMode?: boolean }) {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [proposalType, setProposalType] = useState<"SHORT" | "LONG">("SHORT");
  const [title, setTitle] = useState("");
  const [resubmitKey, setResubmitKey] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadReportSummary = async (id: number) => {
    const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${id}/summary`, { method: "POST", credentials: "include" });
    if (!response.ok) return;
    const next = await response.json() as Report;
    setReport((current) => current?.proposal.id === id ? next : current);
  };

  const openReport = async (id: number) => {
    setSelectedId(id); setError("");
    const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${id}`, { credentials: "include" });
    if (!response.ok) { setError("The compliance report is not available yet."); return; }
    setReport(await response.json() as Report); setShowUpload(false); void loadReportSummary(id);
  };

  const load = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/${reviewerMode ? "reports" : "submissions/mine"}`, { credentials: "include" });
      if (!response.ok) throw new Error("Proposal history could not be loaded.");
      const rows = await response.json() as Submission[];
      setSubmissions(rows);
      if (!selectedId && rows[0]?.report_available) await openReport(rows[0].id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Proposal history could not be loaded."); } finally { setLoading(false); }
  };
  // The initial request synchronizes this workspace with the server-owned submission list.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [api, reviewerMode]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) { setError("Choose a PDF, DOCX, or TXT proposal."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const action = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.dataset.action || "submit";
      const body = new FormData();
      body.append("proposal_type", proposalType); body.append("title", title || file.name.replace(/\.[^.]+$/, "")); body.append("action", action); body.append("proposal_file", file);
      if (resubmitKey) body.append("proposal_key", resubmitKey);
      const response = await fetch(`${api}/api/v1/proposal-compliance/submissions`, { method: "POST", credentials: "include", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Proposal compliance processing failed.");
      setReport(payload.report as Report | null); setSelectedId((payload.submission as Submission).id);
      setMessage(action === "draft" ? "Proposal saved as a draft. Submit it when it is ready for compliance checking." : "Proposal processed against the active university baseline.");
      setFile(null); setTitle(""); setResubmitKey(null); setShowUpload(false); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Proposal upload failed."); } finally { setBusy(false); }
  };

  const submitDraft = async (id: number) => {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/submissions/${id}/submit`, { method: "POST", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Draft submission failed.");
      setReport(payload.report as Report); setSelectedId(id); setMessage("Draft submitted and checked against the active university baseline."); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Draft submission failed."); } finally { setBusy(false); }
  };

  const withdraw = async (id: number) => {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/submissions/${id}/withdraw`, { method: "POST", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Proposal withdrawal failed.");
      setMessage("Proposal withdrawn. Its version history remains available."); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Proposal withdrawal failed."); } finally { setBusy(false); }
  };

  const reviewStatus = async (status: "APPROVED" | "CHANGES_REQUESTED" | "REJECTED") => {
    if (!selectedId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/submissions/${selectedId}/status`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Proposal status could not be updated.");
      setMessage(`Proposal marked ${status.toLowerCase().replaceAll("_", " ")}.`); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Proposal status could not be updated."); } finally { setBusy(false); }
  };

  const startResubmit = (item: Submission) => {
    setProposalType(item.proposal_type as "SHORT" | "LONG"); setTitle(item.title); setResubmitKey(item.proposal_key); setReport(null); setShowUpload(true); setMessage(`Resubmission started for ${item.title}. Choose the new document file.`); setError("");
  };

  const rerun = async () => {
    if (!selectedId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${selectedId}/run`, { method: "POST", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Compliance re-run failed.");
      setReport(payload as Report); setMessage("Compliance report re-run against the current active baseline."); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Compliance re-run failed."); } finally { setBusy(false); }
  };

  const download = () => { if (selectedId) window.open(`${api}/api/v1/proposal-compliance/reports/${selectedId}/pdf`, "_blank", "noopener,noreferrer"); };
  const original = () => { if (selectedId) window.open(`${api}/api/v1/proposal-compliance/reports/${selectedId}/original`, "_blank", "noopener,noreferrer"); };
  const annotated = () => { if (selectedId) window.open(`${api}/api/v1/proposal-compliance/reports/${selectedId}/annotated`, "_blank", "noopener,noreferrer"); };
  const newCheck = () => { setShowUpload(true); setReport(null); setResubmitKey(null); setMessage(""); };

  if (loading && !report) return <section className="module3-workspace"><div className="module3-loading">Loading proposal compliance workspace...</div></section>;
  return <section className="module3-workspace" aria-labelledby="module3-compliance-heading">
    <div className="module3-page-heading module3-report-heading"><div><p className="module3-eyebrow">Proposal Compliance Review</p><h1 id="module3-compliance-heading">Compliance Report</h1><p>Detailed analysis of your proposal against the active university template.</p></div><div className="module3-report-actions"><button type="button" onClick={newCheck} className="module3-secondary-button">New Check</button>{report && <><button type="button" onClick={() => void rerun()} className="module3-primary-button" disabled={busy}>Re-run Check</button><button type="button" onClick={download} className="module3-secondary-button">Download PDF</button><button type="button" onClick={annotated} className="module3-secondary-button">View Annotated PDF</button><button type="button" onClick={original} className="module3-secondary-button">View Original</button>{reviewerMode && <><button type="button" onClick={() => void reviewStatus("APPROVED")} className="module3-secondary-button" disabled={busy}>Approve</button><button type="button" onClick={() => void reviewStatus("CHANGES_REQUESTED")} className="module3-secondary-button" disabled={busy}>Request changes</button><button type="button" onClick={() => void reviewStatus("REJECTED")} className="module3-secondary-button" disabled={busy}>Reject</button></>}</>}</div></div>
    {message && <p className="module3-alert module3-alert--success" role="status">{message}</p>}{error && <p className="module3-alert module3-alert--error" role="alert">{error}</p>}
    {showUpload || !report ? <form className="module3-panel module3-proposal-upload" onSubmit={(event) => void submit(event)}><div className="module3-panel-heading"><div><span className="module3-kicker">{resubmitKey ? "Resubmit version" : "New check"}</span><h2>{resubmitKey ? "Resubmit Your Proposal" : "Submit Your Proposal"}</h2></div><span className="module3-live-dot">Template-aware</span></div><p className="module3-muted">Upload your existing proposal for compliance checking. The active university baseline is used and every uploaded version is preserved.</p><div className="module3-form-grid"><label>Proposal title<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Enter proposal title" /></label><label>Proposal type<select value={proposalType} onChange={(event) => setProposalType(event.target.value as "SHORT" | "LONG")}><option value="SHORT">Short proposal</option><option value="LONG">Long proposal</option></select></label></div><label className="module3-file-drop">Proposal document<input type="file" accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file && <strong>{file.name}</strong>}</label><div className="module3-form-actions"><button type="submit" data-action="draft" className="module3-secondary-button" disabled={busy}>Save Draft</button><button type="submit" data-action="submit" className="module3-primary-button" disabled={busy}>{busy ? "Processing proposal..." : "Submit & run compliance check"}</button></div>{submissions.some((item) => item.status === "DRAFT") && <div className="module3-draft-list"><strong>Saved drafts</strong>{submissions.filter((item) => item.status === "DRAFT").map((item) => <div key={item.id}><span>v{item.version} - {item.title}</span><button type="button" className="module3-secondary-button" onClick={() => void submitDraft(item.id)} disabled={busy}>Submit draft</button><button type="button" className="module3-secondary-button" onClick={() => void withdraw(item.id)} disabled={busy}>Withdraw</button></div>)}</div>}</form> : <ReportView api={api} report={report} submissions={submissions} onSelect={(id) => void openReport(id)} onDownload={download} onOriginal={original} onAnnotated={annotated} onRerun={() => void rerun()} onResubmit={startResubmit} onWithdraw={withdraw} busy={busy} />}
  </section>;
}
function FriendlyRowsTable({ rows }: { rows: FriendlyRow[] }) {
  if (!rows.length) return <p className="module3-empty">No checks are available for this report.</p>;
  return <div className="module3-friendly-table-wrap"><table className="module3-friendly-table"><thead><tr><th>Area</th><th>University requirement</th><th>Student document</th><th>Difference</th><th>Result</th><th>Correction</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td data-label="Area"><strong>{row.area}</strong><small>{row.problem}</small></td><td data-label="University requirement">{row.requirement}</td><td data-label="Student document">{row.studentDocument}</td><td data-label="Difference">{row.difference}</td><td data-label="Result"><Pill status={row.status} /></td><td data-label="Correction">{row.correction}</td></tr>)}</tbody></table></div>;
}
function ReportView({ api, report, submissions, onSelect, onDownload, onOriginal, onAnnotated, onRerun, onResubmit, onWithdraw, busy }: { api: string; report: Report; submissions: Submission[]; onSelect: (id: number) => void; onDownload: () => void; onOriginal: () => void; onAnnotated: () => void; onRerun: () => void; onResubmit: (item: Submission) => void; onWithdraw: (id: number) => void; busy: boolean }) {
  const summary = report.reportSummary;
  const rows = report.comparisonRows ?? [];
  const priorityRows = report.whatToFixFirst ?? rows.filter((row) => row.statusCode !== "PASS");
  const passedRows = report.passedChecks ?? rows.filter((row) => row.statusCode === "PASS");
  const proposalHistory = report.proposal.proposalKey
    ? submissions.filter((item) => item.proposal_key === report.proposal.proposalKey)
    : submissions.filter((item) => item.id === report.proposal.id);
  const student = report.student?.name ?? "Current student";
  const summaryText = report.aiSummary || summary.deterministicSummary || "Review the checks below and correct the highest-priority items first.";
  return <div className="module3-friendly-report">
    <section className="module3-panel module3-friendly-report__header">
      <div><span className="module3-kicker">Proposal Compliance Report</span><h2>{report.proposal.title}</h2><div className="module3-report-identity"><span><b>Student</b>{student}</span><span><b>Document</b>{report.document.filename}</span><span><b>Version</b>v{report.proposal.version}</span></div></div>
      <div className="module3-friendly-score"><strong>{summary.score}%</strong><Pill status={summary.status} /><small>{summary.metrics.passed} of {summary.metrics.total} checks passed</small></div>
    </section>

    <section className="module3-panel module3-friendly-summary"><div><span className="module3-kicker">Simple AI summary</span><h2>What this report means</h2></div><p>{summaryText}</p>{report.aiSummaryStatus && <small className="module3-muted">{report.aiSummaryStatus === "COMPLETED" ? "Generated from verified report findings." : "Showing the deterministic report explanation."}</small>}</section>

    <section className="module3-report-stats" aria-label="Compliance totals"><div><strong>{summary.metrics.passed}</strong><span>checks passed</span></div><div><strong>{summary.metrics.failed}</strong><span>failed</span></div><div><strong>{summary.metrics.partial}</strong><span>require verification</span></div><div><strong>{summary.metrics.total}</strong><span>total checks</span></div></section>

    <section className="module3-panel"><div className="module3-section-heading"><div><span className="module3-kicker">Priority actions</span><h2 className="module3-section-title">What to Fix First</h2></div><span className="module3-muted">Start with high-priority corrections</span></div>{priorityRows.length ? <div className="module3-priority-list">{priorityRows.map((row) => <article className="module3-priority-row" key={`priority-${row.id}`}><Pill status={row.priority} /><div><strong>{row.problem}</strong><p>{row.correction}</p></div><Pill status={row.status} /></article>)}</div> : <p className="module3-success-text">No corrections are required for the configured checks.</p>}</section>

    <section className="module3-panel"><div className="module3-section-heading"><div><span className="module3-kicker">Verified comparison</span><h2 className="module3-section-title">University Template vs Student Document</h2></div><span className="module3-muted">One row per requirement</span></div><FriendlyRowsTable rows={rows} /></section>

    <section className="module3-panel"><div className="module3-section-heading"><div><span className="module3-kicker">Successful checks</span><h2 className="module3-section-title">Passed Checks</h2></div></div>{passedRows.length ? <div className="module3-passed-list">{passedRows.map((row) => <div key={`passed-${row.id}`}><span aria-hidden="true">✓</span><strong>{row.problem}</strong><small>{row.requirement}</small></div>)}</div> : <p className="module3-muted">No checks passed yet.</p>}</section>

    <details className="module3-panel module3-evidence-panel"><summary>View Evidence <span>Administrator details</span></summary><div className="module3-evidence-list">{rows.filter((row) => row.statusCode !== "PASS").map((row) => <article key={`evidence-${row.id}`}><strong>{row.problem}</strong><p>{row.evidence}</p>{row.affectedPages?.length ? <small>Affected pages: {row.affectedPages.join(", ")}</small> : null}</article>)}</div></details>

    <section className="module3-panel module3-final-panel"><div className="module3-section-heading"><div><span className="module3-kicker">Report actions</span><h2 className="module3-section-title">Review and continue</h2></div></div><div className="module3-form-actions"><button className="module3-primary-button" type="button" onClick={onDownload}>Download report PDF</button><button className="module3-secondary-button" type="button" onClick={onOriginal}>View original</button><button className="module3-secondary-button" type="button" onClick={onAnnotated}>View annotated PDF</button><button className="module3-secondary-button" type="button" onClick={onRerun} disabled={busy}>Re-run check</button></div></section>

    {proposalHistory.length > 0 && <section className="module3-panel module3-history-panel"><div className="module3-panel-heading"><div><span className="module3-kicker">Audit trail</span><h2 className="module3-section-title">Version History</h2></div><button type="button" className="module3-secondary-button" onClick={() => onResubmit(proposalHistory.find((item) => item.id === report.proposal.id) ?? proposalHistory[0])}>Resubmit new version</button></div><p className="module3-muted">Only versions of this proposal are listed. Upload the next file with “Resubmit new version” to create a comparable version.</p><div className="module3-history-list">{proposalHistory.map((item) => <div className="module3-history-row" key={item.id}><button type="button" onClick={() => item.report_available && onSelect(item.id)} disabled={!item.report_available}><span>v{item.version} - {item.filename}</span><strong>{item.report_available ? `${item.score ?? 0}%` : item.status}</strong></button>{item.status === "DRAFT" && <button type="button" className="module3-secondary-button" onClick={() => onResubmit(item)}>Edit draft</button>}{["DRAFT", "SUBMITTED", "RESUBMITTED", "CHANGES_REQUESTED"].includes(item.status) && <button type="button" className="module3-secondary-button" onClick={() => onWithdraw(item.id)} disabled={busy}>Withdraw</button>}</div>)}</div>{(report.versionHistory ?? []).some((item) => item.changeSummary) && <div className="module3-history-list">{(report.versionHistory ?? []).filter((item) => item.changeSummary).map((item) => <article className="module3-history-row" key={`summary-${item.version}`}><span><strong>v{item.version} → v{item.changeSummary?.toVersion}</strong> {item.changeSummary?.summary}</span><small>{item.changeSummary?.changedSections.join(", ") || "No section changes"} · {item.changeSummary?.source}</small></article>)}</div>}<ProposalVersionComparison api={api} submissionId={report.proposal.id} /></section>}
  </div>;
}
