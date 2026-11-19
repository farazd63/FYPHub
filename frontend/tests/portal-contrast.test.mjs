import assert from "node:assert/strict";
import fs from "node:fs";

const root = new URL("../src/", import.meta.url);
const index = fs.readFileSync(new URL("index.css", root), "utf8");
const student = fs.readFileSync(new URL("portals/student/student.css", root), "utf8");
const placeholder = fs.readFileSync(new URL("portals/student/modules/StudentPhasePlaceholder.tsx", root), "utf8");
const design = fs.readFileSync(new URL("design-system.css", root), "utf8");
const shells = [
  "portals/student/StudentPortal.tsx",
  "portals/supervisor/SupervisorPortal.tsx",
  "portals/coordinator/CoordinatorPortal.tsx",
  "portals/evaluator/EvaluatorPortal.tsx",
  "AdminPortal.tsx",
];

for (const file of shells) {
  const source = fs.readFileSync(new URL(file, root), "utf8");
  assert.match(source, /student-(?:shell|overview__eyebrow|page-heading)|admin-(?:role|sidebar)/, `${file} retains a readable shell/heading hook`);
}
assert.match(student, /student-status--partial/);
assert.match(placeholder, /student-page-heading|student-placeholder/);
assert.match(index, /\.student-page-heading \.student-overview__eyebrow/);
assert.match(index, /var\(--fy-brand/);
assert.match(index, /\.student-supervisor-option:disabled/);
assert.match(index, /opacity: 1/);
assert.doesNotMatch(index, /student-status[^}]*opacity:\s*0\.[0-7]/);
assert.match(design, /\.cycle-overview__hero h1[\s\S]*color:\s*#fff/);
assert.match(design, /\[aria-current="page"\]:hover/);
assert.match(design, /--fy-brand:\s*#e0a85c/);
console.log("portal-contrast.test.mjs: all assertions passed");
