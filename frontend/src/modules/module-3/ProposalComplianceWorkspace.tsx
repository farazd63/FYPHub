import { ProposalAiSummary, type ProposalSummary } from "../../ProposalAiSummary";
import { useEffect, useState, type FormEvent } from "react";
import "./module-3.css";

type Submission = { id: number; proposal_key: string; title: string; proposal_type: string; version: number; status: string; processing_status: string; filename: string; page_count: number; score: number | null; report_status: string | null; report_available: boolean; created_at: string };
type Summary = { score: number; status: string; totalIssues: number; metrics: { passed: number; failed: number; partial: number; total: number } };
type ReviewCheck = { id: string; name: string; status: string; expected?: unknown; actual?: unknown; difference?: unknown; evidence?: string; location?: unknown };
type Category = { name: string; status: string; detail: string; checks?: ReviewCheck[] };
type Section = { name: string; check1: string; check2: string };
type Violation = { id: string; severity: string; title: string; location: string; requirement: unknown; detected: unknown; difference: unknown; evidence: string; affectedArea: string };
type DocumentDifferenceIssue = { id: string; category: string; severity: "critical" | "warning" | "passed"; issue: string; originalTemplate: string; studentDocument: string; difference: string; affectedPages: number[]; requiredAction: string; status: "failed" | "warning" | "passed" };
type ReportMetadata = { reportVersion?: string; templateName?: string; analysisDate?: string };
type ChangeSummary = { source: string; model: string; fromVersion: number; toVersion: number; summary: string; changedSections: string[]; advisory: boolean };
type Report = { reportSummary: Summary; aiSummary?: ProposalSummary | null; reportMetadata?: ReportMetadata; documentDifferenceIssues?: DocumentDifferenceIssue[]; categories: Category[]; sectionCompliance: Section[]; violations: Violation[]; missingSections: { issue: string; details: string }[]; academicConsistency?: { name: string; status: string; evidence: string }[]; finalResults: { totalChecks: number; passed: number; failed: number; partial: number; totalViolations: number; severityBreakdown: { major: number; minor: number; info: number } }; document: { filename: string; pageCount: number; previewText: string; selectedPage: number }; proposal: { id: number; proposalKey?: string; title: string; type: string; version: number }; template?: { title?: string; versionId?: number; rules?: Record<string, unknown> }; versionHistory?: { version: number; filename: string; score: number | null; changeSummary?: ChangeSummary }[] };
type DocumentPreview = { url: string; title: string; pageCount: number };

const statusClass = (status: string) => status.toLowerCase().replaceAll(" ", "-").replaceAll("_", "-");

function Pill({ status }: { status: string }) { return <span className={`module3-status-pill module3-status-pill--${statusClass(status)}`}>{status}</span>; }

export function ProposalComplianceWorkspace({ api, reviewerMode = false }: { api: string; reviewerMode?: boolean }) {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [summaryRevision, setSummaryRevision] = useState(0);
  const [proposalType, setProposalType] = useState<"SHORT" | "LONG">("SHORT");
  const [title, setTitle] = useState("");
  const [resubmitKey, setResubmitKey] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [previewPage, setPreviewPage] = useState(1);
  const [previewZoom, setPreviewZoom] = useState(100);
  const [previewFrameBusy, setPreviewFrameBusy] = useState(false);

  useEffect(() => () => {
    if (preview?.url) URL.revokeObjectURL(preview.url);
  }, [preview?.url]);

  const openReport = async (id: number) => {
    setSelectedId(id); setError(""); setPreview(null); setPreviewError("");
    const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${id}`, { credentials: "include" });
    if (!response.ok) { setError("The compliance report is not available yet."); return; }
    setReport(await response.json() as Report); setShowUpload(false);
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
    setProposalType(item.proposal_type as "SHORT" | "LONG"); setTitle(item.title); setResubmitKey(item.proposal_key); setReport(null); setPreview(null); setPreviewError(""); setShowUpload(true); setMessage(`Resubmission started for ${item.title}. Choose the new document file.`); setError("");
  };

  const rerun = async () => {
    if (!selectedId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${selectedId}/run`, { method: "POST", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Compliance re-run failed.");
      setReport(payload as Report); setSummaryRevision((value) => value + 1); setMessage("Compliance report re-run against the current active baseline."); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Compliance re-run failed."); } finally { setBusy(false); }
  };

  const previewDocument = async (path: string, title: string, fallbackPageCount = 1) => {
    if (!selectedId) return;
    setPreviewBusy(true); setPreviewFrameBusy(true); setPreviewError("");
    try {
      const response = await fetch(`${api}${path}`, { credentials: "include" });
      if (!response.ok) throw new Error("The document preview could not be loaded.");
      const blob = await response.blob();
      const pageCount = Number(response.headers.get("X-Preview-Page-Count")) || fallbackPageCount;
      setPreview({ url: URL.createObjectURL(blob), title, pageCount: Math.max(1, pageCount) });
      setPreviewPage(1); setPreviewZoom(100);
    } catch (caught) {
      setPreviewFrameBusy(false); setPreviewError(caught instanceof Error ? caught.message : "The document preview could not be loaded.");
    } finally { setPreviewBusy(false); }
  };
  const previewReport = () => { if (selectedId) void previewDocument(`/api/v1/proposal-compliance/reports/${selectedId}/pdf`, "Compliance report preview"); };
  const original = () => { if (selectedId) void previewDocument(`/api/v1/proposal-compliance/reports/${selectedId}/original`, "Original student document", report?.document.pageCount || 1); };
  const annotated = () => { if (selectedId) void previewDocument(`/api/v1/proposal-compliance/reports/${selectedId}/annotated`, "Annotated student document", (report?.document.pageCount || 1) + 1); };
  const template = () => { if (selectedId) void previewDocument(`/api/v1/proposal-compliance/reports/${selectedId}/template`, "Original university template"); };
  const closePreview = () => { setPreview(null); setPreviewError(""); setPreviewFrameBusy(false); setPreviewPage(1); };
  const newCheck = () => { closePreview(); setShowUpload(true); setReport(null); setResubmitKey(null); setMessage(""); };

  if (loading && !report) return <section className="module3-workspace"><div className="module3-loading">Loading proposal compliance workspace...</div></section>;
  return <section className="module3-workspace" aria-labelledby="module3-compliance-heading">
    <div className="module3-page-heading module3-report-heading"><div><p className="module3-eyebrow">Proposal Compliance Review</p><h1 id="module3-compliance-heading">Template Compliance and Document Difference Report</h1><p>Strict comparison between university template and student document</p></div><div className="module3-report-actions"><button type="button" onClick={newCheck} className="module3-secondary-button">New Check</button>{report && <><button type="button" onClick={() => void rerun()} className="module3-primary-button" disabled={busy}>Re-run Check</button><button type="button" onClick={previewReport} className="module3-secondary-button" disabled={previewBusy}>Preview PDF</button><button type="button" onClick={annotated} className="module3-secondary-button" disabled={previewBusy}>Preview Annotated PDF</button><button type="button" onClick={original} className="module3-secondary-button" disabled={previewBusy}>Preview Original</button>{reviewerMode && <><button type="button" onClick={() => void reviewStatus("APPROVED")} className="module3-secondary-button" disabled={busy}>Approve</button><button type="button" onClick={() => void reviewStatus("CHANGES_REQUESTED")} className="module3-secondary-button" disabled={busy}>Request changes</button><button type="button" onClick={() => void reviewStatus("REJECTED")} className="module3-secondary-button" disabled={busy}>Reject</button></>}</>}</div></div>
    {(previewBusy || previewError || preview) && <section className="module3-panel module3-inline-preview" aria-label="Document preview"><div className="module3-inline-preview__heading"><div><span className="module3-kicker">In-app document preview</span><h2>{preview?.title || "Document preview"}</h2></div>{preview && <button type="button" className="module3-secondary-button" onClick={closePreview}>Close preview</button>}</div>{previewBusy && <p className="module3-muted" role="status">Preparing the actual document preview...</p>}{previewError && <p className="module3-alert module3-alert--error" role="alert">{previewError}</p>}{preview && <><div className="module3-preview-controls" aria-label="Preview controls"><button type="button" className="module3-secondary-button" disabled={previewPage <= 1} onClick={() => setPreviewPage((page) => Math.max(1, page - 1))}>Previous page</button><span>Page {previewPage} of {preview.pageCount}</span><button type="button" className="module3-secondary-button" disabled={previewPage >= preview.pageCount} onClick={() => setPreviewPage((page) => Math.min(preview.pageCount, page + 1))}>Next page</button><label>Zoom<select value={previewZoom} onChange={(event) => setPreviewZoom(Number(event.target.value))}><option value={75}>75%</option><option value={100}>100%</option><option value={125}>125%</option><option value={150}>150%</option></select></label></div>{previewFrameBusy && <p className="module3-muted" role="status">Loading page...</p>}<iframe className="module3-inline-preview__frame" src={`${preview.url}#page=${previewPage}&zoom=${previewZoom}`} title={preview.title} onLoad={() => setPreviewFrameBusy(false)} onError={() => { setPreviewFrameBusy(false); setPreviewError("The document preview could not be displayed in the browser."); }} /></>}</section>}
    {message && <p className="module3-alert module3-alert--success" role="status">{message}</p>}{error && <p className="module3-alert module3-alert--error" role="alert">{error}</p>}
    {report && selectedId && !showUpload && <ProposalAiSummary key={`${selectedId}-${summaryRevision}`} api={api} requestId={selectedId} initialSummary={report.aiSummary} autoGenerate={!report.aiSummary} endpoint={`/api/v1/proposal-compliance/reports/${selectedId}/ai-summary`} />}
    {showUpload || !report ? <form className="module3-panel module3-proposal-upload" onSubmit={(event) => void submit(event)}><div className="module3-panel-heading"><div><span className="module3-kicker">{resubmitKey ? "Resubmit version" : "New check"}</span><h2>{resubmitKey ? "Resubmit Your Proposal" : "Submit Your Proposal"}</h2></div><span className="module3-live-dot">Template-aware</span></div><p className="module3-muted">Upload your existing proposal for compliance checking. The active university baseline is used and every uploaded version is preserved.</p><div className="module3-form-grid"><label>Proposal title<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Enter proposal title" /></label><label>Proposal type<select value={proposalType} onChange={(event) => setProposalType(event.target.value as "SHORT" | "LONG")}><option value="SHORT">Short proposal</option><option value="LONG">Long proposal</option></select></label></div><label className="module3-file-drop">Proposal document<input type="file" accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file && <strong>{file.name}</strong>}</label><div className="module3-form-actions"><button type="submit" data-action="draft" className="module3-secondary-button" disabled={busy}>Save Draft</button><button type="submit" data-action="submit" className="module3-primary-button" disabled={busy}>{busy ? "Processing proposal..." : "Submit & run compliance check"}</button></div>{submissions.some((item) => item.status === "DRAFT") && <div className="module3-draft-list"><strong>Saved drafts</strong>{submissions.filter((item) => item.status === "DRAFT").map((item) => <div key={item.id}><span>v{item.version} - {item.title}</span><button type="button" className="module3-secondary-button" onClick={() => void submitDraft(item.id)} disabled={busy}>Submit draft</button><button type="button" className="module3-secondary-button" onClick={() => void withdraw(item.id)} disabled={busy}>Withdraw</button></div>)}</div>}</form> : <ReportView report={report} submissions={submissions} onSelect={(id) => void openReport(id)} onPreviewReport={previewReport} onOriginal={original} onAnnotated={annotated} onTemplate={template} onResubmit={startResubmit} onWithdraw={withdraw} busy={busy} />}
  </section>;
}

const pageLabel = (pages: number[], pageCount: number) => {
  const normalized = [...new Set((pages ?? []).filter((page) => Number.isInteger(page) && page > 0))].sort((left, right) => left - right);
  const safePages = normalized.length ? normalized : Array.from({ length: Math.max(1, pageCount) }, (_, index) => index + 1);
  if (safePages.length === 1) return `Page ${safePages[0]}`;
  const contiguous = safePages.every((page, index) => index === 0 || page === safePages[index - 1] + 1);
  return contiguous ? `Pages ${safePages[0]}-${safePages[safePages.length - 1]}` : `Pages ${safePages.join(", ")}`;
};

const fallbackIssues = (report: Report): DocumentDifferenceIssue[] => {
  const pageCount = Math.max(1, report.document.pageCount || 1);
  const pages = Array.from({ length: pageCount }, (_, index) => index + 1);
  return report.categories.flatMap((category) => (category.checks ?? []).map((check) => {
    const failed = check.status === "FAIL";
    const passed = check.status === "PASS";
    const strict = ["Page Count", "Page Size", "Page Orientation", "Left Margin", "Right Margin", "Top Margin", "Bottom Margin", "Page Numbering", "Template Structure", "Section Sequence"].includes(check.name) || category.name === "Document Structure";
    const location = check.location && typeof check.location === "object" ? check.location as { page?: number } : {};
    const affectedPages = strict || !location.page ? pages : [location.page];
    const original = check.expected === null || check.expected === undefined || check.expected === "" ? "Template rule not configured" : Array.isArray(check.expected) ? check.expected.join(" -> ") : String(check.expected);
    const student = check.actual === null || check.actual === undefined || check.actual === "" ? "Measurement not detected" : Array.isArray(check.actual) ? check.actual.join(" -> ") : String(check.actual);
    return {
      id: check.id,
      category: category.name,
      severity: passed ? "passed" : strict ? "critical" : "warning",
      issue: check.name,
      originalTemplate: original,
      studentDocument: student,
      difference: passed ? "Matches the approved university template." : check.difference === null || check.difference === undefined ? "Could not verify this requirement from the uploaded document." : String(check.difference),
      affectedPages,
      requiredAction: passed ? "No action required." : "Follow the active university template requirement.",
      status: passed ? "passed" : failed ? "failed" : "warning",
    };
  }));
};

function IssueTable({ issues, pageCount }: { issues: DocumentDifferenceIssue[]; pageCount: number }) {
  if (!issues.length) return <p className="module3-empty">No checks in this group.</p>;
  return <div className="module3-comparison-table-wrap"><table className="module3-comparison-table"><thead><tr>{["Issue", "Original / University Template", "Student Document", "Difference", "Strict Page Number", "Required Action"].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{issues.map((item) => <tr key={item.id}><td data-label="Issue"><strong>{item.issue}</strong></td><td data-label="Original / University Template">{item.originalTemplate}</td><td data-label="Student Document">{item.studentDocument}</td><td data-label="Difference">{item.difference}</td><td data-label="Strict Page Number"><span className="module3-page-chip">{pageLabel(item.affectedPages, pageCount)}</span></td><td data-label="Required Action">{item.requiredAction}</td></tr>)}</tbody></table></div>;
}

function IssueGroup({ title, tone, issues, pageCount }: { title: string; tone: "critical" | "warning" | "passed"; issues: DocumentDifferenceIssue[]; pageCount: number }) {
  return <section className={`module3-issue-group module3-issue-group--${tone}`}><div className="module3-issue-group__heading"><div><span className="module3-kicker">{tone === "passed" ? "No action required" : tone === "critical" ? "Strict rule" : "Review recommended"}</span><h2>{title}</h2></div><span className="module3-issue-count">{issues.length}</span></div><IssueTable issues={issues} pageCount={pageCount} /></section>;
}

function ReportView({ report, submissions, onSelect, onPreviewReport, onOriginal, onAnnotated, onTemplate, onResubmit, onWithdraw, busy }: { report: Report; submissions: Submission[]; onSelect: (id: number) => void; onPreviewReport: () => void; onOriginal: () => void; onAnnotated: () => void; onTemplate: () => void; onResubmit: (item: Submission) => void; onWithdraw: (id: number) => void; busy: boolean }) {
  const issues = report.documentDifferenceIssues?.length ? report.documentDifferenceIssues : fallbackIssues(report);
  const pageCount = Math.max(1, report.document.pageCount || 1);
  const critical = issues.filter((item) => item.severity === "critical" && item.status !== "passed");
  const warnings = issues.filter((item) => item.severity === "warning" && item.status !== "passed");
  const passed = issues.filter((item) => item.status === "passed");
  const status = critical.some((item) => item.status === "failed") ? "Rejected" : critical.length || warnings.length ? "Needs Correction" : "Compliant";
  const templateName = report.reportMetadata?.templateName || report.template?.title || "Active University Template";
  const analysisDate = report.reportMetadata?.analysisDate ? new Date(report.reportMetadata.analysisDate).toLocaleDateString() : "Current analysis";
  const reportVersion = report.reportMetadata?.reportVersion || "2.0";
  const templatePageCount = issues.find((item) => item.issue === "Page Count")?.originalTemplate || "Configured by active baseline";
  return <>
    <section className="module3-report-meta module3-panel"><div><span className="module3-kicker">Student-facing compliance report</span><h2>{report.proposal.title}</h2><p>Version {report.proposal.version} - {report.document.filename}</p></div><dl><div><dt>Template name</dt><dd>{templateName}</dd></div><div><dt>Analysis date</dt><dd>{analysisDate}</dd></div><div><dt>Report version</dt><dd>{reportVersion}</dd></div></dl></section>
    <section className="module3-summary-cards" aria-label="Compliance summary"><div className="module3-summary-card"><span>Total Issues</span><strong>{critical.length + warnings.length}</strong><small>All corrections to review</small></div><div className="module3-summary-card module3-summary-card--critical"><span>Critical Issues</span><strong>{critical.length}</strong><small>Strict requirements</small></div><div className="module3-summary-card module3-summary-card--warning"><span>Warnings</span><strong>{warnings.length}</strong><small>Needs verification</small></div><div className={`module3-summary-card module3-summary-card--status module3-summary-card--${status.toLowerCase().replaceAll(" ", "-")}`}><span>Submission Status</span><strong>{status}</strong><small>{status === "Compliant" ? "Ready for submission" : "Correction required"}</small></div></section>
    <div className="module3-compliance-layout"><main className="module3-issue-column"><section className="module3-panel module3-issue-intro"><span className="module3-kicker">Comparison-based review</span><h2>Document differences</h2><p>Every finding compares the approved university template with the uploaded student document and identifies the exact affected PDF page.</p></section><IssueGroup title="Critical Violations" tone="critical" issues={critical} pageCount={pageCount} /><IssueGroup title="Warnings" tone="warning" issues={warnings} pageCount={pageCount} /><IssueGroup title="Passed Checks" tone="passed" issues={passed} pageCount={pageCount} /></main><aside className="module3-report-sidebar"><section className="module3-panel module3-preview-card"><div className="module3-sidebar-heading"><div><span className="module3-kicker">Approved baseline</span><h2>Original Template Preview</h2></div><Pill status="Compliant" /></div><div className="module3-source-card"><strong>{templateName}</strong><span>{report.proposal.type} template · actual uploaded source</span><em>{templatePageCount}</em></div><button type="button" className="module3-secondary-button module3-full-button" onClick={onTemplate}>View original template</button></section><section className="module3-panel module3-preview-card"><div className="module3-sidebar-heading"><div><span className="module3-kicker">Uploaded file</span><h2>Student Document Preview</h2></div><span className="module3-page-chip">{pageLabel(pageCount > 1 ? Array.from({ length: pageCount }, (_, index) => index + 1) : [1], pageCount)}</span></div><div className="module3-source-card module3-source-card--student"><strong>{report.document.filename}</strong><span>{report.proposal.title} · actual uploaded source</span><em>{critical.length ? `${critical.length} strict issue${critical.length === 1 ? "" : "s"} marked` : "No critical issues marked"}</em></div><div className="module3-sidebar-actions"><button type="button" className="module3-secondary-button" onClick={onOriginal}>View student document</button><button type="button" className="module3-secondary-button" onClick={onAnnotated}>View annotated copy</button></div></section><section className="module3-panel module3-difference-summary"><span className="module3-kicker">At a glance</span><h2>Difference Summary</h2><p>{critical.length ? `${critical.length} strict requirement${critical.length === 1 ? "" : "s"} must be corrected before submission.` : warnings.length ? "No critical violations were found, but review the warnings before submission." : "The student document matches the active university template."}</p><dl><div><dt>Template pages</dt><dd>{templatePageCount}</dd></div><div><dt>Student pages</dt><dd>{pageCount === 1 ? "1 page" : `${pageCount} pages`}</dd></div></dl><button type="button" className="module3-primary-button module3-preview-report-button" onClick={onPreviewReport}>Preview Correction Report</button></section></aside></div>
    <div className="module3-rule-banner"><strong>Strict Rule</strong><span>Page count, page numbering, page size, and approved template structure are mandatory. Every violation must show the exact affected page.</span></div>
    {submissions.length > 0 && <section className="module3-panel module3-history-panel"><div className="module3-panel-heading"><h2 className="module3-section-title">Version History</h2><button type="button" className="module3-secondary-button" onClick={() => onResubmit(submissions.find((item) => item.id === report.proposal.id) ?? submissions[0])}>Resubmit new version</button></div><div className="module3-history-list">{submissions.map((item) => <div className="module3-history-row" key={item.id}><button type="button" onClick={() => item.report_available && onSelect(item.id)} disabled={!item.report_available}><span>v{item.version} - {item.filename}</span><strong>{item.report_available ? `${item.score ?? 0}%` : item.status}</strong></button>{item.status === "DRAFT" && <button type="button" className="module3-secondary-button" onClick={() => onResubmit(item)}>Edit draft</button>}{["DRAFT", "SUBMITTED", "RESUBMITTED", "CHANGES_REQUESTED"].includes(item.status) && <button type="button" className="module3-secondary-button" onClick={() => onWithdraw(item.id)} disabled={busy}>Withdraw</button>}</div>)}</div></section>}
  </>;
}
