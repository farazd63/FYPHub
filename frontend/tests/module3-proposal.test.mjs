import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const workspace = fs.readFileSync(new URL("../src/modules/module-3/ProposalComplianceWorkspace.tsx", import.meta.url), "utf8");
const templates = fs.readFileSync(new URL("../src/modules/module-3/AdminProposalTemplates.tsx", import.meta.url), "utf8");
const aiSummary = fs.readFileSync(new URL("../src/ProposalAiSummary.tsx", import.meta.url), "utf8");

test("Module 3 exposes short/long draft, submit, resubmit, and review lifecycle actions", () => {
  for (const label of ["Short proposal", "Long proposal", "Save Draft", "Submit & run compliance check", "Resubmit Your Proposal", "Withdraw", "Approve", "Request changes", "Reject"]) {
    assert.match(workspace, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
  assert.match(workspace, /\/api\/v1\/proposal-compliance\/submissions\/\$\{id\}\/withdraw/);
  assert.match(workspace, /\/api\/v1\/proposal-compliance\/submissions\/\$\{selectedId\}\/status/);
});

test("Module 3 renders compliance findings and version change summaries", () => {
  assert.match(workspace, /academicConsistency/);
  assert.match(workspace, /changeSummary/);
  assert.match(workspace, /Preview Annotated PDF/);
  assert.match(workspace, /Preview PDF/);
  assert.match(workspace, /View student document/);
  assert.match(workspace, /View annotated copy/);
  assert.match(workspace, /View original template/);
  assert.match(workspace, /X-Preview-Page-Count/);
  assert.doesNotMatch(workspace, /download\s*=/i);
  assert.doesNotMatch(workspace, /module3-mini-lines/);
});

test("Module 3 template administration exposes structural and formatting rules", () => {
  for (const rule of ["alignment", "heading_style", "top_margin_mm", "bottom_margin_mm", "left_margin_mm", "right_margin_mm", "required_captions", "required_references", "required_tables", "required_figures", "required_appendices"]) {
    assert.match(templates, new RegExp(rule));
  }
  assert.doesNotMatch(templates, /table_count|figure_count|caption_count|reference_count|appendix_count/);
});

test("Module 3 template administration can delete inactive template versions", () => {
  assert.match(templates, /method: "DELETE"/);
  assert.match(templates, /Deactivate the active template before deleting it/);
  assert.match(templates, /window\.confirm/);
  assert.match(templates, />Delete<\/button>/);
});

test("AI summary handles non-JSON proxy responses without exposing a parser error", () => {
  assert.match(aiSummary, /response\.text\(\)/);
  assert.match(aiSummary, /invalid response/);
  assert.doesNotMatch(aiSummary, /const body = await response\.json\(\)/);
});

test("saved AI summaries are displayed without regenerating on report reload", () => {
  assert.match(workspace, /initialSummary=\{report\.aiSummary\}/);
  assert.match(workspace, /autoGenerate=\{!report\.aiSummary\}/);
});
