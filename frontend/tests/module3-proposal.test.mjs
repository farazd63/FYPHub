import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const workspace = fs.readFileSync(new URL("../src/modules/module-3/ProposalComplianceWorkspace.tsx", import.meta.url), "utf8");
const templates = fs.readFileSync(new URL("../src/modules/module-3/AdminProposalTemplates.tsx", import.meta.url), "utf8");

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
  assert.match(workspace, /View Annotated PDF/);
  assert.match(workspace, /Download PDF/);
});

test("Module 3 template administration exposes structural and formatting rules", () => {
  for (const rule of ["alignment", "heading_style", "caption_count", "reference_count", "appendix_count", "required_captions", "required_references", "required_appendices"]) {
    assert.match(templates, new RegExp(rule));
  }
});
