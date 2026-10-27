import { useState } from "react";

type SearchResult = { id: number; match_type: string; title: string; academic_year: string; short_summary: string; category_scope: string; source_label: string; pdf_available: boolean; pdf_url: string | null };

export function ProposalReferenceSearch({ api }: { api: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [message, setMessage] = useState("");
  const [matchType, setMatchType] = useState("");
  const [busy, setBusy] = useState(false);
  const search = async () => {
    if (!query.trim() || busy) return;
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-references/search?q=${encodeURIComponent(query.trim())}`, { credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Reference search is unavailable.");
      setResults(body.results as SearchResult[]); setMatchType(body.match_type as string);
    } catch (error) { setResults([]); setMatchType(""); setMessage(error instanceof Error ? error.message : "Reference search is unavailable."); }
    finally { setBusy(false); }
  };
  return <section className="student-request-card" aria-labelledby="proposal-reference-search-heading"><h2 id="proposal-reference-search-heading">Proposal reference search</h2><p className="student-request-muted">Advisory title search only. Similar titles do not block submission; semantic analysis is unavailable.</p><form className="student-request-actions" onSubmit={(event) => { event.preventDefault(); void search(); }}><input className="student-request-input" aria-label="Proposal title search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search proposal title" /><button type="submit" disabled={busy || !query.trim()}>{busy ? "Searching…" : "Search"}</button></form>{message && <p className="student-request-alert" role="alert">{message}</p>}{matchType === "no_close_match" && <p className="student-request-muted">No close title match found.</p>}{results.length > 0 && <div className="student-reference-results" aria-live="polite">{results.map((result) => <article key={result.id}><strong>{result.title}</strong><small>{result.academic_year} · {result.category_scope} · {result.match_type === "exact_title_match" ? "Exact title match" : "Possible similar title"}</small><p>{result.short_summary}</p><small>Source: {result.source_label}</small>{result.pdf_available && result.pdf_url && <a className="student-request-document-link" href={`${api}${result.pdf_url}`} target="_blank" rel="noreferrer">Open reference PDF</a>}</article>)}</div>}</section>;
}
