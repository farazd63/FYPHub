import { useCallback, useEffect, useRef, useState } from "react";
import { ArchivedProjectDetail } from "../ArchivedProjectDetail";
import { appPathname } from "../../../../platform-path";

type Result = {
  rank: number;
  id: number;
  title: string;
  short_summary: string;
  academic_year: string;
  session?: string;
  group_name?: string | null;
  supervisor_name?: string | null;
  domain?: string | null;
  technologies_used?: string | null;
  completion_percentage?: number | null;
  project_status?: string | null;
  project_scope: string;
  completion_stage: string;
  implemented_scope: string;
  remaining_gaps: string;
  available_documents_count: number;
  match_reason: string;
};
type Filters = {
  academic_year: string;
  session_name: string;
  department: string;
  supervisor: string;
  technology: string;
};

const yearValid = (value: string) =>
  !value.trim() || /^\d{4}$/.test(value.trim());
const projectRouteFromPath = () => {
  const match = appPathname().match(
    /^\/student\/search\/projects\/(\d+)$/,
  );
  if (!match) return null;
  const id = Number(match[1]);
  return Number.isInteger(id) && id > 0 ? id : null;
};

export function KnowledgeSearch({ api }: { api: string }) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>({
    academic_year: "",
    session_name: "",
    department: "",
    supervisor: "",
    technology: "",
  });
  const [results, setResults] = useState<Result[]>([]);
  const [selected] = useState<number | null>(() => projectRouteFromPath());
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [searchNonce, setSearchNonce] = useState(0);
  const requestId = useRef(0);

  const search = useCallback(async () => {
    if (!yearValid(filters.academic_year)) {
      setMessage("Academic year must be a four-digit year (for example 2026).");
      setResults([]);
      return;
    }
    const id = ++requestId.current;
    setLoading(true);
    setMessage("");
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      Object.entries(filters).forEach(([key, value]) => {
        if (value.trim()) params.set(key, value.trim());
      });
      const response = await fetch(
        `${api}/api/v1/archived-projects/search${params.toString() ? `?${params}` : ""}`,
        { credentials: "include" },
      );
      const body = await response.json().catch(() => ({}));
      if (id !== requestId.current) return;
      if (!response.ok)
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Knowledge search is unavailable.",
        );
      setResults(body.results as Result[]);
    } catch (error) {
      if (id !== requestId.current) return;
      setMessage(
        error instanceof Error
          ? error.message
          : "Knowledge search is unavailable.",
      );
      setResults([]);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [api, query, filters]);

  useEffect(() => {
    const timer = window.setTimeout(
      () => {
        void search();
      },
      searchNonce > 0 ? 0 : 300,
    );
    return () => window.clearTimeout(timer);
  }, [search, searchNonce]);

  if (selected !== null)
    return (
      <ArchivedProjectDetail
        api={api}
        projectId={selected}
      />
    );
  return (
    <section
      className="student-phase-page archive-knowledge-page"
      aria-labelledby="knowledge-search-heading"
    >
      <div className="student-page-heading">
        <p className="student-overview__eyebrow">Student research phase</p>
        <h1 id="knowledge-search-heading">
          FYP Knowledge Search &amp; Analytics
        </h1>
        <p>
          Search visible archived projects by title, keywords, year, session,
          department, supervisor, or technology.
        </p>
      </div>
      <div className="student-request-card">
        <form
          className="student-request-actions"
          onSubmit={(event) => {
            event.preventDefault();
            setSearchNonce((value) => value + 1);
          }}
        >
          <input
            className="student-request-input"
            aria-label="Search archived projects"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search title, keyword, or research area"
          />
          <button type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </button>
        </form>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {(
            [
              ["academic_year", "Academic year"],
              ["department", "Department"],
              ["supervisor", "Supervisor"],
              ["technology", "Technology"],
            ] as const
          ).map(([key, label]) => (
            <input
              key={key}
              aria-label={label}
              className="student-request-input"
              placeholder={label}
              value={filters[key]}
              onChange={(event) =>
                setFilters({ ...filters, [key]: event.target.value })
              }
            />
          ))}
          <select
            aria-label="Session"
            className="student-request-input"
            value={filters.session_name}
            onChange={(event) =>
              setFilters({ ...filters, session_name: event.target.value })
            }
          >
            <option value="">All sessions</option>
            <option value="FALL">Fall</option>
            <option value="SPRING">Spring</option>
          </select>
        </div>
        {!yearValid(filters.academic_year) && (
          <p className="student-request-alert" role="alert">
            Academic year must be a four-digit year.
          </p>
        )}
      </div>
      {message && (
        <p className="student-request-alert" role="alert">
          {message}
        </p>
      )}
      {!loading && !results.length ? (
        <div className="student-placeholder">
          No active archived projects matched this search.
        </div>
      ) : (
        <div className="archive-search-results">
          {results.map((result) => (
            <article
              className="student-request-card archive-result-card"
              key={result.id}
            >
              <span className="archive-result-rank">#{result.rank}</span>
              <div>
                <h2>{result.title}</h2>
                <p>{result.short_summary}</p>
                <small>
                  {result.academic_year} · {result.session ?? ""} ·{" "}
                  {result.project_scope} · {result.completion_stage} ·{" "}
                  {result.available_documents_count} documents
                </small>
                <p>
                  <strong>Match:</strong> {result.match_reason}
                </p>
                <p>
                  <strong>Implemented:</strong> {result.implemented_scope}
                </p>
                <p>
                  <strong>Remaining gaps:</strong> {result.remaining_gaps}
                </p>
                <button
                  type="button"
                  onClick={() =>
                    window.location.assign(`/student/search/projects/${result.id}`)
                  }
                >
                  Open project details
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
