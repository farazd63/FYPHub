import { useCallback, useEffect, useState } from "react";
import "./proposal-compliance-report.css";
import "./proposal-compliance-report-overrides.css";

type Proposal = { id: number; status: string; title: string | null; proposal_type?: string; document: { filename: string } | null };
type Overall = { score: number; status: string; passed: number; failed: number; partial: number; unverifiable: number; total: number };
type Category = { name: string; status: string; summary: string; checks: Record<string, number> };
type Check = { id: string; name: string; category: string; status: string; severity?: string; expected: unknown; actual: unknown; difference: number | null; location?: { scope?: string; page?: number | null }; evidence: string };
type VersionHistory = { current_version: number; previous_version: number | null; added_headings: string[]; removed_headings: string[]; text_length_delta: number | null; summary: string };
type AcademicAnalysis = { consistency_score: number; alignment_valid: boolean; section_analysis: Record<string, string>; identified_gaps: { category: string; severity: string; issue_description: string; recommendation: string }[]; executive_summary: string; status: string; source: string; model?: string | null; advisory?: boolean };
type Report = { report_id: number; proposal: { request_id: number; title: string; type: string; version: number; filename: string }; template: { title: string; version: number; type: string }; overall: Overall; categories: Category[]; sections: Check[]; violations: Check[]; missing_sections: { issue: string; details: string }[]; document: { filename: string; page_count: number; preview_available: boolean; original_url?: string; version_history?: VersionHistory }; version_history?: VersionHistory; academic_analysis?: AcademicAnalysis };

const label = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/(^|\s)\w/g, (match) => match.toUpperCase());
const displayValue = (item: unknown) => item === null || item === undefined || item === "" ? "Not available" : String(item);
const statusClass = (status: string) => status === "PASS" || status === "COMPLIANT" ? "pass" : status === "FAIL" || status === "NOT_COMPLIANT" ? "fail" : status === "UNVERIFIABLE" ? "unverifiable" : "partial";

function StatusPill({ status }: { status: string }) {
  const tone = statusClass(status);
  return <span className={`compliance-pill compliance-pill--${tone}`}><span aria-hidden="true">{tone === "pass" ? "OK" : tone === "fail" ? "X" : tone === "unverifiable" ? "i" : "!"}</span>{label(status)}</span>;
}

function EmptyReport({ message, onRun, busy }: { message: string; onRun: () => void; busy: boolean }) {
  return <section className="compliance-empty"><div className="compliance-empty__icon" aria-hidden="true">OK</div><h2>{message}</h2><p>Upload and submit a proposal first, then run the deterministic template checks.</p><button type="button" onClick={onRun} disabled={busy}>{busy ? "Analyzing proposal..." : "Run compliance check"}</button></section>;
}

export function ProposalComplianceReport({ api, reviewerMode = false, autoRun = false, embedded = false }: { api: string; reviewerMode?: boolean; autoRun?: boolean; embedded?: boolean }) {
  const [report, setReport] = useState<Report | null>(null);
  const [availableReports, setAvailableReports] = useState<Report[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [academicBusy, setAcademicBusy] = useState(false);
  const [message, setMessage] = useState("");

  const runReport = useCallback(async (proposalId: number) => {
    const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${proposalId}/run`, { method: "POST", credentials: "include" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "The active template or proposal document is not ready.");
    const next = body as Report;
    setReport(next);
    setState("ready");
    setAvailableReports((current) => [next, ...current.filter((item) => item.report_id !== next.report_id)]);
    return next;
  }, [api]);

  const load = useCallback(async () => {
    setState("loading");
    setMessage("");
    try {
      if (reviewerMode) {
        const response = await fetch(`${api}/api/v1/proposal-compliance/reports`, { credentials: "include" });
        if (!response.ok) throw new Error("Authorized compliance reports could not be loaded.");
        const reports = await response.json() as Report[];
        setAvailableReports(reports);
        if (!reports.length) {
          const monitorPaths = ["/api/v1/proposals/admin/monitor", "/api/v1/proposals/coordinator/monitor", "/api/v1/proposals/mine"];
          let monitored: Proposal[] = [];
          for (const path of monitorPaths) {
            const monitorResponse = await fetch(`${api}${path}`, { credentials: "include" });
            if (monitorResponse.ok) {
              monitored = await monitorResponse.json() as Proposal[];
              if (monitored.length) break;
            }
          }
          const selected = monitored.find((item) => item.document && ["SUBMITTED", "ACCEPTED", "CHANGES_REQUESTED"].includes(item.status)) ?? monitored.find((item) => item.document) ?? null;
          setProposal(selected);
          setMessage(selected ? "A submitted proposal is ready. Run the compliance check to generate its report." : "No submitted proposal with a document is available yet.");
          setState("empty");
          return;
        }
        setReport(reports[0]);
        setProposal({ id: reports[0].proposal.request_id, status: "COMPLETED", title: reports[0].proposal.title, document: { filename: reports[0].proposal.filename } });
        setState("ready");
        return;
      }
      const response = await fetch(`${api}/api/v1/proposals/mine`, { credentials: "include" });
      const proposals = response.ok ? await response.json() as Proposal[] : [];
      const selected = proposals.find((item) => item.document && ["SUBMITTED", "ACCEPTED", "CHANGES_REQUESTED"].includes(item.status)) ?? proposals.find((item) => item.document) ?? null;
      setProposal(selected);
      if (!selected) { setState("empty"); return; }
      const reportResponse = await fetch(`${api}/api/v1/proposal-compliance/reports/${selected.id}`, { credentials: "include" });
      if (reportResponse.status === 404) {
        if (autoRun) {
          setBusy(true);
          try { await runReport(selected.id); } finally { setBusy(false); }
        } else setState("empty");
        return;
      }
      if (!reportResponse.ok) throw new Error("The compliance report could not be loaded.");
      setReport(await reportResponse.json() as Report);
      setState("ready");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The compliance service is unavailable.");
      setState("error");
    }
  }, [api, autoRun, reviewerMode, runReport]);

  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [load]);
  useEffect(() => {
    const refresh = (event: Event) => {
      const proposalId = (event as CustomEvent<{ id?: number }>).detail?.id;
      if (autoRun && proposalId) {
        setBusy(true);
        void runReport(proposalId).catch((error) => {
          setMessage(error instanceof Error ? error.message : "The compliance run failed.");
          setState("error");
        }).finally(() => setBusy(false));
        return;
      }
      void load();
    };
    window.addEventListener("module3-template-uploaded", refresh);
    window.addEventListener("module3-proposal-uploaded", refresh);
    return () => {
      window.removeEventListener("module3-template-uploaded", refresh);
      window.removeEventListener("module3-proposal-uploaded", refresh);
    };
  }, [autoRun, load, runReport]);

  const run = async () => {
    if (!proposal || busy) return;
    setBusy(true);
    setMessage("");
    try {
      await runReport(proposal.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The compliance run failed.");
      setState("error");
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    if (!report) return;
    const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${report.proposal.request_id}/pdf`, { credentials: "include" });
    if (!response.ok) { setMessage("The PDF report could not be generated."); return; }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `proposal-compliance-${report.proposal.request_id}.pdf`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const runAcademicAnalysis = async () => {
    if (!report || academicBusy) return;
    setAcademicBusy(true); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/reports/${report.proposal.request_id}/academic-analysis`, { method: "POST", credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Academic consistency analysis could not be completed.");
      setReport({ ...report, academic_analysis: body as AcademicAnalysis });
    } catch (error) { setMessage(error instanceof Error ? error.message : "Academic consistency analysis is unavailable."); }
    finally { setAcademicBusy(false); }
  };

  if (state === "loading") return <section className="compliance-loading"><div className="compliance-spinner" aria-hidden="true" /><h1>Analyzing your proposal...</h1><p>Loading the stored compliance report.</p></section>;
  if (state === "error") return <section className="compliance-empty"><h2>Compliance report unavailable</h2><p role="alert">{message}</p><button type="button" onClick={() => void load()}>Retry</button></section>;
  if (state === "empty" || !report) return <><div className="compliance-heading"><div><p className="student-overview__eyebrow">Proposal checker</p><h1>Compliance Report</h1><p>Detailed analysis of your proposal against the university template.</p></div></div>{message && <p className="compliance-alert" role="alert">{message}</p>}<EmptyReport message={proposal ? "No compliance report is available yet." : "Submit a proposal to begin."} onRun={() => void run()} busy={busy} /></>;

  const { overall } = report;
  const issues = overall.failed + overall.partial + overall.unverifiable;
  return <section className={`compliance-report${embedded ? " compliance-report--embedded" : ""}`} aria-labelledby="compliance-report-heading">
    <header className="compliance-heading"><div><p className="student-overview__eyebrow">Proposal checker</p><h1 id="compliance-report-heading">Compliance Report</h1><p>Detailed analysis of your proposal against the university template.</p></div><div className="compliance-heading__actions">{reviewerMode && availableReports.length > 1 && <select aria-label="Select compliance report" value={report.report_id} onChange={(event) => { const selected = availableReports.find((item) => item.report_id === Number(event.target.value)); if (selected) { setReport(selected); setProposal({ id: selected.proposal.request_id, status: "COMPLETED", title: selected.proposal.title, document: { filename: selected.proposal.filename } }); } }}><option value={report.report_id}>{report.proposal.title}</option>{availableReports.filter((item) => item.report_id !== report.report_id).map((item) => <option key={item.report_id} value={item.report_id}>{item.proposal.title}</option>)}</select>}<button type="button" onClick={() => void run()} disabled={busy}>{busy ? "Checking..." : "Re-run Check"}</button><button type="button" onClick={() => void download()}>Download PDF</button><a href={`${api}/api/v1/proposals/document/${report.proposal.request_id}`} target="_blank" rel="noreferrer">View Original</a></div></header>
    <div className="compliance-summary"><div className="compliance-score"><div className={`compliance-score__ring compliance-score__ring--${statusClass(overall.status)}`}><strong>{overall.score}%</strong><span>Compliance<br />Score</span></div></div><div className="compliance-summary__status"><span>Overall Status</span><strong><StatusPill status={overall.status} /></strong><p>{issues} review item{issues === 1 ? "" : "s"} found in your proposal</p></div><div className="compliance-stat compliance-stat--pass"><b>OK</b><span>Passed</span><strong>{overall.passed}</strong></div><div className="compliance-stat compliance-stat--fail"><b>X</b><span>Failed</span><strong>{overall.failed}</strong></div><div className="compliance-stat compliance-stat--partial"><b>!</b><span>Partial</span><strong>{overall.partial}</strong></div><div className="compliance-stat compliance-stat--total"><b>#</b><span>Total</span><strong>{overall.total}</strong></div></div>
    <div className="compliance-grid compliance-grid--top"><section className="compliance-card"><h2>Summary by Category</h2>{report.categories.length ? report.categories.map((category) => <div className="compliance-category" key={category.name}><span className="compliance-category__icon" aria-hidden="true">+</span><strong>{category.name}</strong><StatusPill status={category.status} /><small>{category.summary}</small></div>) : <p className="compliance-muted">No template categories are configured yet.</p>}</section><section className="compliance-card"><h2>Section-wise Compliance</h2>{report.sections.length ? report.sections.map((item) => <div className="compliance-section-row" key={item.id}><span aria-hidden="true">#</span><strong>{item.name}</strong><StatusPill status={item.status} /></div>) : <p className="compliance-muted">The active template has no required sections configured.</p>}</section></div>
     <div className="compliance-grid compliance-grid--middle"><section className="compliance-card compliance-violations"><h2>Detailed Violation Report</h2>{report.violations.length ? report.violations.map((item) => <article className={`compliance-violation compliance-violation--${statusClass(item.status)}`} key={item.id}><div className="compliance-violation__head"><b>#{item.id}</b><span>{item.severity ?? "Review"}</span><strong>{item.name}</strong><StatusPill status={item.status} /></div><div className="compliance-violation__body"><div><b>Requirement</b><span>{displayValue(item.expected)}</span></div><div><b>Detected</b><span>{displayValue(item.actual)}</span></div><div><b>Location</b><span>{item.location?.page ? `Page ${item.location.page}` : item.location?.scope ?? "Document"}</span></div><div><b>Evidence</b><span>{item.evidence}</span></div></div></article>) : <p className="compliance-success">All configured requirements passed.</p>}</section><section className="compliance-card compliance-preview"><div className="compliance-card__row"><h2>Document Preview</h2><span>Page 1 of {report.document.page_count}</span></div><div className="compliance-paper"><h3>{report.proposal.title}</h3><p>{report.document.filename}</p><p className="compliance-paper__line" /><p className="compliance-paper__line compliance-paper__line--short" /><p className="compliance-paper__line" /></div><p className="compliance-muted">Preview is based on the authorized extracted document representation.</p>{report.version_history && <div className="compliance-version-summary"><strong>Version history</strong><p>{report.version_history.summary}</p>{report.version_history.added_headings.length > 0 && <small>Added: {report.version_history.added_headings.join(", ")}</small>}{report.version_history.removed_headings.length > 0 && <small>Removed: {report.version_history.removed_headings.join(", ")}</small>}</div>}</section></div>
    <div className="compliance-grid compliance-grid--bottom"><section className="compliance-card compliance-missing"><h2>Missing &amp; Misplaced Sections</h2>{report.missing_sections.length ? <div className="compliance-table">{report.missing_sections.map((item) => <div key={item.details}><b>{item.issue}</b><span>{item.details}</span></div>)}</div> : <p className="compliance-success">No missing required sections detected.</p>}</section><section className="compliance-card compliance-final"><h2>Final Results</h2><div className="compliance-final__stats"><span>Total Checks <b>{overall.total}</b></span><span>Passed <b>{overall.passed}</b></span><span>Failed <b>{overall.failed}</b></span><span>Review <b>{issues}</b></span></div><button type="button" onClick={() => void download()}>Download Detailed Report (PDF)</button><small>Template: {report.template.title} · Version {report.template.version}</small></section></div>
    <section className="compliance-card compliance-academic"><div className="compliance-card__row"><h2>Academic Consistency (Advisory)</h2><button type="button" onClick={() => void runAcademicAnalysis()} disabled={academicBusy}>{academicBusy ? "Analyzing..." : "Run Llama 3.2 analysis"}</button></div>{report.academic_analysis ? <><p><strong>{report.academic_analysis.consistency_score}% consistency</strong> · {report.academic_analysis.alignment_valid ? "Core sections align" : "Review alignment gaps"} · {report.academic_analysis.source === "AI" ? `AI: ${report.academic_analysis.model ?? "Llama 3.2"}` : "Deterministic fallback"}</p><p className="compliance-muted">{report.academic_analysis.executive_summary}</p>{report.academic_analysis.identified_gaps.map((gap) => <div className="compliance-category" key={`${gap.category}-${gap.issue_description}`}><strong>{gap.category}</strong><small>{gap.issue_description} {gap.recommendation}</small></div>)}</> : <p className="compliance-muted">No advisory analysis has been run yet. This does not change the deterministic compliance score.</p>}</section>
  </section>;
}
