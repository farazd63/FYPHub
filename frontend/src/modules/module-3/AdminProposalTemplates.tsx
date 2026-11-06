import { useEffect, useState, type FormEvent } from "react";
import "./module-3.css";

type Template = { id: number; template_type: "SHORT" | "LONG"; version: number; title: string; source_note: string; is_active: boolean; rules: Record<string, unknown>; };
type EditableRule = "page_size" | "margin_mm" | "right_margin_mm" | "top_margin_mm" | "bottom_margin_mm" | "font_family" | "font_size_pt" | "line_spacing" | "page_numbering" | "table_count" | "figure_count";
const editableRules: EditableRule[] = ["page_size", "margin_mm", "right_margin_mm", "top_margin_mm", "bottom_margin_mm", "font_family", "font_size_pt", "line_spacing", "page_numbering", "table_count", "figure_count"];
const value = (item: unknown) => item === null || item === undefined || item === "" ? "Not detected" : String(item);

export function AdminProposalTemplates({ api }: { api: string }) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [type, setType] = useState<"SHORT" | "LONG">("SHORT");
  const [title, setTitle] = useState("");
  const [sourceNote, setSourceNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<Template | null>(null);
  const [draftRules, setDraftRules] = useState<Record<string, unknown>>({});
  const [sectionsText, setSectionsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    const response = await fetch(`${api}/api/v1/proposal-compliance/templates`, { credentials: "include" });
    if (!response.ok) throw new Error("Templates could not be loaded.");
    setTemplates(await response.json() as Template[]);
  };
  // The initial request synchronizes this screen with the server-owned template list.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load().catch((caught) => setError(caught instanceof Error ? caught.message : "Templates could not be loaded.")); }, [api]);

  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) { setError("Select the approved PDF or DOCX template first."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const body = new FormData(); body.append("template_type", type); body.append("title", title || file.name); body.append("source_note", sourceNote || "Uploaded official university template"); body.append("template_file", file);
      const response = await fetch(`${api}/api/v1/proposal-compliance/templates/upload`, { method: "POST", credentials: "include", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Template extraction failed.");
      setMessage("Template uploaded and extracted. Review the detected rules, confirm them, then activate the version."); setTitle(""); setSourceNote(""); setFile(null); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Template upload failed."); } finally { setBusy(false); }
  };

  const review = (template: Template) => {
    setSelected(template); setDraftRules({ ...template.rules });
    setSectionsText(Array.isArray(template.rules.required_sections) ? (template.rules.required_sections as string[]).join("\n") : ""); setError("");
  };

  const saveRules = async () => {
    if (!selected) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const rules = { ...draftRules, required_sections: sectionsText.split(/\r?\n/).map((item) => item.trim()).filter(Boolean) };
      const response = await fetch(`${api}/api/v1/proposal-compliance/templates/${selected.id}/rules`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(rules) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Rule confirmation failed.");
      const saved = payload as Template;
      setSelected(saved); setDraftRules({ ...saved.rules }); setSectionsText(Array.isArray(saved.rules.required_sections) ? (saved.rules.required_sections as string[]).join("\n") : "");
      setMessage("Rules confirmed and saved as a new immutable rule snapshot. You can activate this baseline now."); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Rule confirmation failed."); } finally { setBusy(false); }
  };

  const activate = async (template: Template) => {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/templates/${template.id}/activate`, { method: "POST", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Template activation failed.");
      setMessage(`${template.title} is now the active ${template.template_type} baseline.`); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Template activation failed."); } finally { setBusy(false); }
  };

  const deactivate = async (template: Template) => {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/templates/${template.id}/deactivate`, { method: "POST", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Template deactivation failed.");
      setMessage(`${template.title} has been deactivated. Students must wait for an approved baseline to be activated.`); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Template deactivation failed."); } finally { setBusy(false); }
  };

  return <section className="module3-admin-page" aria-labelledby="module3-templates-heading">
    <div className="module3-page-heading"><p className="module3-eyebrow">Proposal Template</p><h1 id="module3-templates-heading">Proposal Templates</h1><p>Upload the approved SHORT or LONG template. Rules are extracted from the file and remain versioned for historical reports.</p></div>
    {message && <p className="module3-alert module3-alert--success" role="status">{message}</p>}
    {error && <p className="module3-alert module3-alert--error" role="alert">{error}</p>}
    <div className="module3-admin-grid">
      <form className="module3-panel module3-template-upload" onSubmit={(event) => void upload(event)}>
        <div className="module3-panel-heading"><div><span className="module3-kicker">Official source</span><h2>Upload and extract</h2></div><span className="module3-live-dot">Admin only</span></div>
        <p className="module3-muted">Use the approved university PDF or DOCX. No template values are hardcoded.</p>
        <label>Proposal type<select value={type} onChange={(event) => setType(event.target.value as "SHORT" | "LONG")}><option value="SHORT">Short proposal</option><option value="LONG">Long proposal</option></select></label>
        <label>Template title<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Uses filename if blank" /></label>
        <label>Source note<textarea value={sourceNote} onChange={(event) => setSourceNote(event.target.value)} placeholder="Approval or academic authority note" rows={3} /></label>
        <label className="module3-file-drop">Approved PDF/DOCX<input type="file" accept="application/pdf,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file && <strong>{file.name}</strong>}</label>
        <button className="module3-primary-button" type="submit" disabled={busy}>{busy ? "Extracting…" : "Upload & extract rules"}</button>
      </form>
      <section className="module3-panel"><div className="module3-panel-heading"><div><span className="module3-kicker">Version control</span><h2>Baseline history</h2></div><span className="module3-count">{templates.length}</span></div>{!templates.length ? <p className="module3-empty">No official template has been uploaded yet.</p> : <div className="module3-template-list">{templates.map((template) => <article className={`module3-template-row ${template.is_active ? "module3-template-row--active" : ""}`} key={template.id}><div><div className="module3-template-row__top"><strong>{template.template_type} · v{template.version}</strong><span className={`module3-status-pill ${template.is_active ? "module3-status-pill--pass" : "module3-status-pill--muted"}`}>{template.is_active ? "Active baseline" : "Not active"}</span></div><h3>{template.title}</h3><p>{template.source_note}</p></div><div className="module3-row-actions"><button type="button" onClick={() => review(template)}>Review &amp; confirm rules</button>{template.is_active ? <button type="button" onClick={() => void deactivate(template)} disabled={busy}>Deactivate</button> : <button type="button" onClick={() => void activate(template)} disabled={busy}>Activate</button>}</div></article>)}</div>}</section>
    </div>
    {selected && <section className="module3-panel module3-rule-review"><div className="module3-panel-heading"><div><span className="module3-kicker">Extracted evidence</span><h2>{selected.title} · {selected.template_type} v{selected.version}</h2></div><button className="module3-close-button" type="button" onClick={() => setSelected(null)}>Close</button></div><p className="module3-muted">These values came from the uploaded official document. Correct only if the university-approved template evidence confirms the value; saving creates a new rule snapshot for traceability.</p><div className="module3-rule-grid">{editableRules.map((key) => <label key={key}><span>{key.replaceAll("_", " ")}</span><input value={value(draftRules[key]) === "Not detected" ? "" : value(draftRules[key])} onChange={(event) => setDraftRules((current) => ({ ...current, [key]: event.target.value }))} placeholder="Not detected" /></label>)}</div><div className="module3-section-review"><label><h3>Required sections (one per line)</h3><textarea value={sectionsText} onChange={(event) => setSectionsText(event.target.value)} rows={7} placeholder="Introduction\nObjectives\nMethodology" /></label></div><div className="module3-review-actions"><button className="module3-primary-button" type="button" onClick={() => void saveRules()} disabled={busy}>{busy ? "Saving…" : "Confirm & save rules"}</button>{!selected.is_active && <button className="module3-secondary-button" type="button" onClick={() => void activate(selected)} disabled={busy}>Activate baseline</button>}</div></section>}
  </section>;
}
