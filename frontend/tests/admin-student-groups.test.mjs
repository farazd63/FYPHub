import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../src/AdminStudentGroups.tsx", import.meta.url), "utf8");

test("student group members table shows cycle-scoped project and supervisor values", () => {
  for (const column of ["Member", "Registration", "Email", "Role", "Project Title", "Supervisor"]) {
    assert.match(source, new RegExp(`>${column}<`));
  }
  assert.match(source, /group\.project\?\.title\?\.\s*trim\(\)\s*\|\|\s*"Not assigned"/);
  assert.match(source, /group\.supervisor\?\.name\?\.\s*trim\(\)\s*\|\|\s*"Not assigned"/);
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

test("group signup names are assigned during admin approval", () => {
  assert.match(source, /group_name_assigned/);
  assert.match(source, /Approve group access/);
  assert.match(source, /official name is generated automatically/);
  assert.match(source, /const generatedName/);
  assert.match(source, /Reject group signup/);
  assert.match(source, /The group will not be able to log in/);
});

test("admin group details can edit, add, and remove members", () => {
  assert.match(source, />Edit members<|Edit members in/);
  assert.match(source, /Update a member(?:&apos;|')s name, registration number, email, or role/);
  assert.match(source, /student-groups\/\$\{memberManagerTarget\.id\}\/members\/\$\{memberId\}/);
  assert.match(source, /method: "PATCH"/);
  assert.match(source, /method: "DELETE"/);
  assert.match(source, /Remove member/);
  assert.match(source, /Add new member/);
  assert.match(source, /Historical submissions and collaboration messages stay available/);
});
