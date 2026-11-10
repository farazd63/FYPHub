import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const dashboard = fs.readFileSync(new URL("AcademicCycleDashboard.tsx", root), "utf8");
const admin = fs.readFileSync(new URL("AdminPortal.tsx", root), "utf8");
const coordinator = fs.readFileSync(new URL("portals/coordinator/CoordinatorPortal.tsx", root), "utf8");

test("academic cycle dashboard is mounted in both authorized portal shells", () => {
  assert.match(admin, /AcademicCycleDashboard/);
  assert.match(admin, /page === "cycles" \? <AcademicCycleDashboard/);
  assert.match(coordinator, /AcademicCycleDashboard/);
  assert.match(coordinator, /page === "cycles" \? <AcademicCycleDashboard/);
});

test("academic cycle dashboard loads list and authorized detail data with the session", () => {
  assert.match(dashboard, /api\/v1\/academic-cycles/);
  assert.match(dashboard, /api\/v1\/academic-cycles\/\$\{detailId\}\/overview/);
  assert.match(dashboard, /credentials: "include"/);
  assert.doesNotMatch(dashboard, /rows\.map\(async \(cycle\)/);
  assert.match(dashboard, /window\.history\.pushState\(\{ academicCycleId: cycle\.id \}/);
  assert.match(dashboard, /setDetailId\(cycle\.id\)/);
  assert.match(dashboard, /const detailPath = `\/api\/v1\/academic-cycles\/\$\{detailId\}\/overview`/);
  assert.doesNotMatch(dashboard, /academic-cycles\/\$\{cycle\.code\}\/overview/);
  assert.match(dashboard, /cycle_id: detailId/);
  assert.match(dashboard, /Cycle details were not found/);
  assert.match(dashboard, /Back to Academic Cycles/);
  assert.match(dashboard, /Loading academic cycles/);
  assert.match(dashboard, /No academic cycles are configured/);
  assert.match(dashboard, /role="alert"/);
  assert.match(dashboard, /Retry/);
});

test("detail dashboard provides the required summary and data tabs", () => {
  for (const label of ["supervisors", "students", "groups", "projects", "active_projects", "completed_projects", "pending_reviews", "required_documents"]) {
    assert.match(dashboard, new RegExp(label));
  }
  for (const tab of ["supervisors", "projects", "groups", "students", "documents"]) {
    assert.match(dashboard, new RegExp(`\"${tab}\"`));
  }
  assert.match(dashboard, /View details/);
  assert.match(dashboard, /No .* are recorded for this cycle/);
});
