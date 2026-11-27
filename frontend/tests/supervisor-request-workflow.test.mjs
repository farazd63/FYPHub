import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const read = (relative) => fs.readFileSync(path.join(here, "..", "src", ...relative.split("/")), "utf8");

const student = read("portals/student/modules/SupervisorMatching.tsx");
const studentPortal = read("portals/student/StudentPortal.tsx");
const supervisor = read("portals/supervisor/modules/supervisor-requests/SupervisorRequestsPdf.tsx");
const coordinator = read("portals/coordinator/modules/supervisor-requests/CoordinatorRequestsPdf.tsx");

for (const endpoint of [
  "/supervisor-requests/cycles",
  "/supervisor-requests/supervisors?academic_cycle_id=",
  "/supervisor-requests/mine",
  "/supervisor-matching/lock-status",
]) assert.match(student, new RegExp(endpoint.replace(/[/?=]/g, "\\$&")));
assert.match(student, /supervisor-requests\/manual/);
assert.match(student, /Available supervisors/);
assert.match(student, /Generate request/);
assert.match(student, /status_history/);
assert.match(studentPortal, /SupervisorMatching api=\{api\}/);

assert.match(supervisor, /supervisor\/requests/);
assert.match(supervisor, /RequestConversation/);
assert.match(supervisor, /Request changes/);
assert.match(supervisor, /Reject request/);
assert.match(supervisor, /Accept request/);
assert.match(supervisor, /supervisor\/requests\/\$\{selected\.id\}\/\$\{action\}/);

assert.match(coordinator, /supervisor-requests\/coordinator\/monitor/);
assert.match(coordinator, /extracted_fields/);
assert.doesNotMatch(coordinator, /\/decision/);

console.log("supervisor-request-workflow.test.mjs: all assertions passed");
