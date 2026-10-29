import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "../StudentPortal.tsx"), "utf8");
const sidebar = readFileSync(join(here, "../StudentSidebar.tsx"), "utf8");
const placeholder = readFileSync(join(here, "../modules/StudentPhasePlaceholder.tsx"), "utf8");
const app = readFileSync(join(here, "../../../App.tsx"), "utf8");
const css = readFileSync(join(here, "../student.css"), "utf8");

const phases = [
  ["Student Team & Collaboration Hub", "Partial", "/student/team"],
  ["Student Proposal & AI Compliance Check", "Coming in Module 3", "/student/proposals"],
  ["Proposal Similarity & Originality Check", "Coming in Module 4", "/student/similarity"],
  ["Supervisor Selection & Allocation", "Partial", "/student/supervisors"],
  ["Supervisor Proposal Review & Revision", "Coming in Module 6", "/student/reviews"],
  ["Coordinator Proposal Control", "Coming in Module 7", "/student/coordinator"],
  ["Panel Scheduling & Defense", "Coming in Module 8", "/student/panel/schedule"],
  ["Panel Evaluation & Feedback", "Coming in Module 9", "/student/panel/evaluation"],
  ["Project Progress & Supervision Dashboard", "Coming in Module 10", "/student/progress"],
  ["Final FYP Archive & Handover", "Coming in Module 11", "/student/archive"],
  ["FYP Knowledge Search & Analytics", "Coming in Module 12", "/student/search"],
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
assert.doesNotMatch(placeholder, /fetch\(|axios|XMLHttpRequest/);
assert.match(css, /#10244a/);
assert.match(css, /#3567d6/);

console.log("student-portal.test.mjs: all assertions passed");
