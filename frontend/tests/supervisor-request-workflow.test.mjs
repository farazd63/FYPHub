import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const read = (relative) => fs.readFileSync(path.join(here, "..", "src", ...relative.split("/")), "utf8");
const student = read("portals/student/modules/supervisor-selection/StudentSupervisorSelection.tsx");
const studentPdf = read("portals/student/modules/supervisor-selection/StudentSupervisorSelectionPdf.tsx");
const supervisor = read("portals/supervisor/modules/supervisor-requests/SupervisorRequests.tsx");
const supervisorPdf = read("portals/supervisor/modules/supervisor-requests/SupervisorRequestsPdf.tsx");
const admin = read("portals/admin/modules/supervisor-requests/AdminSupervisorRequests.tsx");
const adminPdf = read("portals/admin/modules/supervisor-requests/AdminSupervisorRequestsPdf.tsx");
const coordinator = read("portals/coordinator/modules/supervisor-requests/CoordinatorRequests.tsx");
const coordinatorPdf = read("portals/coordinator/modules/supervisor-requests/CoordinatorRequestsPdf.tsx");
const app = read("App.tsx");
const references = read("portals/student/modules/supervisor-selection/ProposalReferenceSearch.tsx");
const conversation = read("portals/student/modules/supervisor-selection/RequestConversation.tsx");

for (const endpoint of ["/supervisor-requests/cycles", "/supervisor-requests/supervisors?academic_cycle_id=", "/supervisor-requests/mine"]) assert.match(studentPdf, new RegExp(endpoint.replace(/[/?=]/g, "\\$&")));
for (const text of ["Available supervisors", "one-page proposal PDF", "Extracted preview", "status_history", "Upload replacement and resubmit", "Withdraw"]) assert.match(studentPdf, new RegExp(text.replace(/[&/]/g, "\\$&")));
assert.match(studentPdf, /FormData/);
assert.match(studentPdf, /supervisor-requests\/draft\/.*\/document/);
assert.match(studentPdf, /supervisor-requests\/.*\/confirm/);
assert.match(student, /ProposalReferenceSearch/);
assert.match(studentPdf, /RequestConversation/);
assert.doesNotMatch(studentPdf, /Proposal title<input/);
assert.match(supervisor, /supervisor-requests\/supervisor\/queue/);
assert.match(supervisor, /action, comment/);
assert.match(supervisor, /Accept/);
assert.match(supervisor, /Reject/);
assert.match(supervisor, /Request Changes/);
assert.match(supervisorPdf, /Open original PDF/);
assert.match(supervisorPdf, /extraction_runtime/);
assert.match(admin, /supervisor-requests\/admin\/monitor/);
assert.match(admin, /Read-only monitoring/);
assert.doesNotMatch(admin, /method: "POST"/);
assert.match(adminPdf, /Open original PDF/);
assert.match(adminPdf, /Audit trail/);
assert.match(coordinator, /supervisor-requests\/coordinator\/monitor/);
assert.match(coordinator, /Read-only cycle monitoring/);
assert.doesNotMatch(coordinator, /\/decision/);
assert.match(coordinatorPdf, /Open original PDF/);
assert.match(coordinatorPdf, /extracted_fields/);
assert.match(app, /authUser\?\.role === "STUDENT"/);
assert.match(app, /authUser\?\.role === "SUPERVISOR"/);
assert.match(app, /authUser\?\.role === "COORDINATOR"/);
assert.match(references, /proposal-references\/search/);
assert.match(references, /semantic analysis is unavailable/);
assert.match(conversation, /supervisor-requests\/.*\/conversation/);
assert.match(conversation, /credentials: "include"/);
for (const relative of [
  "portals/supervisor/modules/supervisor-requests/RequestConversation.tsx",
  "portals/coordinator/modules/supervisor-requests/RequestConversation.tsx",
  "portals/admin/modules/supervisor-requests/RequestConversation.tsx",
  "portals/supervisor/modules/supervisor-requests/ProposalReferenceSearch.tsx",
  "portals/coordinator/modules/supervisor-requests/ProposalReferenceSearch.tsx",
  "portals/admin/modules/supervisor-requests/ProposalReferenceSearch.tsx",
]) assert.ok(fs.existsSync(path.join(here, "..", "src", ...relative.split("/"))), `${relative} is missing`);
assert.doesNotMatch(app, /PanelPortal.*supervisor-requests/);

console.log("supervisor-request-workflow.test.mjs: all assertions passed");
