import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const workspace = fs.readFileSync(new URL("../src/portals/student/modules/ProposalLifecycleWorkspace.tsx", import.meta.url), "utf8");
const placeholder = fs.readFileSync(new URL("../src/portals/student/modules/StudentPhasePlaceholder.tsx", import.meta.url), "utf8");

test("student proposal route renders the dedicated lifecycle workspace", () => {
  assert.match(workspace, /Proposal Lifecycle &amp; Review/);
  assert.match(placeholder, /ProposalLifecycleWorkspace/);
  assert.match(workspace, /proposal_type/);
  assert.match(workspace, /value=\{type\}/);
});

test("proposal workspace supports PDF and DOCX lifecycle actions", () => {
  assert.match(workspace, /application\/pdf/);
  assert.match(workspace, /application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document/);
  assert.match(workspace, /Save draft/);
  assert.match(workspace, /Submit proposal/);
  assert.match(workspace, /Resubmit proposal/);
  assert.match(workspace, /Version and decision history/);
  assert.match(workspace, /Withdraw/);
});
