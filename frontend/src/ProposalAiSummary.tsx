import { useCallback, useEffect, useState } from "react";

export type ProposalSummary = {
  status: string;
  summary?: string;
  model?: string;
  source?: string;
  generated_at?: string;
  message?: string;
  summary_word_count?: number;
};
type SummaryResponse = Partial<ProposalSummary> & { detail?: string | { message?: string } };

type ProposalAiSummaryProps = {
  api: string;
  requestId: number;
  documentId?: number;
  initialSummary?: ProposalSummary | null;
  autoGenerate?: boolean;
  endpoint?: string;
  revision?: number;
};

const cacheKeyFor = (api: string, requestId: number, endpoint?: string, revision = 0) =>
  `fyphub.ai-summary:${api}:${endpoint ?? requestId}:r${revision}`;

export function ProposalAiSummary(props: ProposalAiSummaryProps) {
  const { api, requestId, initialSummary, autoGenerate = true, endpoint, revision = 0 } = props;
  const cacheKey = cacheKeyFor(api, requestId, endpoint, revision);
  const [result, setResult] = useState<ProposalSummary | null>(() => {
    if (initialSummary?.status === "COMPLETED" && initialSummary.summary) return initialSummary;
    try {
      const cached = sessionStorage.getItem(cacheKey);
      if (!cached) return null;
      const parsed = JSON.parse(cached) as ProposalSummary;
      return parsed?.status === "COMPLETED" && parsed.summary ? parsed : null;
    } catch {
      return null;
    }
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const generate = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${api}${endpoint ?? `/api/v1/supervisor-requests/${requestId}/ai-summary`}`, { method: "POST", credentials: "include" });
      const raw = await response.text();
      let body: SummaryResponse = {};
      try {
        body = raw.trim() ? JSON.parse(raw) as SummaryResponse : {};
      } catch {
        throw new Error(`The summary service returned an invalid response (HTTP ${response.status}). Please retry.`);
      }
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "AI summary could not be generated.");
      const summary = body as ProposalSummary;
      setResult(summary);
      try {
        sessionStorage.setItem(cacheKey, JSON.stringify(summary));
      } catch {
        /* ignore quota */
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI summary is unavailable.");
    } finally {
      setBusy(false);
    }
  }, [api, requestId, endpoint, cacheKey]);

  useEffect(() => {
    if (!autoGenerate) return;
    if (result?.status === "COMPLETED" && result.summary) return;
    const timer = window.setTimeout(() => void generate(), 0);
    return () => window.clearTimeout(timer);
  }, [autoGenerate, generate, result]);

  return <section className="proposal-ai-summary fy-card fy-card--pad-md" aria-label="Report summary">
    <h3 className="proposal-ai-summary__title">Report summary</h3>
    {busy ? <p className="proposal-ai-summary__body" role="status">Summarizing the report...</p> : result?.status === "COMPLETED" && result.summary ? <p className="proposal-ai-summary__body proposal-ai-summary__text">{result.summary}</p> : <><p className="proposal-ai-summary__body" role="status">{error || result?.message || "Generate a concise summary from the report content."}</p><button type="button" className="fy-btn fy-btn--secondary fy-btn--sm" onClick={() => void generate()}>{result || error ? "Retry report summary" : "Generate report summary"}</button></>}
  </section>;
}
