import { createPortal } from "react-dom";
import { useMemo, useState } from "react";
import "../module03.css";
import { formatWarnings, safeJson } from "../warningFormatter";

type Template = {
  id: number;
  template_type: string;
  filename: string;
  version: number;
  extraction_status: string;
  extracted_rules: Record<string, unknown>;
  extraction_warnings: unknown[];
  confidence: string | null;
  baseline_status: "COMPLETE" | "INCOMPLETE";
  missing_fields: string[];
  activation_mode: "COMPLETE" | "PARTIAL" | null;
  version_kind: string;
  parent_template_id: number | null;
  template_metadata: Record<string, unknown>;
  provenance: string;
  is_active: boolean;
  sha256: string;
  file_size: number;
  created_at: string;
  activated_at: string | null;
};

const detail = (body: unknown, fallback: string) => {
  const value = (body as { detail?: unknown })?.detail;
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "message" in value) {
    const message = (value as { message?: unknown }).message;
    return typeof message === "string" ? message : fallback;
  }
  return fallback;
};

const statusLabel = (value: string | undefined) => {
  const normalized = value?.toUpperCase();
  if (normalized === "EXTRACTED") return "Extracted";
  if (normalized === "FAILED") return "Failed";
  if (normalized === "PENDING") return "Pending";
  return value ? value.replace(/_/g, " ") : "Pending";
};

const readableValue = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "Not detected";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.length ? value.map(readableValue).join(", ") : "None detected";
  return Object.entries(value as Record<string, unknown>)
    .map(([key, nested]) => `${key.replace(/[_-]+/g, " ")}: ${readableValue(nested)}`)
    .join("; ");
};

const ruleLabel = (key: string) => ({
  margins: "Margins",
  line_spacing: "Line spacing",
  paragraph_spacing: "Paragraph spacing",
  default_font_family: "Font family",
  default_font_size_pt: "Font size",
  heading_order: "Heading order",
  heading_hierarchy: "Heading hierarchy",
  expected_sections: "Expected sections",
  citation_patterns: "Citation patterns",
  structural_baseline_status: "Structural baseline status",
  baseline_status: "Structural status",
  page_geometry: "Page geometry",
  caption_style: "Caption style",
  reference_template_fields: "Reference template fields",
}[key] ?? key.replace(/[_-]+/g, " "));

const extractedRuleKeys = [
  "page_geometry",
  "margins",
  "line_spacing",
  "paragraph_spacing",
  "default_font_family",
  "default_font_size_pt",
  "heading_hierarchy",
  "expected_sections",
  "citation_patterns",
  "structural_baseline_status",
  "baseline_status",
  "heading_order",
  "caption_style",
  "reference_template_fields",
];

export function AdminTemplateUploadModal({ api, onSaved }: { api: string; onSaved?: () => void }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("SHORT");
  const [file, setFile] = useState<File | null>(null);
  const [busyAction, setBusyAction] = useState<"upload" | "activate" | "metadata" | "rules" | null>(null);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<Template | null>(null);
  const [history, setHistory] = useState<Template[]>([]);
  const busy = busyAction !== null;
  const warnings = useMemo(() => formatWarnings(result?.extraction_warnings ?? []).filter((warning) => !["incomplete_structural_baseline", "required_structural_fields_missing"].includes(warning.code ?? "")), [result]);
  const incomplete = Boolean(result && result.baseline_status !== "COMPLETE");
  const canActivate = Boolean(result && result.extraction_status.toUpperCase() === "EXTRACTED" && Object.keys(result.extracted_rules ?? {}).length > 0);
  const activationStatus = result?.is_active ? (result.activation_mode === "PARTIAL" ? "PARTIAL BASELINE" : "COMPLETE BASELINE") : "NOT ACTIVATED";
  const partialConfirmationMessage = "This template is incomplete. Activating it as a partial baseline may produce incomplete compliance checks. Do you want to continue?";
  const busyLabel = busyAction === "activate" ? "Activating baseline..." : busyAction === "metadata" ? "Creating metadata version..." : busyAction === "rules" ? "Creating rules version..." : "Uploading and extracting...";

  const refreshHistory = async () => {
    try {
      const response = await fetch(`${api}/api/v1/module-03/admin/templates`, { credentials: "include" });
      if (response.ok) setHistory(await response.json() as Template[]);
    } catch {
      // History is supplemental; ingestion and activation errors remain visible.
    }
  };

  const upload = async () => {
    if (!file || busy) return;
    setBusyAction("upload");
    setMessage("");
    try {
      const form = new FormData();
      form.append("template_type", type);
      form.append("document", file);
      const response = await fetch(`${api}/api/v1/module-03/admin/templates`, { method: "POST", credentials: "include", body: form });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(detail(body, "The template could not be ingested."));
      const template = body as Template;
      setResult(template);
      void refreshHistory();
      setMessage(template.extraction_status.toUpperCase() === "FAILED" ? "The document could not be extracted into a usable baseline. Review the warnings and upload a supported document." : "Template ingested. Review the extraction warnings before activating it.");
      onSaved?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The template service is unavailable.");
    } finally {
      setBusyAction(null);
    }
  };

  const activate = async () => {
    if (!result || !canActivate || busy) return;
    if (incomplete && !window.confirm(partialConfirmationMessage)) return;
    setBusyAction("activate");
    setMessage("");
    try {
      const form = new FormData();
      form.append("active", "true");
      form.append("activation_mode", incomplete ? "PARTIAL" : "COMPLETE");
      if (incomplete) form.append("confirm_partial", "true");
      const response = await fetch(`${api}/api/v1/module-03/admin/templates/${result.id}/activate`, { method: "POST", credentials: "include", body: form });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(detail(body, "The baseline could not be activated."));
      setResult(body as Template);
      void refreshHistory();
      setMessage(`Baseline activated as ${body.activation_mode === "PARTIAL" ? "partial" : "complete"} for the selected proposal type.`);
      onSaved?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The activation service is unavailable.");
    } finally {
      setBusyAction(null);
    }
  };

  const createMetadataVersion = async () => {
    if (!result || busy) return;
    setBusyAction("metadata"); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/module-03/admin/templates/${result.id}/metadata-version`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template_metadata: { ...result.template_metadata, reviewed_at: new Date().toISOString() }, provenance: "Observed reference property" }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(detail(body, "The metadata version could not be created."));
      setResult(body as Template); setMessage("Metadata version created."); void refreshHistory(); onSaved?.();
    } catch (error) { setMessage(error instanceof Error ? error.message : "The metadata version could not be created."); }
    finally { setBusyAction(null); }
  };

  const createRuleVersion = async () => {
    if (!result || busy) return;
    setBusyAction("rules"); setMessage("");
    try {
      const response = await fetch(`${api}/api/v1/module-03/admin/templates/${result.id}/rule-version`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provenance: "Observed reference property" }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(detail(body, "The formatting rule version could not be created."));
      setResult(body.template as Template); setMessage(`Rules v${body.rule_version} created.`); void refreshHistory(); onSaved?.();
    } catch (error) { setMessage(error instanceof Error ? error.message : "The formatting rule version could not be created."); }
    finally { setBusyAction(null); }
  };

  const dialog = open ? (
    <div className="module03-dialog" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <div className="module03-dialog__panel" role="dialog" aria-modal="true" aria-labelledby="module03-template-upload-heading">
        <div className="module03-dialog__head">
          <div>
            <p className="module03-dialog__eyebrow">Module 03 · Admin ingestion</p>
            <h2 id="module03-template-upload-heading">Upload proposal baseline</h2>
          </div>
          <button type="button" className="module03-dialog__close" aria-label="Close" onClick={() => setOpen(false)}>×</button>
        </div>
        <div className="module03-dialog__body">
          <p>Upload the approved SHORT or LONG DOCX/PDF. Rules are extracted from the document; no hardcoded template values are used.</p>
          <div className="module03-grid">
            <label className="module03-field">Template type<select value={type} onChange={(event) => setType(event.target.value)}><option>SHORT</option><option>LONG</option></select></label>
            <label className="module03-field">Reference document<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
          </div>
          <div className="module03-status-row" aria-live="polite"><span>Extraction status</span><strong className={`module03-status-badge module03-status-badge--${(result?.extraction_status ?? (file ? "PENDING" : "PENDING")).toLowerCase()}`}>{statusLabel(result?.extraction_status ?? "PENDING")}</strong>{busy && <span>{busyLabel}</span>}</div>
          {result && <div className="module03-baseline-status" aria-live="polite"><span>Baseline status</span><strong className={`module03-status-badge module03-status-badge--${activationStatus.toLowerCase().replace(/\s+/g, "-")}`}>{activationStatus}</strong></div>}
          {busyAction === "upload" && <div className="module03-progress" role="progressbar" aria-label="Uploading and extracting" aria-valuetext="Uploading and extracting"><span /></div>}
          {message && <p className={`module03-alert ${result?.extraction_status.toUpperCase() === "FAILED" || message.toLowerCase().includes("could not") ? "error" : "success"}`} role={result ? "status" : "alert"}>{message}</p>}
          {result && <>
            <div className="module03-preview-summary"><div><span>Version</span><strong>v{result.version} {result.version_kind === "METADATA" ? "metadata" : "initial reference"}</strong></div><div><span>Confidence</span><strong>{result.confidence ?? "Unknown"}</strong></div><div><span>Activation mode</span><strong>{result.activation_mode ?? "Not activated"}</strong></div><div><span>Provenance</span><strong>{result.provenance}</strong></div><div><span>File</span><strong>{result.filename}</strong></div></div>
            {incomplete && <div className="module03-incomplete-summary" role="alert"><strong>This template is incomplete and cannot be activated as a complete baseline.</strong><span>{result.missing_fields.length + warnings.length} review item{result.missing_fields.length + warnings.length === 1 ? "" : "s"} require attention.</span></div>}
            {result.missing_fields.length > 0 && <details className="module03-missing-fields"><summary>View missing fields <span className="module03-count-badge">{result.missing_fields.length}</span></summary><ul>{result.missing_fields.map((field) => <li key={field}>{field}</li>)}</ul></details>}
            {warnings.length > 0 && <section aria-labelledby="module03-template-warnings-heading"><h3 id="module03-template-warnings-heading" className="module03-section-title">Extraction warnings <span className="module03-count-badge">{warnings.length}</span></h3><div className="module03-warning-list">{warnings.map((warning, index) => <article className={`module03-warning module03-warning--${warning.severity}`} key={`${warning.code ?? "warning"}-${index}`}><div className="module03-warning__content"><span className="module03-warning__badge">{warning.severity}</span><p>{warning.message}</p></div><details><summary>Developer details</summary><pre className="module03-json">{safeJson(warning.raw)}</pre></details></article>)}</div></section>}
            <section aria-labelledby="module03-template-rules-heading"><h3 id="module03-template-rules-heading" className="module03-section-title">Extracted sections and formatting rules</h3><div className="module03-rule-grid">{extractedRuleKeys.filter((key) => key in (result.extracted_rules ?? {})).map((key) => <article key={key} className="module03-rule-card"><strong>{ruleLabel(key)}</strong><span>{readableValue(result.extracted_rules[key])}</span></article>)}</div></section>
            <details className="module03-developer-details"><summary>Developer details · raw extracted JSON</summary><pre className="module03-json">{safeJson(result.extracted_rules)}</pre></details>
          </>}
          {history.length > 0 && <section aria-labelledby="module03-template-history-heading"><h3 id="module03-template-history-heading" className="module03-section-title">Baseline history</h3><div className="module03-history-list">{history.map((item) => <article key={item.id} className="module03-history-card"><div><strong>{item.template_type} · v{item.version}</strong><span>{item.filename}</span></div><div className="module03-history-meta"><span>Activation: {item.activation_mode ?? "Not activated"}</span><span>Confidence: {item.confidence ?? "Unknown"}</span><span>Warnings: {item.extraction_warnings.length}</span><span>Missing fields: {item.missing_fields.length ? item.missing_fields.join(", ") : "None"}</span></div></article>)}</div></section>}
        </div>
        <div className="module03-dialog__footer"><button type="button" className="module03-button" disabled={!file || busy} onClick={() => void upload()}>{busyAction === "upload" ? "Extracting..." : "Ingest and extract"}</button>{result && <><button type="button" className="module03-button secondary" disabled={busy} onClick={() => void createMetadataVersion()}>Create metadata version</button><button type="button" className="module03-button secondary" disabled={busy} onClick={() => void createRuleVersion()}>Create rules version</button></>}<button type="button" aria-label={incomplete ? "Confirm partial baseline activation" : "Activate baseline"} className={`module03-button module03-button--activate ${incomplete ? "module03-button--partial" : ""}`} disabled={!canActivate || busy || Boolean(result?.is_active)} onClick={() => void activate()}>{busyAction === "activate" ? "Activating..." : result?.is_active ? `Active ${result.activation_mode === "PARTIAL" ? "partial" : "complete"} baseline` : incomplete ? "Activate partial baseline" : "Activate baseline"}</button><button type="button" className="module03-button secondary" onClick={() => setOpen(false)}>Close</button></div>
      </div>
    </div>
  ) : null;

  return <><button type="button" className="module03-button secondary" onClick={() => { setOpen(true); setMessage(""); void refreshHistory(); }}>{"Upload dynamic baseline"}</button>{dialog && createPortal(dialog, document.body)}</>;
}
