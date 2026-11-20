import { useEffect, useState, type FormEvent } from "react";
import "./module-3.css";

type Template = { id: number; template_type: "SHORT" | "LONG"; version: number; title: string; source_note: string; is_active: boolean; rules: Record<string, unknown> };
type MainRule = "page_size" | "top_margin_mm" | "bottom_margin_mm" | "left_margin_mm" | "right_margin_mm" | "font_family" | "font_size_pt" | "line_spacing" | "alignment" | "heading_style" | "page_numbering";
type OptionalRule = "required_references" | "required_captions" | "required_tables" | "required_figures" | "required_appendices";

const mainRules: Array<[MainRule, string]> = [
  ["page_size", "Page size"],
  ["top_margin_mm", "Top margin (mm)"],
  ["bottom_margin_mm", "Bottom margin (mm)"],
  ["left_margin_mm", "Left margin (mm)"],
  ["right_margin_mm", "Right margin (mm)"],
  ["font_family", "Font family"],
  ["font_size_pt", "Font size (pt)"],
  ["line_spacing", "Line spacing"],
  ["alignment", "Text alignment"],
  ["heading_style", "Heading style"],
  ["page_numbering", "Page numbering"],
];
const optionalRules: Array<[OptionalRule, string]> = [
  ["required_references", "References"],
  ["required_captions", "Captions"],
  ["required_tables", "Tables"],
  ["required_figures", "Figures"],
  ["required_appendices", "Appendices"],
];

const displayRule = (key: string, item: unknown) => {
  if (item === null || item === undefined || item === "" || item === "Not detected") return "Not detected";
  if (key === "page_numbering" || key.startsWith("required_")) return item === true || Number(item) > 0 ? "Required" : "Not detected";
  if (Array.isArray(item)) return item.length ? item.join("\n") : "Not detected";
  return String(item);
};

export function AdminProposalTemplates({ api }: { api: string }) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [type, setType] = useState<"SHORT" | "LONG">("SHORT");
  const [title, setTitle] = useState("");
  const [sourceNote, setSourceNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<Template | null>(null);
  const [draftRules, setDraftRules] = useState<Record<string, unknown>>({});
  const [sectionsText, setSectionsText] = useState("");
  const [editingRules, setEditingRules] = useState(false);
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
      setMessage("Official template uploaded and parsed deterministically. Review the confirmed main rules before activation."); setTitle(""); setSourceNote(""); setFile(null); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Template upload failed."); } finally { setBusy(false); }
  };

  const review = (template: Template) => {
    setSelected(template); setDraftRules({ ...template.rules }); setEditingRules(false);
    setSectionsText(Array.isArray(template.rules.required_sections) ? (template.rules.required_sections as string[]).join("\n") : ""); setError("");
  };

  const updateRule = (key: string, value: string) => {
    setDraftRules((current) => ({ ...current, [key]: value }));
  };

  const cancelRuleEdit = () => {
    if (!selected) return;
    setDraftRules({ ...selected.rules });
    setSectionsText(Array.isArray(selected.rules.required_sections) ? (selected.rules.required_sections as string[]).join("\n") : "");
    setEditingRules(false);
    setError("");
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
      setSelected(saved); setDraftRules({ ...saved.rules }); setSectionsText(Array.isArray(saved.rules.required_sections) ? (saved.rules.required_sections as string[]).join("\n") : ""); setEditingRules(false);
      setMessage("Deterministic rules confirmed and saved as a new immutable snapshot. Activate this official baseline when ready."); await load();
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

  const remove = async (template: Template) => {
    if (template.is_active) {
      setError("Deactivate the active template before deleting it.");
      return;
    }
    if (!window.confirm(`Delete ${template.template_type} v${template.version} (${template.title})? This cannot be undone.`)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/proposal-compliance/templates/${template.id}`, { method: "DELETE", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "object" ? payload.detail.message : payload.detail || "Template deletion failed.");
      if (selected?.id === template.id) setSelected(null);
      setMessage(`${template.title} was deleted.`);
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Template deletion failed."); } finally { setBusy(false); }
  };

  const visibleOptionalRules = editingRules ? optionalRules : optionalRules.filter(([key]) => key in draftRules);
  return <section className="module3-admin-page" aria-labelledby="module3-templates-heading">
    <div className="module3-page-heading module3-admin-page-heading"><div><h1 id="module3-templates-heading">Proposal Templates</h1><p>Upload the official university PDF or DOCX. Rules are measured from that file only; unclear values remain Not detected.</p></div></div>
    {message && <p className="module3-alert module3-alert--success" role="status">{message}</p>}
    {error && <p className="module3-alert module3-alert--error" role="alert">{error}</p>}
    <div className="module3-admin-grid">
      <form className="module3-panel module3-template-upload" onSubmit={(event) => void upload(event)}>
        <div className="module3-panel-heading"><div><h2>Upload and parse</h2></div></div>
        <p className="module3-muted">PDF uses PyMuPDF; DOCX uses python-docx. OCR is used only when a PDF has no readable text.</p>
        <label>Proposal type<select value={type} onChange={(event) => setType(event.target.value as "SHORT" | "LONG")}><option value="SHORT">Short proposal</option><option value="LONG">Long proposal</option></select></label>
        <label>Template title<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Uses filename if blank" /></label>
        <label>Source note<textarea value={sourceNote} onChange={(event) => setSourceNote(event.target.value)} placeholder="Approval or academic authority note" rows={3} /></label>
        <label className="module3-file-drop">Approved PDF/DOCX<input type="file" accept="application/pdf,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file && <strong>{file.name}</strong>}</label>
        <button className="module3-primary-button" type="submit" disabled={busy}>{busy ? "Parsing…" : "Upload & parse rules"}</button>
      </form>
      <section className="module3-panel"><div className="module3-panel-heading"><div><span className="module3-kicker">Version control</span><h2>Baseline history</h2></div><span className="module3-count">{templates.length}</span></div>{!templates.length ? <p className="module3-empty">No official template has been uploaded yet.</p> : <div className="module3-template-list">{templates.map((template) => <article className={`module3-template-row ${template.is_active ? "module3-template-row--active" : ""}`} key={template.id}><div><div className="module3-template-row__top"><strong>{template.template_type} · v{template.version}</strong><span className={`module3-status-pill ${template.is_active ? "module3-status-pill--pass" : "module3-status-pill--muted"}`}>{template.is_active ? "Active baseline" : "Not active"}</span></div><h3>{template.title}</h3><p>{template.source_note}</p></div><div className="module3-row-actions"><button type="button" onClick={() => review(template)}>Review extracted rules</button>{template.is_active ? <button type="button" onClick={() => void deactivate(template)} disabled={busy}>Deactivate</button> : <><button type="button" onClick={() => void activate(template)} disabled={busy}>Activate</button><button type="button" className="module3-danger-button" onClick={() => void remove(template)} disabled={busy}>Delete</button></>}</div></article>)}</div>}</section>
    </div>
    {selected && <section className="module3-panel module3-rule-review"><div className="module3-panel-heading"><div><span className="module3-kicker">Deterministic evidence</span><h2>{selected.title} · {selected.template_type} v{selected.version}</h2></div><button className="module3-close-button" type="button" onClick={() => { if (editingRules) cancelRuleEdit(); setSelected(null); }}>Close</button></div><p className="module3-muted">These values were measured from the official template file. You can correct them before activating the baseline. Saving creates a new immutable rule snapshot; source pages and extraction provenance remain retained internally.</p><div className="module3-rule-grid">{mainRules.map(([key, label]) => <label key={key}><span>{label}</span><input value={displayRule(key, draftRules[key])} readOnly={!editingRules} aria-readonly={!editingRules} onChange={(event) => updateRule(key, event.target.value)} placeholder="Not detected" /></label>)}</div>{visibleOptionalRules.length > 0 && <div className="module3-section-review"><h3>Explicitly required template elements</h3><div className="module3-rule-grid">{visibleOptionalRules.map(([key, label]) => <label key={key}><span>{label}</span><input value={displayRule(key, draftRules[key])} readOnly={!editingRules} aria-readonly={!editingRules} onChange={(event) => updateRule(key, event.target.value)} /></label>)}</div></div>}<div className="module3-section-review"><label><h3>Required sections (one per line)</h3><textarea value={sectionsText} readOnly={!editingRules} aria-readonly={!editingRules} onChange={(event) => setSectionsText(event.target.value)} rows={7} placeholder="Not detected" /></label></div><div className="module3-review-actions">{editingRules ? <><button className="module3-primary-button" type="button" onClick={() => void saveRules()} disabled={busy}>{busy ? "Saving…" : "Save changes"}</button><button className="module3-secondary-button" type="button" onClick={cancelRuleEdit} disabled={busy}>Cancel</button></> : <button className="module3-primary-button" type="button" onClick={() => { setEditingRules(true); setMessage(""); }} disabled={busy}>Edit extracted rules</button>}{!selected.is_active && <button className="module3-secondary-button" type="button" onClick={() => void activate(selected)} disabled={busy || editingRules}>Activate baseline</button>}</div></section>}
  </section>;
}
