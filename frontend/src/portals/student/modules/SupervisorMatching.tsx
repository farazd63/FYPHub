import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { IconButton } from "../../../ui/IconButton";
import "./supervisor-matching.css";

type Proposal = { id: number; proposal_key: string; title: string; version: number; status: string; analysis?: Analysis };
type Analysis = { status: string; preliminary: boolean; fields?: Record<string, unknown> | null; error_message?: string | null };
type Match = { id: number; rank: number; supervisor_name: string; final_score: number; ai_score?: number; deterministic_score?: number; score_components: Record<string, number>; explanation: { reasons: string[]; gaps: string[]; related_projects: Array<{ title: string; year?: number | null; summary?: string | null }>; confidence: number; ai_rationale?: string; ranking_method?: string } };
type MatchingLock = { locked: boolean; request_id: number | null; assignment_id: number | null; supervisor_id: number | null; supervisor_name: string | null; accepted_at: string | null; message: string | null };

async function readJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : body?.detail?.message || body?.message || "The request could not be completed.");
  return body as T;
}

export function SupervisorMatching({ api }: { api: string }) {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [rankingMethod, setRankingMethod] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [lock, setLock] = useState<MatchingLock>({ locked: false, request_id: null, assignment_id: null, supervisor_id: null, supervisor_name: null, accepted_at: null, message: null });
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadType, setUploadType] = useState<"SHORT" | "LONG">("SHORT");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [proposalKey, setProposalKey] = useState<string | null>(null);

  const chosen = useMemo(() => proposals.find((proposal) => proposal.id === selected), [proposals, selected]);
  const locked = lock.locked;

  const load = async () => {
    try {
      const current = await readJson<Proposal[]>(await fetch(`${api}/api/v1/supervisor-matching/proposals`, { credentials: "include" }));
      setProposals(current);
      setProposalKey(current[0]?.proposal_key ?? null);
      setSelected(current[0]?.id ?? null);
      setAnalysis(current[0]?.analysis ?? null);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Proposals could not be loaded."); }
  };
  const loadLock = async () => {
    try { setLock(await readJson<MatchingLock>(await fetch(`${api}/api/v1/supervisor-matching/lock-status`, { credentials: "include" })));
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Supervisor matching status could not be loaded."); }
  };
  useEffect(() => {
    void load();
    void loadLock();
    const refreshLock = () => void loadLock();
    window.addEventListener("focus", refreshLock);
    return () => window.removeEventListener("focus", refreshLock);
  }, [api]);

  const uploadProposal = async () => {
    if (locked || !uploadFile || !uploadTitle.trim()) return;
    setLoading(true); setError(""); setNotice("");
    try {
      const form = new FormData();
      form.append("proposal_type", uploadType);
      form.append("title", uploadTitle.trim());
      form.append("action", "submit");
      if (proposalKey) form.append("proposal_key", proposalKey);
      form.append("proposal_file", uploadFile);
      const result = await readJson<{ submission: Pick<Proposal, "id" | "proposal_key"> }>(await fetch(`${api}/api/v1/proposal-compliance/submissions`, { method: "POST", credentials: "include", body: form }));
      setProposalKey(result.submission.proposal_key);
      setUploadTitle(""); setUploadFile(null); setSelected(result.submission.id); setAnalysis(null); setMatches([]);
      setNotice("Proposal uploaded. Analyze it below to extract the topic, domain, skills, methods, and research area.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Proposal upload failed."); }
    finally { setLoading(false); }
  };

  const analyze = async () => {
    if (locked || !selected) return;
    setLoading(true); setError(""); setNotice("");
    try {
      const result = await readJson<Analysis>(await fetch(`${api}/api/v1/supervisor-matching/proposals/${selected}/analyze`, { method: "POST", credentials: "include" }));
      setAnalysis(result); setMatches([]); setNotice("Proposal analyzed. Review the extracted facts before requesting matches."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Analysis failed."); }
    finally { setLoading(false); }
  };

  const recommend = async () => {
    if (locked || !selected) return;
    setLoading(true); setError(""); setNotice("");
    try {
      const result = await readJson<{ results: Match[]; ranking_method?: string }>(await fetch(`${api}/api/v1/supervisor-matching/proposals/${selected}/recommendations`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ limit: 10 }) }));
      setMatches(result.results); setRankingMethod(result.ranking_method || ""); setNotice(result.results.length ? `Recommendations use verified profile evidence, derived supervision history, current capacity, and ${result.ranking_method === "llama3.1-assisted" ? "a fairness-constrained Llama 3.1 fit review" : "the deterministic fallback because the AI review was unavailable"}.` : "No eligible supervisors matched the current rules.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Matching failed."); }
    finally { setLoading(false); }
  };

  const requestSupervisor = async (matchId: number) => {
    if (locked) return;
    setLoading(true); setError("");
    try { await readJson(await fetch(`${api}/api/v1/supervisor-matching/recommendations/${matchId}/request`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ message: "I would like to discuss this proposal and supervision fit." }) })); setNotice("Supervision request submitted. The supervisor can accept or reject it from their request queue."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The request could not be submitted."); }
    finally { setLoading(false); }
  };

  return <section className="matching-page">
    <div className="matching-hero"><div><p className="matching-eyebrow">PROPOSAL TO SUPERVISOR</p><h1>Find a supervisor who fits the work</h1><p>Upload one proposal, let the system extract its signals, compare eligible supervisors, and send a request to your preferred match.</p></div><div className="matching-hero__mark" role="img" aria-label="AI fit"><span className="matching-hero__mark-main">AI</span><span className="matching-hero__mark-rule" aria-hidden="true" /><span className="matching-hero__mark-sub">FIT</span></div></div>
    {locked && <div className="matching-lock" role="status"><span className="matching-lock__icon" aria-hidden="true">✓</span><div><strong>Supervisor assignment confirmed</strong><p>Your request was accepted{lock.supervisor_name ? ` by ${lock.supervisor_name}` : ""}. Supervisor matching is now locked for this group.</p></div><span className="matching-lock__badge">LOCKED</span></div>}
    {error && <p className="matching-alert matching-alert--error" role="alert">{error}</p>}{notice && <p className="matching-alert" role="status">{notice}</p>}
    <div className="matching-layout">
      <article className="matching-card matching-card--proposals">
        <div className="matching-card__heading"><div><h2>Your project proposal</h2></div><IconButton label="Refresh current proposal" size="sm" variant="secondary" disabled={loading || locked} onClick={() => void load()}><RefreshCw size={15} strokeWidth={1.8} aria-hidden /></IconButton></div>
        <div className={`matching-upload ${locked ? "is-locked" : ""}`}><label>Project title<input value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} placeholder="Your final year project title" disabled={locked || loading} /></label><div className="matching-upload__fields"><label>Document type<select value={uploadType} onChange={(event) => setUploadType(event.target.value as "SHORT" | "LONG")} disabled={locked || loading}><option value="SHORT">Proposal / one-pager</option><option value="LONG">Long proposal</option></select></label><label>File<input type="file" accept=".pdf,.docx,.txt" onChange={(event) => setUploadFile(event.target.files?.[0] || null)} disabled={locked || loading} /></label></div><button type="button" className="matching-button" disabled={locked || loading || !uploadFile || !uploadTitle.trim()} onClick={() => void uploadProposal()}>Upload proposal</button></div>
        {!proposals.length ? <p className="matching-muted">Upload one proposal above to start the combined analysis and supervisor recommendation flow.</p> : <div className="matching-proposals">{proposals.map((proposal) => <button type="button" key={proposal.id} className={`matching-proposal ${selected === proposal.id ? "is-selected" : ""}`} disabled={locked || loading} onClick={() => { setSelected(proposal.id); setAnalysis(proposal.analysis ?? null); setMatches([]); setNotice(""); }}><span><strong>{proposal.title}</strong><small>Current version {proposal.version} · {proposal.status}</small></span><span className="matching-status">{proposal.analysis?.status ?? "Ready"}</span></button>)}</div>}
      </article>
      <article className="matching-card matching-card--analysis"><h2>Proposal understanding</h2>{chosen ? <><p className="matching-muted">{analysis?.preliminary ? "Preliminary analysis: confirm the proposal review before relying on a final decision." : "This analysis uses the latest stored proposal version."}</p><div className="matching-actions"><button type="button" className="matching-button" disabled={locked || loading} onClick={() => void analyze()}>{loading ? "Working..." : analysis?.status === "COMPLETED" ? "Re-analyze proposal" : "Analyze proposal"}</button><button type="button" className="matching-button matching-button--outline" disabled={locked || loading || analysis?.status !== "COMPLETED"} onClick={() => void recommend()}>Show matches</button></div>{analysis?.fields && <div className="matching-facts">{Object.entries(analysis.fields).filter(([, value]) => value && (!Array.isArray(value) || value.length)).map(([key, value]) => <div className="matching-fact" key={key}><span>{key.replaceAll("_", " ")}</span><strong>{Array.isArray(value) ? value.join(", ") : String(value)}</strong></div>)}</div>}</> : <p className="matching-muted">Select a proposal to start. Matching stays unavailable until extraction completes.</p>}</article>
    </div>
    <section className="matching-results"><div className="matching-card__heading"><div><h2>Recommended supervisors</h2></div><span className="matching-privacy">Verified profile · Capacity checked · History derived{matches.length > 0 && ` · ${rankingMethod === "llama3.1-assisted" ? "Llama 3.1 assisted" : "Deterministic fallback"}`}</span></div>{matches.length ? <div className="matching-result-grid">{matches.map((match) => <article className="matching-result" key={match.id}><div className="matching-result__top"><span className="matching-rank">#{match.rank}</span><div><h3>{match.supervisor_name}</h3><strong>{match.final_score.toFixed(1)}<small>/100 fit</small></strong></div></div><div className="matching-scorebar"><span style={{ width: `${Math.min(100, match.final_score)}%` }} /></div><div className="matching-components">{Object.entries(match.score_components).filter(([key]) => key !== "final_score").map(([key, value]) => <span key={key}>{key.replace("_score", "").replaceAll("_", " ")} <b>{value.toFixed(0)}</b></span>)}</div><ul className="matching-reasons">{match.explanation.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>{match.explanation.ai_rationale && <p className="matching-related">Llama 3.1 fit review: {match.explanation.ai_rationale}</p>}{match.explanation.related_projects.length > 0 && <p className="matching-related">Related history: {match.explanation.related_projects.map((project) => project.title).join(" · ")}</p>}{match.explanation.gaps.length > 0 && <p className="matching-gaps">Evidence gaps: {match.explanation.gaps.join(", ")}</p>}<button type="button" className="matching-button" disabled={locked || loading} onClick={() => void requestSupervisor(match.id)}>Request this supervisor</button></article>)}</div> : <div className="matching-empty"><span>o</span><p>{chosen && analysis?.status === "COMPLETED" ? "Click Show matches to see the current shortlist." : "Your explainable shortlist will appear here after proposal analysis."}</p></div>}</section>
  </section>;
}
