import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const read = (relative) => fs.readFileSync(path.join(here, "..", "src", ...relative.split("/")), "utf8");

const portal = read("portals/supervisor/SupervisorPortal.tsx");
const sidebar = read("portals/supervisor/SupervisorSidebar.tsx");
const overview = read("portals/supervisor/SupervisorOverview.tsx");
const assigned = read("portals/supervisor/SupervisorAssignedTeams.tsx");
const history = read("portals/supervisor/SupervisorDecisionHistory.tsx");
const unavailable = read("portals/supervisor/SupervisorUnavailable.tsx");
const requestView = read("portals/supervisor/modules/supervisor-requests/SupervisorRequestsPdf.tsx");
const app = read("App.tsx");

for (const label of ["Overview", "Supervisor Requests", "Assigned Students & Teams", "Proposal Review", "Supervisor Capacity", "Conversations", "Decision History", "Agentic Supervision"]) {
  assert.match(sidebar, new RegExp(label.replace(/[&]/g, "\\&")), `${label} should be in supervisor navigation`);
}
assert.match(portal, /SupervisorSidebar/);
assert.match(portal, /SupervisorOverview/);
assert.match(portal, /SupervisorAssignedTeams/);
assert.match(portal, /SupervisorDecisionHistory/);
assert.match(portal, /SupervisorUnavailable/);
assert.match(sidebar, /aria-current/);
assert.match(sidebar, /Collapse navigation/);
assert.match(sidebar, /Expand navigation/);
assert.match(sidebar, /student-sidebar__overlay/);
assert.match(overview, /supervisor-requests\/supervisor\/queue/);
assert.match(overview, /credentials: "include"/);
assert.match(assigned, /group-channels\/teams/);
assert.match(assigned, /credentials: "include"/);
assert.match(history, /supervisor-requests\/supervisor\/queue/);
assert.match(requestView, /RequestConversation/);
assert.match(requestView, /ProposalReferenceSearch/);
assert.match(requestView, /supervisor-requests\/.*\/decision/);
assert.match(unavailable, /No supervisor API currently exposes/);
assert.match(app, /authUser\?\.role === "SUPERVISOR"/);
console.log("supervisor-portal.test.mjs: all assertions passed");
