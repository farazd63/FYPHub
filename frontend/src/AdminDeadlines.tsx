import { useCallback, useEffect, useRef, useState } from "react";

type Cycle = { id: number; code: string; display_name: string };
type Preview = { local_due_at: string; time_zone: string; utc_offset: string; due_at_utc: string };
type Summary = Preview & { id: number; academic_cycle_id: number; academic_cycle_name: string; name: string; description: string | null; latest_version_number: number };
type Version = Preview & { id: number; version_number: number; name: string; description: string | null; created_at: string };
type Detail = { id: number; academic_cycle_id: number; academic_cycle_name: string; created_at: string; versions: Version[] };
type Form = { academic_cycle_id: string; name: string; description: string; local_due_at: string; time_zone: string; utc_offset: string };
type ApiDetail = { code?: string; message?: string; fields?: { path: string }[]; valid_offsets?: string[] };

const input = "w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm text-[#243746] focus:border-[#176b66] disabled:cursor-not-allowed disabled:bg-[#f4f6f4]";
const emptyForm = (): Form => ({ academic_cycle_id: "", name: "", description: "", local_due_at: "", time_zone: "", utc_offset: "" });
const apiDetail = (body: unknown): ApiDetail => typeof (body as { detail?: unknown })?.detail === "object" ? (body as { detail: ApiDetail }).detail : { message: typeof (body as { detail?: unknown })?.detail === "string" ? String((body as { detail: unknown }).detail) : undefined };
const displayInstant = (value: string) => new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC", timeZoneName: "short" }).format(new Date(value));

export function AdminDeadlines({ api }: { api: string }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [cycles, setCycles] = useState<Cycle[]>([]), [zones, setZones] = useState<string[]>([]), [deadlines, setDeadlines] = useState<Summary[]>([]);
  const [filterCycle, setFilterCycle] = useState("");
  const [selected, setSelected] = useState<Detail | null>(null), [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [form, setForm] = useState<Form>(emptyForm), [preview, setPreview] = useState<Preview | null>(null), [offsets, setOffsets] = useState<string[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({}), [message, setMessage] = useState(""), [messageIsError, setMessageIsError] = useState(false);
  const [previewing, setPreviewing] = useState(false), [saving, setSaving] = useState(false);
  const detailRequest = useRef(0), listRequest = useRef(0);

  const loadDeadlines = useCallback(async (cycleId: string) => {
    const token = ++listRequest.current;
    try {
      const query = cycleId ? `?academic_cycle_id=${encodeURIComponent(cycleId)}` : "";
      const response = await fetch(`${api}/api/v1/admin/academic-deadlines${query}`, { credentials: "include" });
      if (!response.ok) throw new Error();
      const rows = await response.json() as Summary[];
      if (token === listRequest.current) setDeadlines(rows);
    } catch {
      if (token === listRequest.current) throw new Error("Deadline configurations could not be loaded.");
    }
  }, [api]);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [cycleResponse, zoneResponse] = await Promise.all([
        fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" }),
        fetch(`${api}/api/v1/admin/time-zones`, { credentials: "include" }),
      ]);
      if (!cycleResponse.ok || !zoneResponse.ok) throw new Error();
      setCycles(await cycleResponse.json() as Cycle[]);
      setZones(await zoneResponse.json() as string[]);
      await loadDeadlines("");
      setState("ready");
    } catch {
      setState("error");
    }
  }, [api, loadDeadlines]);

  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [load]);

  const invalidatePreview = (changes: Partial<Form>, clearOffset = false) => {
    setForm((current) => ({ ...current, ...changes, ...(clearOffset ? { utc_offset: "" } : {}) }));
    setPreview(null); setOffsets([]); setErrors({}); setMessage("");
  };

  const previewTime = async () => {
    if (!form.local_due_at || !form.time_zone) { setErrors({ local_due_at: "Enter a local date/time and select a timezone." }); return; }
    setPreviewing(true); setMessage(""); setMessageIsError(false);
    try {
      const response = await fetch(`${api}/api/v1/admin/academic-deadlines/preview`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ local_due_at: form.local_due_at, time_zone: form.time_zone, utc_offset: form.utc_offset || null }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = apiDetail(body);
        if (detail.valid_offsets?.length) setOffsets(detail.valid_offsets);
        throw new Error(detail.message ?? "The deadline time could not be resolved.");
      }
      const value = body as Preview;
      setPreview(value); setOffsets([value.utc_offset]); setForm((current) => ({ ...current, utc_offset: value.utc_offset })); setErrors({}); setMessage("Server validation complete. Review the local and UTC times before saving.");
    } catch (error) {
      setMessageIsError(true); setMessage(error instanceof Error ? error.message : "The deadline time could not be resolved.");
    } finally { setPreviewing(false); }
  };

  const openDeadline = async (deadlineId: number, populate = true) => {
    const token = ++detailRequest.current; setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/admin/academic-deadlines/${deadlineId}`, { credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiDetail(body).message ?? "Deadline history could not be loaded.");
      if (token !== detailRequest.current) return;
      const detail = body as Detail, latest = detail.versions.at(-1);
      setSelected(detail); setSelectedVersion(latest?.id ?? null);
      if (populate && latest) {
        setForm({ academic_cycle_id: String(detail.academic_cycle_id), name: latest.name, description: latest.description ?? "", local_due_at: latest.local_due_at, time_zone: latest.time_zone, utc_offset: latest.utc_offset });
        setPreview({ local_due_at: latest.local_due_at, time_zone: latest.time_zone, utc_offset: latest.utc_offset, due_at_utc: latest.due_at_utc }); setOffsets([latest.utc_offset]); setErrors({});
      }
    } catch (error) { if (token === detailRequest.current) { setMessageIsError(true); setMessage(error instanceof Error ? error.message : "Deadline history could not be loaded."); } }
  };

  const selectFilter = async (value: string) => { setFilterCycle(value); try { await loadDeadlines(value); } catch (error) { setMessageIsError(true); setMessage(error instanceof Error ? error.message : "Deadline configurations could not be loaded."); } };
  const startNew = () => { detailRequest.current += 1; setSelected(null); setSelectedVersion(null); setForm({ ...emptyForm(), academic_cycle_id: filterCycle }); setPreview(null); setOffsets([]); setErrors({}); setMessage(""); };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (saving) return;
    const next: Record<string, string> = {};
    if (!form.academic_cycle_id) next.academic_cycle_id = "Select an academic cycle.";
    if (!form.name.trim()) next.name = "Enter a deadline name.";
    if (!preview) next.preview = "Validate the local and UTC time before saving.";
    if (Object.keys(next).length) { setErrors(next); return; }
    setSaving(true); setMessage(""); setMessageIsError(false);
    const payload = { name: form.name.trim(), description: form.description.trim() || null, local_due_at: preview!.local_due_at, time_zone: preview!.time_zone, utc_offset: preview!.utc_offset, due_at_utc: preview!.due_at_utc };
    const bodyPayload = selected ? payload : { academic_cycle_id: Number(form.academic_cycle_id), ...payload };
    const path = selected ? `/api/v1/admin/academic-deadlines/${selected.id}/versions` : "/api/v1/admin/academic-deadlines";
    try {
      const response = await fetch(`${api}${path}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(bodyPayload) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = apiDetail(body), mapped: Record<string, string> = {};
        detail.fields?.forEach(({ path: field }) => { mapped[field] = "Review this value."; }); setErrors(mapped);
        throw new Error(detail.message ?? "The deadline configuration could not be saved.");
      }
      const deadlineId = selected?.id ?? (body as Detail).id;
      await loadDeadlines(filterCycle); await openDeadline(deadlineId, false);
      setMessage(selected ? "New deadline configuration version created. Earlier history is unchanged." : "Deadline configuration created.");
    } catch (error) { setMessageIsError(true); setMessage(error instanceof Error ? error.message : "The deadline service is unavailable."); }
    finally { setSaving(false); }
  };

  const shownVersion = selected?.versions.find((version) => version.id === selectedVersion);

  return <section aria-labelledby="deadlines-heading"><div className="mb-5"><h1 id="deadlines-heading" className="text-2xl font-bold tracking-tight">Academic Deadlines</h1><p className="mt-1 text-sm text-[#60716b]">Configure recorded deadline dates only. This does not enforce submissions, send reminders, or execute escalations.</p></div>
    {message && <p role={messageIsError ? "alert" : "status"} className={`mb-4 rounded-lg px-3 py-2 text-sm ${messageIsError ? "bg-[#fff3f0] text-[#a43a33]" : "bg-[#e4eee7] text-[#176b66]"}`}>{message}</p>}
    {state === "loading" && <div className="rounded-xl border border-[#dce4de] bg-white p-5 text-sm text-[#60716b]">Loading deadline configuration...</div>}
    {state === "error" && <div role="alert" className="rounded-xl border border-[#e6c8c3] bg-[#fff3f0] p-5 text-sm text-[#a43a33]">Deadline configuration could not be loaded. <button type="button" className="underline" onClick={() => void load()}>Try again</button>.</div>}
    {state === "ready" && <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_400px]"><div className="min-w-0 space-y-5"><div className="rounded-xl border border-[#dce4de] bg-white p-5"><div className="flex flex-wrap items-end justify-between gap-3"><label className="grid min-w-[220px] gap-1 text-sm font-semibold">Filter by academic cycle<select className={input} value={filterCycle} onChange={(event) => void selectFilter(event.target.value)}><option value="">All cycles</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name} ({cycle.code})</option>)}</select></label><button type="button" onClick={startNew} className="rounded-lg border border-[#b8cdc1] px-3 py-2.5 text-sm font-semibold text-[#176b66] hover:bg-[#e4eee7]">New deadline</button></div>{!deadlines.length ? <p className="mt-4 rounded-lg border border-dashed border-[#cbd6d0] p-4 text-sm text-[#60716b]">No deadline configurations exist for this selection.</p> : deadlines.map((deadline) => <button key={deadline.id} type="button" onClick={() => void openDeadline(deadline.id)} className="mt-3 flex w-full flex-wrap items-center justify-between gap-3 rounded-lg border border-[#e8ede9] p-3 text-left text-sm hover:bg-[#f4f8f5]"><span><b>{deadline.name}</b><span className="mt-1 block text-xs text-[#60716b]">{deadline.academic_cycle_name} · latest recorded version {deadline.latest_version_number}</span><span className="mt-1 block text-xs text-[#60716b]">{deadline.local_due_at.replace("T", " ")} {deadline.utc_offset} · {deadline.time_zone}</span></span><span className="text-xs font-semibold text-[#176b66]">Open history</span></button>)}</div>
      {selected && <div className="rounded-xl border border-[#dce4de] bg-white p-5"><h2 className="font-bold">Complete configuration history</h2><p className="mt-1 text-xs text-[#60716b]">Latest means most recently recorded, not approved or operationally active.</p><div className="mt-4 flex flex-wrap gap-2">{selected.versions.map((version) => <button key={version.id} type="button" aria-pressed={selectedVersion === version.id} onClick={() => setSelectedVersion(version.id)} className={`rounded-lg border px-3 py-2 text-sm font-semibold ${selectedVersion === version.id ? "border-[#4663ff] bg-[#eef0ff] text-[#4663ff]" : "border-[#dce4de]"}`}>Version {version.version_number}</button>)}</div>{shownVersion && <article className="mt-4 rounded-lg border border-[#e8ede9] p-4"><b>{shownVersion.name}</b>{shownVersion.description && <p className="mt-1 text-sm text-[#60716b]">{shownVersion.description}</p>}<dl className="mt-3 grid gap-2 text-sm"><div><dt className="font-semibold">Recorded local time</dt><dd>{shownVersion.local_due_at.replace("T", " ")} {shownVersion.utc_offset} · {shownVersion.time_zone}</dd></div><div><dt className="font-semibold">Canonical UTC</dt><dd>{displayInstant(shownVersion.due_at_utc)}</dd></div></dl></article>}</div>}
      </div><form onSubmit={submit} className="h-fit rounded-xl border border-[#dce4de] bg-white p-5"><h2 className="font-bold">{selected ? "Create next configuration version" : "Create deadline configuration"}</h2><p className="mt-1 text-xs text-[#60716b]">No operational status is assigned.</p><div className="mt-4 grid gap-4"><label className="grid gap-1 text-sm font-semibold">Academic cycle<select className={input} disabled={saving || Boolean(selected)} value={form.academic_cycle_id} onChange={(event) => setForm({ ...form, academic_cycle_id: event.target.value })}><option value="">Select academic cycle</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_name} ({cycle.code})</option>)}</select>{errors.academic_cycle_id && <span className="text-xs text-[#a43a33]">{errors.academic_cycle_id}</span>}</label><label className="grid gap-1 text-sm font-semibold">Deadline name<input className={input} disabled={saving} value={form.name} onChange={(event) => { setForm({ ...form, name: event.target.value }); setErrors({ ...errors, name: "" }); }} />{errors.name && <span className="text-xs text-[#a43a33]">{errors.name}</span>}</label><label className="grid gap-1 text-sm font-semibold">Description <span className="font-normal text-[#60716b]">(optional)</span><textarea rows={3} className={input} disabled={saving} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label><label className="grid gap-1 text-sm font-semibold">Local date and time<input type="datetime-local" className={input} disabled={saving} value={form.local_due_at} onChange={(event) => invalidatePreview({ local_due_at: event.target.value }, true)} />{errors.local_due_at && <span className="text-xs text-[#a43a33]">{errors.local_due_at}</span>}</label><label className="grid gap-1 text-sm font-semibold">IANA timezone<select className={input} disabled={saving} value={form.time_zone} onChange={(event) => invalidatePreview({ time_zone: event.target.value }, true)}><option value="">Select timezone</option>{zones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}</select></label>{offsets.length > 1 && <label className="grid gap-1 text-sm font-semibold">UTC offset choice<select className={input} value={form.utc_offset} onChange={(event) => { setForm({ ...form, utc_offset: event.target.value }); setPreview(null); setErrors({}); setMessage(""); }}><option value="">Select intended offset</option>{offsets.map((offset) => <option key={offset} value={offset}>{offset}</option>)}</select><span className="text-xs font-normal text-[#60716b]">This local time occurs twice; choose the intended offset.</span></label>}<button type="button" disabled={saving || previewing} onClick={() => void previewTime()} className="rounded-lg border border-[#b8cdc1] px-4 py-2.5 text-sm font-semibold text-[#176b66] disabled:opacity-50">{previewing ? "Validating..." : "Validate local and UTC time"}</button>{errors.preview && <p className="text-xs text-[#a43a33]">{errors.preview}</p>}{preview && <div className="rounded-lg border border-[#cbd6d0] bg-[#f8fafc] p-3 text-sm"><p><b>Local:</b> {preview.local_due_at.replace("T", " ")} {preview.utc_offset} · {preview.time_zone}</p><p className="mt-1"><b>Canonical UTC:</b> {displayInstant(preview.due_at_utc)}</p></div>}<button disabled={saving || !preview} className="rounded-lg bg-[#176b66] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#125650] disabled:opacity-60">{saving ? "Saving..." : selected ? "Create configuration version" : "Save deadline configuration"}</button></div></form></div>}
  </section>;
}
