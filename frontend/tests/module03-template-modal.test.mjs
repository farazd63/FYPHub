import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..", "src", "modules", "module_03_proposal");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

const modal = read("components/AdminTemplateUploadModal.tsx");
const compliance = read("ProposalComplianceView.tsx");
const styles = read("module03.css");
const formatter = read("warningFormatter.ts");
const adminPortal = fs.readFileSync(path.join(here, "..", "src", "AdminPortal.tsx"), "utf8");

assert.match(modal, /createPortal\(dialog, document\.body\)/, "modal should escape clipping admin containers");
assert.match(modal, /module03-dialog__footer/, "modal should keep footer actions reachable");
assert.match(modal, /Activate baseline/, "modal should expose guarded activation");
assert.match(modal, /Activate partial baseline/, "incomplete baselines should expose partial activation");
assert.match(modal, /This template is incomplete\. Activating it as a partial baseline may produce incomplete compliance checks\. Do you want to continue\?/, "partial activation requires explicit confirmation");
assert.match(modal, /activation_mode/);
assert.match(modal, /missing_fields/);
assert.match(modal, /baseline_status/);
assert.match(modal, /Create metadata version/, "modal should expose metadata version creation");
assert.match(modal, /Create rules version/, "modal should expose rule version creation");
assert.match(modal, /metadata-version/, "metadata version should use the backend endpoint");
assert.match(modal, /rule-version/, "rule version should use the backend endpoint");
assert.match(modal, /Confirm partial baseline activation/, "low-confidence activation requires explicit confirmation");
assert.match(modal, /aria-label=\"Uploading and extracting\"/, "modal should expose ingestion progress");
assert.match(modal, /formatWarnings\(result\?\.extraction_warnings/, "Admin warnings should use the formatter");
assert.match(modal, /module03-incomplete-summary/, "incomplete templates should show one summary alert");
assert.match(modal, /This template is incomplete and cannot be activated as a complete baseline\./, "incomplete summary should use the approved message");
assert.match(modal, /View missing fields/, "missing fields should be collapsible");
assert.match(modal, /module03-count-badge/, "warning and missing-field counts should be visible");
assert.match(modal, /incomplete_structural_baseline.*required_structural_fields_missing/, "structural summary warnings should not be duplicated in extraction warnings");
assert.match(modal, /module03-button--partial/, "partial activation should have a distinct action style");
assert.match(modal, /activationStatus/, "activation status badge should be rendered");
assert.doesNotMatch(modal, /Object\.entries\(result\.extracted_rules/, "only readable extracted rule fields should be rendered");
assert.match(compliance, /formatWarnings\(proposal\.extraction_warnings\)/, "student warnings should use the formatter");
assert.doesNotMatch(`${modal}\n${compliance}`, /\[object Object\]|map\(String\)/, "Module 03 must not stringify warning objects directly");
for (const key of ["message", "code", "field", "issue", "severity"]) assert.match(formatter, new RegExp(key), `formatter should support ${key} warnings`);
assert.match(formatter, /formatWarnings/);

assert.match(styles, /\.module03-dialog\{[^}]*position:fixed/);
assert.match(styles, /\.module03-dialog\{[^}]*inset:0/);
assert.match(styles, /max-height:calc\(100vh - 32px\)/, "desktop modal should fit within the viewport");
assert.match(styles, /overflow-y:auto/, "modal content should scroll internally");
assert.match(styles, /\.module03-dialog__panel\{[^}]*max-height:90vh[^}]*overflow:hidden/, "the panel should constrain overflow");
assert.match(styles, /\.module03-dialog__body\{[^}]*overflow-y:auto/, "only the body should scroll");
assert.match(styles, /\.module03-dialog__footer\{[^}]*position:static/, "the footer should remain in normal flex flow");
assert.match(styles, /grid-template-columns:repeat\(3,minmax\(0,1fr\)\)/, "desktop extraction cards should use three columns");
assert.match(styles, /grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/, "tablet extraction cards should use two columns");
assert.match(styles, /module03-button--partial/, "partial activation should have an amber style");
assert.match(styles, /@media \(max-width:700px\)/, "modal should have a mobile layout");
assert.match(styles, /width:calc\(100vw - 16px\)/, "mobile modal should fit narrow viewports");
assert.match(adminPortal, /AdminTemplateUploadModal/);
assert.match(adminPortal, /page===\"module03\"/);

console.log("module03-template-modal.test.mjs: all assertions passed");
