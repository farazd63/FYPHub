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
};

export function ProposalAiSummary(props: ProposalAiSummaryProps) {
  const { api, requestId, initialSummary, autoGenerate = true, endpoint } = props;
  const [result, setResult] = useState<ProposalSummary | null>(initialSummary ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const generate = useCallback(async () => {
    setBusy(true);
    setError("");
    setResult(null);
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
      setResult(body as ProposalSummary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI summary is unavailable.");
    } finally {
      setBusy(false);
    }
  }, [api, requestId, endpoint]);

  useEffect(() => {
    if (!autoGenerate) return;
    const timer = window.setTimeout(() => void generate(), 0);
    return () => window.clearTimeout(timer);
  }, [generate, autoGenerate]);

  return <section className="rounded-xl border p-4 my-4" aria-label="Report summary">
    <h3>Report summary</h3>
    {busy ? <p role="status">Summarizing the report...</p> : result?.status === "COMPLETED" && result.summary ? <p className="whitespace-pre-wrap">{result.summary}</p> : <><p role="status">{error || result?.message || "Generate a concise summary from the report content."}</p><button type="button" onClick={() => void generate()}>{result || error ? "Retry report summary" : "Generate report summary"}</button></>}
  </section>;
}
