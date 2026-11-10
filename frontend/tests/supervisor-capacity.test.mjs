import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../src/AdminSupervisorCapacity.tsx", import.meta.url), "utf8");

test("supervisor capacity form uses supervisor, year, and annual maximum groups", () => {
  assert.match(source, /Supervisor<select/);
  assert.match(source, /Academic year<select/);
  assert.doesNotMatch(source, /Session<select/);
  assert.match(source, /Annual maximum groups<input/);
  assert.doesNotMatch(source, /Supervisor email/);
  assert.match(source, /academic_year: Number\(form\.academic_year\)/);
  assert.match(source, /maximum_groups: maximum/);
  assert.doesNotMatch(source, /session: form\.session/);
});

test("supervisor capacity table exposes annual Fall/Spring counts and status badges", () => {
  for (const label of ["Academic year", "Annual maximum", "Fall assigned", "Spring assigned", "Total assigned", "Remaining", "Status", "Actions"]) assert.match(source, new RegExp(label));
  assert.match(source, /AVAILABLE/);
  assert.match(source, /NEARLY_FULL/);
  assert.match(source, /FULL/);
  assert.match(source, /OVER_CAPACITY/);
  assert.match(source, /INACTIVE/);
  assert.match(source, /remaining_capacity/);
  assert.match(source, /Fall and Spring assignments share the same yearly limit/);
});

test("manual supervisor assignment form is removed", () => {
  assert.doesNotMatch(source, /Supervisor assignments/);
  assert.doesNotMatch(source, /Assign supervisor/);
  assert.doesNotMatch(source, /admin\/supervisor-assignments/);
});
