import { useCallback, useEffect, useRef, useState } from "react";

type RubricSummary = { id: number; name: string; description: string | null; latest_version_number: number; created_at: string };
type Criterion = { id: number; name: string; description: string | null; order: number };
type Version = { id: number; version_number: number; name: string; description: string | null; created_at: string; criteria: Criterion[] };
type RubricDetail = { id: number; created_at: string; versions: Version[] };
type CriterionForm = { key: string; name: string; description: string };
type Form = { name: string; description: string; criteria: CriterionForm[] };
type FieldErrors = Record<string, string>;

const input = "w-full rounded-lg border border-[#dce4de] bg-white px-3 py-2.5 text-sm text-[#243746] focus:border-[#176b66] disabled:cursor-not-allowed disabled:bg-[#f4f6f4]";
const newCriterion = (): CriterionForm => ({ key: crypto.randomUUID(), name: "", description: "" });
const emptyForm = (): Form => ({ name: "", description: "", criteria: [newCriterion()] });
const apiMessage = (body: unknown, fallback: string) => {
  const detail = (body as { detail?: string | { message?: string } })?.detail;
  return typeof detail === "string" ? detail : detail?.message ?? fallback;
};

export function AdminEvaluationRubrics({ api }: { api: string }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [rubrics, setRubrics] = useState<RubricSummary[]>([]);
  const [selected, setSelected] = useState<RubricDetail | null>(null);
  const [form, setForm] = useState<Form>(emptyForm);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState("");
  const [messageIsError, setMessageIsError] = useState(false);
  const [saving, setSaving] = useState(false);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const response = await fetch(`${api}/api/v1/admin/evaluation-rubrics`, { credentials: "include" });
      if (!response.ok) throw new Error();
      setRubrics(await response.json() as RubricSummary[]);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [api]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const openRubric = async (rubricId: number, populate = true) => {
    const token = ++requestId.current;
    setMessage("");
    setMessageIsError(false);
    try {
      const response = await fetch(`${api}/api/v1/admin/evaluation-rubrics/${rubricId}`, { credentials: "include" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiMessage(body, "Evaluation criteria history could not be loaded."));
      if (token !== requestId.current) return;
      const detail = body as RubricDetail;
      setSelected(detail);
      if (populate) {
        const latest = detail.versions.at(-1);
        setForm(latest ? {
          name: latest.name,
          description: latest.description ?? "",
          criteria: latest.criteria.map((criterion) => ({ key: crypto.randomUUID(), name: criterion.name, description: criterion.description ?? "" })),
        } : emptyForm());
        setErrors({});
      }
    } catch (error) {
      if (token === requestId.current) { setMessageIsError(true); setMessage(error instanceof Error ? error.message : "Evaluation criteria history could not be loaded."); }
    }
  };

  const changeCriterion = (key: string, field: "name" | "description", value: string) => {
    setForm((current) => ({ ...current, criteria: current.criteria.map((item) => item.key === key ? { ...item, [field]: value } : item) }));
    setErrors((current) => ({ ...current, [`${key}.${field}`]: "" }));
  };
  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= form.criteria.length) return;
    setForm((current) => {
      const criteria = [...current.criteria];
      [criteria[index], criteria[target]] = [criteria[target], criteria[index]];
      return { ...current, criteria };
    });
  };
  const remove = (key: string) => setForm((current) => ({ ...current, criteria: current.criteria.filter((item) => item.key !== key) }));

  const validate = () => {
    const next: FieldErrors = {};
    if (!form.name.trim()) next.name = "Enter an evaluation-criteria name.";
    if (!form.criteria.length) next.criteria = "Add at least one criterion.";
    form.criteria.forEach((criterion) => { if (!criterion.name.trim()) next[`${criterion.key}.name`] = "Enter a criterion name."; });
    setErrors(next);
    return !Object.values(next).some(Boolean);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving || !validate()) return;
    setSaving(true);
    setMessage("");
    setMessageIsError(false);
    const keys = form.criteria.map((criterion) => criterion.key);
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      criteria: form.criteria.map((criterion, index) => ({ name: criterion.name.trim(), description: criterion.description.trim() || null, order: index + 1 })),
    };
    const path = selected ? `/api/v1/admin/evaluation-rubrics/${selected.id}/versions` : "/api/v1/admin/evaluation-rubrics";
    try {
      const response = await fetch(`${api}${path}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const fields = (body as { detail?: { fields?: { path: string }[] } }).detail?.fields ?? [];
        const mapped: FieldErrors = {};
        fields.forEach(({ path: fieldPath }) => {
          const match = /^criteria\.(\d+)\.(name|description|order)$/.exec(fieldPath);
          if (match && keys[Number(match[1])]) mapped[`${keys[Number(match[1])]}.${match[2]}`] = "Review this criterion.";
          else if (fieldPath === "name") mapped.name = "Enter a valid evaluation-criteria name.";
          else mapped.form = "Review the highlighted draft values.";
        });
        setErrors(mapped);
        throw new Error(apiMessage(body, "The draft could not be saved."));
      }
      const rubricId = selected?.id ?? (body as RubricDetail).id;
      setMessage(selected ? "New draft version created. Earlier versions are unchanged." : "Initial draft evaluation criteria created.");
      await load();
      await openRubric(rubricId, false);
      if (!selected) setForm(emptyForm());
    } catch (error) {
      setMessageIsError(true);
      setMessage(error instanceof Error ? error.message : "The evaluation criteria service is unavailable.");
    } finally {
      setSaving(false);
    }
  };

  const startNew = () => { requestId.current += 1; setSelected(null); setForm(emptyForm()); setErrors({}); setMessage(""); setMessageIsError(false); };

  return <section aria-labelledby="rubrics-heading">
    <div className="mb-5"><h1 id="rubrics-heading" className="text-2xl font-bold tracking-tight">Evaluation Criteria</h1><p className="mt-1 text-sm text-[#60716b]">Create internal draft evaluation-criteria configurations and preserve each complete version. Drafts are not approved or available for panel evaluation.</p></div>
    {message && <p role={messageIsError ? "alert" : "status"} className={`mb-4 rounded-lg px-3 py-2 text-sm ${messageIsError ? "bg-[#fff3f0] text-[#a43a33]" : "bg-[#e4eee7] text-[#176b66]"}`}>{message}</p>}
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
      <div className="min-w-0 space-y-5">
        <div className="rounded-xl border border-[#dce4de] bg-white p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="font-bold">Draft evaluation criteria</h2><p className="mt-1 text-xs text-[#60716b]">Internal configuration only</p></div><button type="button" onClick={startNew} className="rounded-lg border border-[#b8cdc1] px-3 py-2 text-sm font-semibold text-[#176b66] hover:bg-[#e4eee7]">New evaluation criteria</button></div>
          {state === "loading" && <p className="mt-4 text-sm text-[#60716b]">Loading draft evaluation criteria...</p>}
          {state === "error" && <p role="alert" className="mt-4 text-sm text-[#a43a33]">Draft evaluation criteria could not be loaded. <button type="button" className="underline" onClick={() => void load()}>Try again</button>.</p>}
          {state === "ready" && !rubrics.length && <p className="mt-4 rounded-lg border border-dashed border-[#cbd6d0] p-4 text-sm text-[#60716b]">No draft evaluation criteria have been configured.</p>}
          {rubrics.map((rubric) => <button key={rubric.id} type="button" onClick={() => void openRubric(rubric.id)} className="mt-3 flex w-full items-center justify-between gap-3 rounded-lg border border-[#e8ede9] p-3 text-left text-sm hover:bg-[#f4f8f5]"><span><b>{rubric.name}</b><span className="mt-1 block text-xs text-[#60716b]">Draft · latest version {rubric.latest_version_number}</span></span><span className="text-xs font-semibold text-[#176b66]">Open history</span></button>)}
        </div>
        {selected && <div className="rounded-xl border border-[#dce4de] bg-white p-5"><h2 className="font-bold">Complete draft history</h2>{selected.versions.map((version) => <article key={version.id} className="mt-4 rounded-lg border border-[#e8ede9] p-4"><div className="flex flex-wrap items-center gap-2"><b>Draft v{version.version_number} · {version.name}</b><span className="rounded-full bg-[#eef0ff] px-2 py-0.5 text-xs font-bold text-[#4663ff]">Draft</span></div>{version.description && <p className="mt-1 text-sm text-[#60716b]">{version.description}</p>}<ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">{version.criteria.map((criterion) => <li key={criterion.id}><span className="font-semibold">{criterion.name}</span>{criterion.description && <span className="block text-[#60716b]">{criterion.description}</span>}</li>)}</ol></article>)}</div>}
      </div>
      <form onSubmit={submit} className="h-fit rounded-xl border border-[#dce4de] bg-white p-5"><div className="flex items-center justify-between gap-3"><h2 className="font-bold">{selected ? "Create next version" : "Create initial evaluation criteria"}</h2><span className="rounded-full bg-[#eef0ff] px-2 py-1 text-xs font-bold text-[#4663ff]">Draft</span></div><p className="mt-1 text-xs text-[#60716b]">Saving creates an immutable complete version.</p>
        <div className="mt-4 grid gap-4"><label className="grid gap-1 text-sm font-semibold">Evaluation criteria name<input className={input} value={form.name} disabled={saving} aria-invalid={Boolean(errors.name)} onChange={(event) => { setForm({ ...form, name: event.target.value }); setErrors({ ...errors, name: "" }); }} />{errors.name && <span className="text-xs text-[#a43a33]">{errors.name}</span>}</label><label className="grid gap-1 text-sm font-semibold">Description <span className="font-normal text-[#60716b]">(optional)</span><textarea className={input} rows={3} value={form.description} disabled={saving} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
          <fieldset className="grid gap-3"><legend className="text-sm font-bold">Ordered criteria</legend>{errors.criteria && <p className="text-xs text-[#a43a33]">{errors.criteria}</p>}{form.criteria.map((criterion, index) => <div key={criterion.key} className="rounded-lg border border-[#e8ede9] p-3"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><b className="text-sm">Criterion {index + 1}</b><div className="flex flex-wrap items-center gap-2"><button type="button" aria-label="Move criterion up" disabled={saving || index === 0} onClick={() => move(index, -1)} className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#b8cdc1] text-[#176b66] transition-colors hover:bg-[#e4eee7] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4663ff] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"><svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-5 w-5 stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 5-5 5 5" /></svg></button><button type="button" aria-label="Move criterion down" disabled={saving || index === form.criteria.length - 1} onClick={() => move(index, 1)} className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#b8cdc1] text-[#176b66] transition-colors hover:bg-[#e4eee7] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4663ff] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"><svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-5 w-5 stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 8 5 5 5-5" /></svg></button><button type="button" aria-label={`Remove criterion ${index + 1}`} disabled={saving} onClick={() => remove(criterion.key)} className="inline-flex h-9 items-center justify-center rounded-lg border border-[#c96d66] px-3 text-sm font-semibold text-[#a43a33] transition-colors hover:bg-[#fff3f0] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#a43a33] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent">Remove</button></div></div><label className="grid gap-1 text-sm font-semibold">Criterion name<input className={input} value={criterion.name} disabled={saving} aria-invalid={Boolean(errors[`${criterion.key}.name`])} onChange={(event) => changeCriterion(criterion.key, "name", event.target.value)} />{errors[`${criterion.key}.name`] && <span className="text-xs text-[#a43a33]">{errors[`${criterion.key}.name`]}</span>}</label><label className="mt-3 grid gap-1 text-sm font-semibold">Description <span className="font-normal text-[#60716b]">(optional)</span><textarea className={input} rows={2} value={criterion.description} disabled={saving} onChange={(event) => changeCriterion(criterion.key, "description", event.target.value)} /></label></div>)}<button type="button" disabled={saving} onClick={() => setForm((current) => ({ ...current, criteria: [...current.criteria, newCriterion()] }))} className="rounded-lg border border-[#b8cdc1] px-3 py-2 text-sm font-semibold text-[#176b66] disabled:opacity-50">Add criterion</button></fieldset>
          <button disabled={saving} className="rounded-lg bg-[#176b66] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#125650] disabled:opacity-60">{saving ? "Saving..." : selected ? "Create draft version" : "Create draft evaluation criteria"}</button>
        </div>
      </form>
    </div>
  </section>;
}
