import { useCallback, useEffect, useRef, useState } from "react";

type Transition = { label: string; source: string; destination: string };
type Version = { id: number; version_number: number; name: string; states: string[]; transitions: Transition[]; created_at: string };
type Detail = { id: number; versions: Version[] };
type Summary = { id: number; name: string; latest_version_number: number };
type Form = { name: string; states: string[]; transitions: Transition[] };
const blank = (): Form => ({ name: "", states: [""], transitions: [] });
const input = "w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm text-[#243746] focus:border-[#176b66] disabled:bg-[#f4f6f4]";
const button = "rounded-lg border border-[#b8cdc1] px-3 py-2 text-sm font-semibold text-[#176b66] hover:bg-[#e4eee7] disabled:opacity-50";

export function AdminWorkflowPolicies({ api }: { api: string }) {
  const [items, setItems] = useState<Summary[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [selected, setSelected] = useState<Detail | null>(null);
  const [form, setForm] = useState<Form>(blank);
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const requestId = useRef(0);
  const load = useCallback(async () => {
    setState("loading");
    try { const response = await fetch(`${api}/api/v1/admin/workflow-policies`, { credentials: "include" }); if (!response.ok) throw new Error(); setItems(await response.json() as Summary[]); setState("ready"); }
    catch { setState("error"); }
  }, [api]);
  useEffect(() => { const ref = requestId; const timer = window.setTimeout(() => void load(), 0); return () => { window.clearTimeout(timer); ref.current++; }; }, [load]);
  const open = async (id: number, populate = true) => {
    const token = ++requestId.current; setHistoryLoading(true); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/admin/workflow-policies/${id}`, { credentials: "include" });
      if (!response.ok) throw new Error("History could not be loaded.");
      const data = await response.json() as Detail;
      if (token !== requestId.current) return;
      setSelected(data);
      if (populate) { const latest = data.versions.at(-1); if (latest) setForm({ name: latest.name, states: [...latest.states], transitions: latest.transitions.map(t => ({ ...t })) }); }
    } catch (err) { if (token === requestId.current) { setIsError(true); setMessage(err instanceof Error ? err.message : "History could not be loaded."); } }
    finally { if (token === requestId.current) setHistoryLoading(false); }
  };
  const reset = () => { requestId.current++; setHistoryLoading(false); setSelected(null); setForm(blank()); setMessage(""); };
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); if (saving || historyLoading) return;
    const states = form.states.map(s => s.trim());
    const transitions = form.transitions.map(t => ({ label: t.label.trim(), source: t.source, destination: t.destination }));
    if (!form.name.trim() || states.some(s => !s) || new Set(states.map(s => s.toLocaleLowerCase())).size !== states.length || transitions.some(t => !t.label || !states.includes(t.source) || !states.includes(t.destination))) {
      setIsError(true); setMessage("Enter a name and unique state labels. Every transition needs a label and states from this draft."); return;
    }
    setSaving(true); setMessage("");
    try {
      const path = selected ? `/${selected.id}/versions` : "";
      const response = await fetch(`${api}/api/v1/admin/workflow-policies${path}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: form.name.trim(), states, transitions }) });
      if (!response.ok) { if (response.status === 422) throw new Error("Review the draft labels and transitions."); throw new Error("Draft could not be saved."); }
      const body = await response.json() as Detail;
      await load(); await open(selected?.id ?? body.id, false);
      setIsError(false); setMessage("Draft version saved. Earlier versions remain unchanged.");
    } catch (err) { setIsError(true); setMessage(err instanceof Error ? err.message : "Draft could not be saved."); }
    finally { setSaving(false); }
  };
  return <section aria-labelledby="workflow-heading">
    <div className="mb-5"><h1 id="workflow-heading" className="text-2xl font-bold">Workflow Policies</h1><p className="mt-1 text-sm text-[#60716b]">Draft configuration only. Saving a draft does not execute transitions.</p></div>
    {message && <p role={isError ? "alert" : "status"} className={`mb-4 rounded-lg px-3 py-2 text-sm ${isError ? "bg-[#fff3f0] text-[#a43a33]" : "bg-[#e4eee7] text-[#176b66]"}`}>{message}</p>}
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
      <div className="min-w-0 space-y-5"><div className="rounded-xl border border-[#dce4de] bg-white p-5"><div className="flex items-center justify-between"><h2 className="font-bold">Draft policies</h2><button type="button" disabled={saving} onClick={reset} className={button}>New draft</button></div>
        {state === "loading" && <p className="mt-4 text-sm">Loading drafts...</p>}{state === "error" && <p role="alert" className="mt-4 text-sm">Drafts could not be loaded. <button type="button" onClick={() => void load()} className="underline">Retry</button></p>}{state === "ready" && items.length === 0 && <p className="mt-4 text-sm text-[#60716b]">No workflow drafts have been configured.</p>}
        {items.map(item => <button key={item.id} type="button" disabled={saving} onClick={() => void open(item.id)} className="mt-3 flex w-full justify-between rounded-lg border border-[#e8ede9] p-3 text-left text-sm hover:bg-[#f4f8f5]"><span><b>{item.name}</b><span className="block text-xs text-[#60716b]">Draft version {item.latest_version_number}</span></span><span className="text-[#176b66]">History</span></button>)}
      </div>{historyLoading && <p role="status">Loading history...</p>}{selected && <div className="rounded-xl border border-[#dce4de] bg-white p-5"><h2 className="font-bold">Complete draft history</h2>{selected.versions.map(v => <article key={v.id} className="mt-4 rounded-lg border border-[#e8ede9] p-4"><b>Version {v.version_number}: {v.name}</b><p className="mt-2 text-sm"><strong>States:</strong> {v.states.join(", ")}</p><p className="mt-2 text-sm font-semibold">Transitions</p>{v.transitions.length ? <ul className="list-disc pl-5 text-sm">{v.transitions.map((t, i) => <li key={i}>{t.label}: {t.source} → {t.destination}</li>)}</ul> : <p className="text-sm text-[#60716b]">No transitions entered.</p>}</article>)}</div>}</div>
      <form onSubmit={save} className="h-fit rounded-xl border border-[#dce4de] bg-white p-5"><h2 className="font-bold">{selected ? "Create next version" : "Create draft"}</h2><p className="mt-1 text-xs text-[#60716b]">Enter your own state and transition labels.</p>
        <fieldset disabled={saving || historyLoading} className="mt-4 grid gap-4"><label className="grid gap-1 text-sm font-semibold">Policy name<input required maxLength={160} className={input} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}/></label>
          <div className="grid gap-2"><h3 className="text-sm font-bold">States</h3>{form.states.map((s, i) => <div key={i} className="flex gap-2"><label className="flex-1 text-sm">State {i + 1}<input required maxLength={160} className={input} value={s} onChange={e => setForm({ ...form, states: form.states.map((v, n) => n === i ? e.target.value : v) })}/></label><button type="button" disabled={form.states.length === 1} onClick={() => setForm({ ...form, states: form.states.filter((_, n) => n !== i) })} className={button}>Remove</button></div>)}<button type="button" disabled={form.states.length >= 100} onClick={() => setForm({ ...form, states: [...form.states, ""] })} className={button}>Add state</button></div>
          <div className="grid gap-3"><h3 className="text-sm font-bold">Transitions</h3>{form.transitions.map((t, i) => <div key={i} className="grid gap-2 rounded-lg border border-[#e8ede9] p-3">{(["label", "source", "destination"] as const).map(field => <label key={field} className="grid gap-1 text-sm capitalize">{field}<input required maxLength={160} className={input} value={t[field]} onChange={e => setForm({ ...form, transitions: form.transitions.map((v, n) => n === i ? { ...v, [field]: e.target.value } : v) })}/></label>)}<button type="button" onClick={() => setForm({ ...form, transitions: form.transitions.filter((_, n) => n !== i) })} className={button}>Remove transition</button></div>)}<button type="button" disabled={form.transitions.length >= 200} onClick={() => setForm({ ...form, transitions: [...form.transitions, { label: "", source: "", destination: "" }] })} className={button}>Add transition</button></div>
          <button className="rounded-lg bg-[#176b66] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving..." : "Save draft version"}</button>
        </fieldset>
      </form>
    </div>
  </section>;
}
