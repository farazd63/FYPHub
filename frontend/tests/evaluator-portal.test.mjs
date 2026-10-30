import assert from "node:assert/strict";
import fs from "node:fs";

const root = new URL("../src/", import.meta.url);
const app = fs.readFileSync(new URL("App.tsx", root), "utf8");
const portal = fs.readFileSync(new URL("portals/evaluator/EvaluatorPortal.tsx", root), "utf8");
const sidebar = fs.readFileSync(new URL("portals/evaluator/EvaluatorSidebar.tsx", root), "utf8");
const overview = fs.readFileSync(new URL("portals/evaluator/EvaluatorOverview.tsx", root), "utf8");
const routedPortal = fs.readFileSync(new URL("portals/student/modules/StudentEvaluatorPortal.tsx", root), "utf8");
const workflow = fs.readFileSync(new URL("portals/student/modules/EvaluatorWorkflow.tsx", root), "utf8");
const adminUsers = fs.readFileSync(new URL("AdminUsersRoles.tsx", root), "utf8");

assert.match(app, /EvaluatorPortal/);
assert.match(app, /authUser\?\.role === "PANEL_MEMBER"/);
assert.doesNotMatch(app, /PanelPortal/);
assert.match(portal, /Evaluator/);
assert.doesNotMatch(portal, /Panel Member/);
assert.doesNotMatch(portal, /fetch\(/);
for (const label of ["Evaluation Queue", "Proposal Review", "Defense Schedule", "Evaluation Criteria", "Scoring & Feedback", "Decision History"]) {
  assert.match(sidebar, new RegExp(label.replace(/[&]/g, "\\&")));
  assert.match(overview, new RegExp(label.replace(/[&]/g, "\\&")));
}
assert.match(adminUsers, /PANEL_MEMBER: "Evaluator"/);
assert.doesNotMatch(adminUsers, /Panel Member/);
assert.match(app, /StudentEvaluatorPortal as EvaluatorPortal/);
assert.match(routedPortal, /EvaluatorWorkflow/);
assert.match(workflow, /panel-evaluations/);
assert.match(workflow, /Submit evaluation/);
console.log("evaluator-portal.test.mjs: all assertions passed");
