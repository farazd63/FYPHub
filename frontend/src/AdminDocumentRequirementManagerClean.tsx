import { useCallback, useEffect, useState } from "react";

type Cycle = { id: number; code: string; display_name: string };
type Requirement = { id: number; title: string; description?: string | null; academic_cycle_id: number; due_at: string; allowed_file_types: string[]; max_file_size_mb: number; is_required: boolean; status: string; submission_count?: number; created_at: string; updated_at: string };

const FIELD_MESSAGES: Record<string, Record<string, string>> = {
  max_file_size_mb: {
    greater_than_equal: "Max size must be at least 1 MB.",
    less_than_equal: "Max size must be at most 100 MB.",
    int_parsing: "Max size must be a whole number of megabytes.",
    missing: "Max size is required.",
  },
  title: { missing: "Requirement name is required.", string_too_short: "Requirement name is required." },
  due_at: { missing: "Deadline is required.", datetime_parsing: "Deadline must be a valid date and time." },
  academic_cycle_id: { missing: "Academic cycle is required." },
};

const errorText = (body: unknown, fallback: string) => {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const payload = detail as { message?: unknown; fields?: Array<{ path?: string; code?: string }> };
    if (Array.isArray(payload.fields) && payload.fields.length) {
      const parts = payload.fields.map((field) => {
        const path = (field.path || "").split(".").pop() || "";
        const mapped = FIELD_MESSAGES[path]?.[field.code || ""];
        if (mapped) return mapped;
        if (path && field.code) return `${path}: ${field.code.replaceAll("_", " ")}`;
        return "";
      }).filter(Boolean);
      if (parts.length) return parts.join(" ");
    }
    if (typeof payload.message === "string" && payload.message.trim()) return payload.message;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const entry = item as { loc?: unknown[]; msg?: unknown };
        const field = Array.isArray(entry.loc) ? entry.loc.filter((part) => part !== "body").join(".") : "";
        const msg = typeof entry.msg === "string" ? entry.msg : "";
        return field && msg ? `${field}: ${msg}` : msg;
      })
      .filter(Boolean);
    if (parts.length) return parts.join(" ");
  }
  return fallback;
};

export function AdminDocumentRequirementManagerClean({ api }: { api: string }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [items, setItems] = useState<Requirement[]>([]);
  const [cycleId, setCycleId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | "create" | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cycleResponse, requirementResponse] = await Promise.all([
        fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" }),
        fetch(`${api}/api/v1/document-requirements`, { credentials: "include" }),
      ]);
      const cycleBody = await cycleResponse.json().catch(() => []);
      const requirementBody = await requirementResponse.json().catch(() => []);
      if (!cycleResponse.ok || !requirementResponse.ok) throw new Error(errorText(cycleResponse.ok ? requirementBody : cycleBody, "Requirements could not be loaded."));
      const available = Array.isArray(cycleBody) ? cycleBody as Cycle[] : [];
      setCycles(available);
      setCycleId((current) => current || (available[0] ? String(available[0].id) : ""));
      setItems(Array.isArray(requirementBody) ? requirementBody as Requirement[] : []);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Requirements could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);

  const request = async (method: string, url: string, body?: object) => {
    const response = await fetch(url, { method, credentials: "include", headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorText(result, "The requirement request could not be completed."));
    return result;
  };

  const create = async () => {
    if (!title.trim() || !cycleId || !deadline) { setNotice("Title, academic cycle, and deadline are required."); return; }
    setBusy("create"); setNotice("");
    try {
      await request("POST", `${api}/api/v1/document-requirements`, { title: title.trim(), description: description.trim() || null, academic_cycle_id: Number(cycleId), module: "General", visible_to_roles: ["STUDENT"], allowed_file_types: ["pdf", "doc", "docx"], max_file_size_mb: 10, due_at: new Date(deadline).toISOString(), is_required: true });
      setTitle(""); setDescription(""); setDeadline(""); setNotice("Requirement saved as draft."); await load();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Requirement could not be created."); }
    finally { setBusy(null); }
  };

  const action = async (item: Requirement, name: "publish" | "archive" | "reopen" | "delete") => {
    if (name === "delete" && !window.confirm(`Delete draft requirement “${item.title}”?`)) return;
    setBusy(item.id); setNotice("");
    try {
      if (name === "delete") await request("DELETE", `${api}/api/v1/document-requirements/${item.id}`);
      else await request("POST", `${api}/api/v1/document-requirements/${item.id}/${name}`);
      setNotice(name === "delete" ? "Requirement deleted." : `Requirement ${name}d.`); await load();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Requirement action failed."); }
    finally { setBusy(null); }
  };

  const visibleItems = cycleId ? items.filter((item) => item.academic_cycle_id === Number(cycleId)) : items;
  return <section aria-label="Required Documents" className="mx-auto w-full max-w-5xl"><h1 className="text-3xl font-bold">Required Documents</h1><p className="mt-1 text-slate-600">Create and manage student document requirements by academic cycle.</p>{notice && <p role="status" className="mt-4 rounded-lg bg-[#eef5ff] p-3 text-sm text-[#315db4]">{notice}</p>}<form className="mt-6 grid gap-4 rounded-2xl border bg-white p-6" onSubmit={(event) => { event.preventDefault(); void create(); }}><h2 className="text-xl font-semibold">Create document requirement</h2><label className="grid gap-1">Document title<input required value={title} onChange={(event) => setTitle(event.target.value)} className="rounded border p-3" /></label><label className="grid gap-1">Academic cycle<select required value={cycleId} onChange={(event) => setCycleId(event.target.value)} className="rounded border p-3"><option value="">Select cycle</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name}{cycle.code ? ` (${cycle.code})` : ""}</option>)}</select></label><label className="grid gap-1">Instructions<textarea value={description} onChange={(event) => setDescription(event.target.value)} className="rounded border p-3" rows={3} /></label><label className="grid gap-1">Deadline<input required type="datetime-local" value={deadline} onChange={(event) => setDeadline(event.target.value)} className="rounded border p-3" /></label><div className="flex flex-wrap gap-2"><button type="submit" disabled={busy !== null} className="rounded bg-slate-700 px-4 py-3 font-semibold text-white">{busy === "create" ? "Saving…" : "Save Draft"}</button></div></form><section className="mt-6 rounded-2xl border bg-white p-6"><h2 className="text-xl font-semibold">Existing document requirements</h2>{loading ? <p className="mt-3">Loading requirements…</p> : !visibleItems.length ? <p className="mt-3">No document requirements created yet for this cycle.</p> : <div className="mt-3 grid gap-3">{visibleItems.map((item) => <article key={item.id} className="rounded border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{item.title}</h3><p className="text-sm">Cycle {item.academic_cycle_id} · {item.status} · Due {new Date(item.due_at).toLocaleString()}</p><p className="text-sm">Submissions: {item.submission_count ?? 0}</p></div><div className="flex flex-wrap gap-2">{item.status === "DRAFT" && <><button type="button" disabled={busy === item.id} onClick={() => void action(item, "publish")} className="rounded border px-3 py-1 text-sm">Publish</button><button type="button" disabled={busy === item.id} onClick={() => void action(item, "delete")} className="rounded border border-red-200 px-3 py-1 text-sm text-red-700">Delete</button></>}{item.status !== "ARCHIVED" && item.status !== "DRAFT" && <button type="button" disabled={busy === item.id} onClick={() => void action(item, "archive")} className="rounded border px-3 py-1 text-sm">Archive</button>}{item.status === "ARCHIVED" && <button type="button" disabled={busy === item.id} onClick={() => void action(item, "reopen")} className="rounded border px-3 py-1 text-sm">Reopen</button>}</div></div></article>)}</div>}</section></section>;
}
