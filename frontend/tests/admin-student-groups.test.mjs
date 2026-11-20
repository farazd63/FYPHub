import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../src/AdminStudentGroups.tsx", import.meta.url), "utf8");

test("student group members table shows cycle-scoped project and supervisor values", () => {
  for (const column of ["Member", "Registration", "Email", "Role", "Project Title", "Supervisor"]) {
    assert.match(source, new RegExp(`>${column}<`));
  }
  assert.match(source, /group\.project\?\.title\?\.trim\(\) \|\| "Not assigned"/);
  assert.match(source, /group\.supervisor\?\.name\?\.trim\(\) \|\| "Not assigned"/);
  assert.match(source, /group\.group_number/);
  assert.match(source, /min-w-\[900px\]/);
});

test("admin group navigation is cycle-first and keeps the selected state in the URL", () => {
  assert.match(source, /api\/v1\/academic-cycles/);
  assert.match(source, /new URLSearchParams\(\{ cycle_id: String\(selectedCycleId\) \}\)/);
  assert.match(source, /group\.academic_cycle_id === selectedCycleId/);
  assert.match(source, /writeSelection\(selectedCycleId, groupId\)/);
  assert.match(source, /document-archive\/cycles\/\$\{selectedCycleId\}\/groups\/\$\{selectedGroupId\}/);
  assert.match(source, /setSelectedGroupId\(null\)/);
});
