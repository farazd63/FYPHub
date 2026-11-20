import { useState } from "react";

type Issue = { fingerprint: string; ruleCode: string; issue: string; category: string; status: string; section: string; pages: number[]; difference?: unknown };
type RemainingIssue = { previous: Issue; current: Issue };
type Comparison = {
  id: number;
  previousVersion: number;
  currentVersion: number;
  previousIssueCount: number;
  currentIssueCount: number;
  netIssueChange: number;
  previousScore: number | null;
  newScore: number | null;
  scoreDifference: number | null;
  overallResult: "Improved" | "Unchanged" | "Worse";
  fixedIssues: Issue[];
  remainingIssues: RemainingIssue[];
  worsenedIssues?: RemainingIssue[];
  newIssues: Issue[];
  unchangedIssues: Issue[];
  deterministicSummary: string;
  differentTemplateVersions: boolean;
  templateVersionMessage: string | null;
  aiSummary: string | null;
  aiStatus: string | null;
};

const value = (item: unknown) => item === null || item === undefined || item === "" ? "Not available" : Array.isArray(item) ? item.join(", ") || "Not available" : typeof item === "object" ? "Structured evidence" : String(item);
const pages = (issue: Issue) => issue.pages?.length ? issue.pages.map((page) => `Page ${page}`).join(", ") : "Document";

function IssueTable({ issues, remaining = false }: { issues: Issue[] | RemainingIssue[]; remaining?: boolean }) {
  const rows = remaining ? (issues as RemainingIssue[]).map((item) => item.current) : issues as Issue[];
  if (!rows.length) return <p className="module3-empty">No issues in this section.</p>;
  return <div className="module3-comparison-table-wrap"><table className="module3-comparison-table"><thead><tr><th>Issue</th><th>Rule</th><th>Section</th><th>Page</th><th>Status</th><th>Difference</th></tr></thead><tbody>{rows.map((issue) => <tr key={issue.fingerprint}><td data-label="Issue"><strong>{issue.issue}</strong><br /><span>{issue.category}</span></td><td data-label="Rule">{issue.ruleCode}</td><td data-label="Section">{value(issue.section)}</td><td data-label="Page"><span className="module3-page-chip">{pages(issue)}</span></td><td data-label="Status"><span className={`module3-status-pill module3-status-pill--${issue.status.toLowerCase()}`}>{issue.status}</span></td><td data-label="Difference">{value(issue.difference)}</td></tr>)}</tbody></table></div>;
}

function IssueGroup({ title, count, tone, issues, remaining = false }: { title: string; count: number; tone: string; issues: Issue[] | RemainingIssue[]; remaining?: boolean }) {
  return <section className={`module3-issue-group module3-issue-group--${tone}`}><div className="module3-issue-group__heading"><h2>{title}</h2><span className="module3-issue-count">{count}</span></div><IssueTable issues={issues} remaining={remaining} /></section>;
}

export function ProposalVersionComparison({ api, submissionId }: { api: string; submissionId: number }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const compare = async () => {
    setOpen(true); setLoading(true); setSummaryLoading(false); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/submissions/${submissionId}/comparison`, { credentials: "include" });
      const payload = await response.json().catch(() => ({})) as { status?: string; message?: string; comparison?: Comparison | null; detail?: string | { message?: string } };
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Version comparison could not be loaded.");
      if (payload.status === "NO_PREVIOUS_VERSION" || !payload.comparison) { setComparison(null); setMessage(payload.message || "No previous version available for comparison."); return; }
      setComparison(payload.comparison);
      if (!payload.comparison.aiSummary) {
        setSummaryLoading(true);
        const summaryResponse = await fetch(`${api}/api/v1/proposal-compliance/comparisons/${payload.comparison.id}/summary`, { method: "POST", credentials: "include" });
        const summaryPayload = await summaryResponse.json().catch(() => ({})) as Comparison;
        if (summaryResponse.ok) setComparison(summaryPayload);
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Version comparison could not be loaded."); } finally { setLoading(false); setSummaryLoading(false); }
  };

  return <div className="module3-version-comparison"><button type="button" className="module3-secondary-button" onClick={() => void compare()}>{open ? "Refresh comparison" : "Compare with Previous Version"}</button>{open && <div className="module3-version-comparison__body">{loading && <p className="module3-muted">Loading the previous audited version...</p>}{error && <p className="module3-alert module3-alert--error" role="alert">{error}</p>}{message && <p className="module3-alert module3-alert--success" role="status">{message}</p>}{comparison && <div className="module3-comparison-report"><div className="module3-report-meta"><div><h2>Version {comparison.previousVersion} → Version {comparison.currentVersion}</h2><p>Structured comparison of the two audited compliance reports.</p></div><dl><div><dt>Previous issues</dt><dd>{comparison.previousIssueCount}</dd></div><div><dt>Current issues</dt><dd>{comparison.currentIssueCount}</dd></div><div><dt>Net change</dt><dd>{comparison.netIssueChange > 0 ? "+" : ""}{comparison.netIssueChange}</dd></div></dl></div><div className="module3-summary-cards"><div className="module3-summary-card"><span>Previous score</span><strong>{comparison.previousScore ?? "—"}%</strong><small>Version {comparison.previousVersion}</small></div><div className="module3-summary-card"><span>Current score</span><strong>{comparison.newScore ?? "—"}%</strong><small>Version {comparison.currentVersion}</small></div><div className={`module3-summary-card ${comparison.scoreDifference !== null && comparison.scoreDifference < 0 ? "module3-summary-card--critical" : comparison.scoreDifference === 0 ? "module3-summary-card--warning" : "module3-summary-card--compliant"}`}><span>Score difference</span><strong>{comparison.scoreDifference === null ? "—" : `${comparison.scoreDifference > 0 ? "+" : ""}${comparison.scoreDifference}`}</strong><small>Percentage points</small></div><div className={`module3-summary-card module3-summary-card--status module3-summary-card--${comparison.overallResult.toLowerCase()}`}><span>Overall result</span><strong>{comparison.overallResult}</strong><small>Based on score and issue change</small></div></div>{comparison.differentTemplateVersions && <div className="module3-rule-banner"><strong>Template note</strong><span>{comparison.templateVersionMessage || "Comparison based on different template versions."}</span></div>}<div className="module3-compliance-layout"><div className="module3-issue-column"><IssueGroup title="Issues fixed" count={comparison.fixedIssues.length} tone="passed" issues={comparison.fixedIssues} /><IssueGroup title="Previous issues remaining" count={comparison.remainingIssues.length} tone="warning" issues={comparison.remainingIssues} remaining />{comparison.worsenedIssues && <IssueGroup title="Issues that became worse" count={comparison.worsenedIssues.length} tone="critical" issues={comparison.worsenedIssues} remaining />}<IssueGroup title="New issues introduced" count={comparison.newIssues.length} tone="critical" issues={comparison.newIssues} /><IssueGroup title="Unchanged issues" count={comparison.unchangedIssues.length} tone="warning" issues={comparison.unchangedIssues} /></div><aside className="module3-report-sidebar"><section className="module3-panel module3-difference-summary"><h2>AI comparison summary</h2>{summaryLoading ? <p>Generating a concise summary from the structured comparison...</p> : <p>{comparison.aiSummary || comparison.deterministicSummary}</p>}{comparison.aiStatus && <small className="module3-muted">Source: {comparison.aiStatus === "COMPLETED" ? "configured LLaMA proposal model" : "deterministic comparison fallback"}</small>}</section></aside></div></div>}</div>}</div>;
}
