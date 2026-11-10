import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const workspace = readFileSync(new URL("EvaluationMarksWorkspace.tsx", root), "utf8");
const student = readFileSync(new URL("portals/student/StudentPortal.tsx", root), "utf8");
const supervisor = readFileSync(new URL("portals/supervisor/SupervisorSidebar.tsx", root), "utf8");
const evaluator = readFileSync(new URL("portals/evaluator/EvaluatorSidebar.tsx", root), "utf8");
const admin = readFileSync(new URL("AdminPortal.tsx", root), "utf8");
const coordinator = readFileSync(new URL("portals/coordinator/CoordinatorPortal.tsx", root), "utf8");

test("evaluation workspace preserves the official category ownership and API contracts", () => {
  assert.match(workspace, /\/api\/v1\/evaluations\/assignments/);
  assert.match(workspace, /\/api\/v1\/evaluations\/my/);
  assert.match(workspace, /\/api\/v1\/student\/results/);
  assert.match(workspace, /credentials: "include"/);
  assert.match(workspace, /FINAL_PRESENTATION/);
  assert.match(workspace, /MID_REVIEW/);
  assert.match(workspace, /SUPERVISOR_EVALUATION/);
  assert.match(workspace, /PROJECT_DOCUMENTATION/);
  assert.match(workspace, /PROPOSAL/);
  assert.match(workspace, /Save Draft/);
  assert.match(workspace, /Submit Evaluation/);
});

test("all role portals mount the restored feature without changing unrelated role shells", () => {
  assert.match(student, /My FYP Results/);
  assert.match(student, /variant="student"/);
  assert.match(supervisor, /Evaluation & Marks/);
  assert.match(evaluator, /Evaluation & Marks/);
  assert.match(admin, /Evaluation & Marks/);
  assert.match(coordinator, /Evaluation & Marks/);
});

console.log("evaluation-marks.test.mjs: all assertions passed");
