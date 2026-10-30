import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "../StudentPortal.tsx"), "utf8");
const sidebar = readFileSync(join(here, "../StudentSidebar.tsx"), "utf8");
const app = readFileSync(join(here, "../../../App.tsx"), "utf8");
const css = readFileSync(join(here, "../student.css"), "utf8");
const visibility = readFileSync(join(here, "../student-visibility.css"), "utf8");

const phases = [
  ["Student Team & Collaboration Hub", "Partial", "/student/team"],
  ["Proposal Compliance Check", "Partial", "/student/proposals"],
  ["Supervisor Selection & Proposal Requests", "Partial", "/student/supervisors"],
  ["FYP Archive & Knowledge Search", "Implemented", "/student/search"],
];

for (const [name, status, route] of phases) {
  assert.match(source, new RegExp(name.replace(/[&]/g, "\\&")), `${name} should render`);
  assert.match(source, new RegExp(status.replace(/[&]/g, "\\&")), `${name} should show ${status}`);
  assert.match(source, new RegExp(route.replace(/[/.]/g, "\\$&")), `${route} should be retained`);
}

assert.match(app, /authUser\.role === "STUDENT"/);
assert.match(app, /<StudentPortal api=\{API\}/);
assert.match(app, /page === "admin-portal"/);
assert.match(app, /if \(page === "account" && authUser\?\.role === "STUDENT"\)/);
assert.match(app, /if \(page === "admin-portal" && authUser\)/);
assert.match(sidebar, /Collapse navigation/);
assert.match(sidebar, /Expand navigation/);
assert.match(sidebar, /aria-current/);
for (const pending of ["Panel Scheduling & Defense", "Panel Evaluation & Feedback", "Coordinator Proposal Control", "Project Progress & Supervision Dashboard", "Final FYP Archive & Handover", "Coming in Module"]) {
  assert.doesNotMatch(source, new RegExp(pending.replace(/[&]/g, "\\&")), `${pending} must remain hidden`);
}
assert.doesNotMatch(source, /data-future-route/);
assert.match(visibility, /semantic|LLM/i);
assert.match(css, /#10244a/);
assert.match(css, /#3567d6/);

console.log("student-portal.test.mjs: all assertions passed");
