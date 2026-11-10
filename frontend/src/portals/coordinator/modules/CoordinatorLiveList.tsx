import { useCallback, useEffect, useState } from "react";

type Row = Record<string, unknown> & { id?: number };

const readRows = (body: unknown): Row[] => {
  if (Array.isArray(body)) return body as Row[];
  if (body && typeof body === "object") {
    for (const key of ["items", "requirements", "results"]) {
      const value = (body as Record<string, unknown>)[key];
      if (Array.isArray(value)) return value as Row[];
    }
  }
  return [];
};

const display = (row: Row, keys: string[]) => keys.map((key) => row[key]).find((value) => value !== null && value !== undefined && value !== "") as string | number | undefined;

export function CoordinatorLiveList({ api, title, description, path, columns }: { api: string; title: string; description: string; path: string; columns: Array<{ label: string; keys: string[] }> }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    setState("loading"); setMessage("");
    try {
      const response = await fetch(`${api}${path}`, { credentials: "include" });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(response.status === 403 ? "Coordinator permission is required for this read-only view." : `The service returned HTTP ${response.status}.`);
      setRows(readRows(body)); setState("ready");
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "The coordinator service could not be reached."); setState("error"); }
  }, [api, path]);
  // Initial data loading is intentionally performed after mount.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  return <section className="student-phase-page" aria-labelledby={`${title}-heading`}><div className="student-page-heading"><p className="student-overview__eyebrow">Coordinator workspace</p><h1 id={`${title}-heading`}>{title}</h1><p>{description}</p></div>{state === "loading" && <p role="status" className="student-placeholder">Loading {title.toLowerCase()}…</p>}{state === "error" && <p role="alert" className="student-request-alert">{message}<button type="button" className="ml-3 underline" onClick={() => void load()}>Retry</button></p>}{state === "ready" && !rows.length && <p className="student-placeholder">No records are available for this authorized view.</p>}{state === "ready" && rows.length > 0 && <div className="mt-5 overflow-x-auto rounded-xl border bg-white"><table className="w-full min-w-[680px] text-left text-sm"><thead className="bg-slate-50"><tr>{columns.map((column) => <th className="px-4 py-3" key={column.label}>{column.label}</th>)}</tr></thead><tbody className="divide-y">{rows.map((row, index) => <tr key={row.id ?? index}>{columns.map((column) => <td className="px-4 py-3" key={column.label}>{String(display(row, column.keys) ?? "Not recorded")}</td>)}</tr>)}</tbody></table></div>}</section>;
}
