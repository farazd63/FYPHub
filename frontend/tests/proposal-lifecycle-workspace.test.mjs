import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const workspace = fs.readFileSync(new URL("../src/portals/student/modules/ProposalLifecycleWorkspace.tsx", import.meta.url), "utf8");
const app = fs.readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
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

test("Run AI review posts through the authenticated API client without status gating", () => {
  assert.match(workspace, /const runAiReview = async/);
  assert.match(workspace, /observeFetch\("proposal\.ai_review", `\$\{api\}\/api\/v1\/proposals\/\$\{selected\.id\}\/ai-review`/);
  assert.match(workspace, /method: "POST"/);
  assert.match(workspace, /credentials: "include"/);
  assert.match(workspace, /disabled=\{aiBusy\}/);
  assert.match(workspace, /Running AI review\.\.\./);
  assert.match(workspace, /401:/);
  assert.match(workspace, /403:/);
  assert.match(workspace, /404:/);
  assert.match(workspace, /409:/);
  assert.match(workspace, /500:/);
  assert.doesNotMatch(workspace, /selected\.status.*ACCEPTED.*runAiReview/);
});

test("proposal workspace loads the local API and reports response status safely", () => {
  assert.match(app, /http:\/\/127\.0\.0\.1:8010/);
  assert.match(workspace, /api\/v1\/proposals\/cycles/);
  assert.match(workspace, /api\/v1\/proposals\/mine/);
  assert.match(workspace, /credentials: "include"/);
  assert.match(workspace, /console\.debug\("API", response\.url, response\.status\)/);
  assert.match(workspace, /401:/);
  assert.match(workspace, /403:/);
  assert.match(workspace, /404:/);
  assert.match(workspace, /500:/);
  assert.match(workspace, /Proposal workspace data could not be loaded/);
  assert.match(workspace, /Network error: the backend could not be reached/);
});
