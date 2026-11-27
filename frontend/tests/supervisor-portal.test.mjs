import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const read = (relative) => fs.readFileSync(path.join(here, "..", "src", ...relative.split("/")), "utf8");

const portal = read("portals/supervisor/SupervisorPortal.tsx");
const sidebar = read("portals/supervisor/SupervisorSidebar.tsx");
const roleSidebar = read("portals/shared/RoleSidebar.tsx");
const overview = read("portals/supervisor/SupervisorOverview.tsx");
const assigned = read("portals/supervisor/SupervisorAssignedTeams.tsx");
const history = read("portals/supervisor/SupervisorDecisionHistory.tsx");
const requestView = read("portals/supervisor/modules/supervisor-requests/SupervisorRequestsPdf.tsx");
const app = read("App.tsx");

for (const label of ["Overview", "Supervisor Requests", "Assigned Students & Teams", "Supervisor Capacity", "Decision History"]) {
  assert.match(sidebar, new RegExp(label.replace(/[&]/g, "\\&")), `${label} should be in supervisor navigation`);
}
assert.match(portal, /SupervisorSidebar/);
assert.match(portal, /SupervisorOverview/);
assert.match(portal, /SupervisorAssignedTeams/);
assert.match(portal, /SupervisorDecisionHistory/);
assert.match(roleSidebar, /aria-current/);
assert.match(roleSidebar, /Collapse navigation/);
assert.match(roleSidebar, /Expand navigation/);
assert.match(roleSidebar, /student-sidebar__overlay/);
assert.match(overview, /supervisor-requests\/supervisor\/queue/);
assert.match(overview, /credentials: "include"/);
assert.match(assigned, /supervisor\/assigned-groups/);
assert.match(assigned, /credentials: "include"/);
assert.match(history, /supervisor-requests\/supervisor\/queue/);
assert.match(requestView, /RequestConversation/);
assert.match(requestView, /supervisor\/requests\/\$\{selected\.id\}\/\$\{action\}/);
assert.match(app, /authUser\?\.role === "SUPERVISOR"/);
console.log("supervisor-portal.test.mjs: all assertions passed");
