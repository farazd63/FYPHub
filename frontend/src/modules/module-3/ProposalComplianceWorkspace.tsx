import { useEffect, useState, type FormEvent } from "react";
import "./module-3.css";

type Submission = { id: number; proposal_key: string; title: string; proposal_type: string; version: number; status: string; processing_status: string; filename: string; page_count: number; score: number | null; report_status: string | null; report_available: boolean; created_at: string };
type Summary = { score: number; status: string; totalIssues: number; metrics: { passed: number; failed: number; partial: number; total: number } };
type Category = { name: string; status: string; detail: string };
type Section = { name: string; check1: string; check2: string };
type Violation = { id: string; severity: string; title: string; location: string; requirement: unknown; detected: unknown; difference: unknown; evidence: string; affectedArea: string };
type Report = { reportSummary: Summary; categories: Category[]; sectionCompliance: Section[]; violations: Violation[]; missingSections: { issue: string; details: string }[]; finalResults: { totalChecks: number; passed: number; failed: number; partial: number; totalViolations: number; severityBreakdown: { major: number; minor: number; info: number } }; document: { filename: string; pageCount: number; previewText: string; selectedPage: number }; proposal: { id: number; proposalKey?: string; title: string; type: string; version: number }; versionHistory: { version: number; filename: string; score: number | null }[] };

const display = (value: unknown) => Array.isArray(value) ? value.join(", ") : value === null || value === undefined || value === "" ? "Not available" : String(value);
const statusClass = (status: string) => status.toLowerCase().replaceAll(" ", "-").replaceAll("_", "-");

function Pill({ status }: { status: string }) { return <span className={`module3-status-pill module3-status-pill--${statusClass(status)}`}>{status}</span>; }
function Metric({ icon, label, value, tone }: { icon: string; label: string; value: number; tone: string }) { return <div className="module3-metric"><span className={`module3-metric-icon module3-metric-icon--${tone}`}>{icon}</span><span>{label}</span><strong>{value}</strong></div>; }

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

  const openReport = async (id: number) => {
    setSelectedId(id); setError("");
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
  const newCheck = () => { setShowUpload(true); setReport(null); setResubmitKey(null); setMessage(""); };

  if (loading && !report) return <section className="module3-workspace"><div className="module3-loading">Loading proposal compliance workspace...</div></section>;
  return <section className="module3-workspace" aria-labelledby="module3-compliance-heading">
    <div className="module3-page-heading module3-report-heading"><div><p className="module3-eyebrow">Module 3 - Proposal review</p><h1 id="module3-compliance-heading">Compliance Report</h1><p>Detailed analysis of your proposal against the active university template.</p></div><div className="module3-report-actions"><button type="button" onClick={newCheck} className="module3-secondary-button">New Check</button>{report && <><button type="button" onClick={() => void rerun()} className="module3-primary-button" disabled={busy}>Re-run Check</button><button type="button" onClick={download} className="module3-secondary-button">Download PDF</button><button type="button" onClick={original} className="module3-secondary-button">View Original</button></>}</div></div>
    {message && <p className="module3-alert module3-alert--success" role="status">{message}</p>}{error && <p className="module3-alert module3-alert--error" role="alert">{error}</p>}
    {showUpload || !report ? <form className="module3-panel module3-proposal-upload" onSubmit={(event) => void submit(event)}><div className="module3-panel-heading"><div><span className="module3-kicker">{resubmitKey ? "Resubmit version" : "New check"}</span><h2>{resubmitKey ? "Resubmit Your Proposal" : "Submit Your Proposal"}</h2></div><span className="module3-live-dot">Template-aware</span></div><p className="module3-muted">Upload your existing proposal for compliance checking. The active university baseline is used and every uploaded version is preserved.</p><div className="module3-form-grid"><label>Proposal title<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Enter proposal title" /></label><label>Proposal type<select value={proposalType} onChange={(event) => setProposalType(event.target.value as "SHORT" | "LONG")}><option value="SHORT">Short proposal</option><option value="LONG">Long proposal</option></select></label></div><label className="module3-file-drop">Proposal document<input type="file" accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file && <strong>{file.name}</strong>}</label><div className="module3-form-actions"><button type="submit" data-action="draft" className="module3-secondary-button" disabled={busy}>Save Draft</button><button type="submit" data-action="submit" className="module3-primary-button" disabled={busy}>{busy ? "Processing proposal..." : "Submit & run compliance check"}</button></div>{submissions.some((item) => item.status === "DRAFT") && <div className="module3-draft-list"><strong>Saved drafts</strong>{submissions.filter((item) => item.status === "DRAFT").map((item) => <div key={item.id}><span>v{item.version} - {item.title}</span><button type="button" className="module3-secondary-button" onClick={() => void submitDraft(item.id)} disabled={busy}>Submit draft</button></div>)}</div>}</form> : <ReportView report={report} submissions={submissions} onSelect={(id) => void openReport(id)} onDownload={download} onOriginal={original} onRerun={() => void rerun()} onResubmit={startResubmit} busy={busy} />}
  </section>;
}

function ReportView({ report, submissions, onSelect, onDownload, onOriginal, onRerun, onResubmit, busy }: { report: Report; submissions: Submission[]; onSelect: (id: number) => void; onDownload: () => void; onOriginal: () => void; onRerun: () => void; onResubmit: (item: Submission) => void; busy: boolean }) {
  const summary = report.reportSummary;
  return <>
    <section className="module3-report-hero module3-panel"><div className="module3-score-wrap"><div className="module3-score-ring" style={{ background: `conic-gradient(#ef3340 ${summary.score}%, #e7edf5 0)` }}><div><strong>{summary.score}%</strong><span>Compliance Score</span></div></div><div><h2>Overall Status</h2><Pill status={summary.status} /><p>{summary.totalIssues} issues found in your proposal</p></div></div><div className="module3-metrics"><Metric icon="OK" label="Passed" value={summary.metrics.passed} tone="pass" /><Metric icon="X" label="Failed" value={summary.metrics.failed} tone="fail" /><Metric icon="!" label="Partial" value={summary.metrics.partial} tone="partial" /><Metric icon="#" label="Total" value={summary.metrics.total} tone="total" /></div></section>
    <div className="module3-report-grid module3-report-grid--top"><section className="module3-panel"><h2 className="module3-section-title">Summary by Category</h2><div className="module3-category-list">{report.categories.map((category) => <div className="module3-category-row" key={category.name}><span className="module3-category-icon">+</span><strong>{category.name}</strong><Pill status={category.status === "PASS" ? "Compliant" : category.status === "FAIL" ? "Non-Compliant" : "Partial"} /><small>{category.detail}</small></div>)}</div></section><section className="module3-panel"><h2 className="module3-section-title">Section-wise Compliance</h2><div className="module3-section-table">{report.sectionCompliance.length ? report.sectionCompliance.map((section) => <div className="module3-section-row" key={section.name}><strong>{section.name}</strong><Pill status={section.check1} /><Pill status={section.check2} /></div>) : <p className="module3-muted">The active template has no reliably detected required sections.</p>}</div></section></div>
    <div className="module3-report-grid module3-report-grid--middle"><section className="module3-panel"><h2 className="module3-section-title module3-section-title--danger">Detailed Violation Report</h2>{report.violations.length ? <div className="module3-violation-list">{report.violations.map((violation) => <article className={`module3-violation module3-violation--${statusClass(violation.severity)}`} key={violation.id}><div className="module3-violation-head"><div><b>#{violation.id}</b><span>{violation.severity}</span><strong>{violation.title}</strong></div><Pill status="Non-Compliant" /></div><div className="module3-violation-body"><div><b>Location</b><span>{violation.location}</span><b>Requirement</b><span>{display(violation.requirement)}</span><b>Detected</b><span>{display(violation.detected)}</span><b>Difference</b><span>{display(violation.difference)}</span></div><div><b>Evidence</b><p>{violation.evidence}</p></div><div><b>Affected Area</b><p>{violation.affectedArea}</p><button type="button" onClick={onOriginal}>View in Document</button></div></div></article>)}</div> : <p className="module3-empty">No violations were detected.</p>}</section><section className="module3-panel module3-document-preview"><div className="module3-preview-heading"><h2 className="module3-section-title">Document Preview</h2><span>Page {report.document.selectedPage} of {report.document.pageCount}</span></div><div className="module3-paper"><h3>{report.proposal.title}</h3><p>{report.document.filename}</p>{report.violations[0] && <div className="module3-highlight"><span>VIOLATION {report.violations[0].id}</span>{report.document.previewText.slice(0, 260)}</div>}<p>{report.document.previewText.slice(260, 620) || "Remaining content..."}</p></div><div className="module3-zoom-toolbar"><button type="button">-</button><span>100%</span><button type="button">+</button><button type="button" onClick={onOriginal}>Full view</button></div></section></div>
    <div className="module3-report-grid module3-report-grid--bottom"><section className="module3-panel module3-missing-panel"><h2 className="module3-section-title">Missing &amp; Misplaced Sections</h2>{report.missingSections.length ? <div className="module3-missing-list">{report.missingSections.map((item) => <div key={`${item.issue}-${item.details}`}><strong>{item.issue}</strong><span>{item.details}</span></div>)}</div> : <p className="module3-success-text">No missing or misplaced sections detected.</p>}</section><section className="module3-panel module3-final-panel"><h2 className="module3-section-title">Final Results</h2><div className="module3-final-metrics"><span>Total Checks<strong>{report.finalResults.totalChecks}</strong></span><span>Passed<strong>{report.finalResults.passed}</strong></span><span>Failed<strong>{report.finalResults.failed}</strong></span><span>Partial<strong>{report.finalResults.partial}</strong></span><span>Violations<strong>{report.finalResults.totalViolations}</strong><small>Major {report.finalResults.severityBreakdown.major} - Minor {report.finalResults.severityBreakdown.minor} - Info {report.finalResults.severityBreakdown.info}</small></span></div><div className="module3-form-actions"><button className="module3-primary-button" type="button" onClick={onDownload}>Download Detailed Report (PDF)</button><button className="module3-secondary-button" type="button" onClick={onRerun} disabled={busy}>Re-run Check</button></div></section></div>
    {submissions.length > 0 && <section className="module3-panel module3-history-panel"><div className="module3-panel-heading"><h2 className="module3-section-title">Version History</h2><button type="button" className="module3-secondary-button" onClick={() => onResubmit(submissions.find((item) => item.id === report.proposal.id) ?? submissions[0])}>Resubmit new version</button></div><div className="module3-history-list">{submissions.map((item) => <div className="module3-history-row" key={item.id}><button type="button" onClick={() => item.report_available && onSelect(item.id)} disabled={!item.report_available}><span>v{item.version} - {item.filename}</span><strong>{item.report_available ? `${item.score ?? 0}%` : item.status}</strong></button>{item.status === "DRAFT" && <button type="button" className="module3-secondary-button" onClick={() => onResubmit(item)}>Edit draft</button>}</div>)}</div></section>}
  </>;
}
