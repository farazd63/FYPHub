import assert from "node:assert/strict";
import fs from "node:fs";

const root = new URL("../src/", import.meta.url);
const progress = fs.readFileSync(new URL("portals/student/modules/StudentProgressDashboard.tsx", root), "utf8");
const scheduling = fs.readFileSync(new URL("portals/coordinator/modules/supervisor-requests/PanelScheduling.tsx", root), "utf8");
const evaluation = fs.readFileSync(new URL("portals/student/modules/EvaluatorWorkflow.tsx", root), "utf8");

for (const source of [progress, scheduling, evaluation]) {
  assert.match(source, /fetch\(/);
  assert.doesNotMatch(source, /Coming soon|not available yet|No .* fabricated/);
}
assert.match(progress, /project-progress/);
assert.match(progress, /milestones/);
assert.match(progress, /tasks/);
assert.match(progress, /meetings/);
assert.match(progress, /Record meeting/);
assert.match(progress, /method: "PATCH"/);
assert.match(progress, /Update/);
assert.match(scheduling, /panel-schedules/);
assert.match(scheduling, /Create defense schedule/);
assert.match(scheduling, /Reschedule/);
assert.match(evaluation, /panel-evaluations/);
assert.match(evaluation, /Save draft/);
assert.match(evaluation, /Submit evaluation/);
assert.match(evaluation, /disagreement_detected/);

console.log("project-workflow.test.mjs: all assertions passed");
