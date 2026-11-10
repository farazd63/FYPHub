import assert from "node:assert/strict";
import fs from "node:fs";

const portal = fs.readFileSync("src/portals/coordinator/CoordinatorPortal.tsx", "utf8");
const overview = fs.readFileSync("src/portals/coordinator/modules/CoordinatorOverview.tsx", "utf8");
const liveList = fs.readFileSync("src/portals/coordinator/modules/CoordinatorLiveList.tsx", "utf8");

assert.match(portal, /Assigned Students & Teams/);
assert.match(portal, /Group Policies/);
assert.match(portal, /Cycle Required Documents/);
assert.match(portal, /Coordinator Decision History/);
assert.match(portal, /Coordinator Audit History/);
assert.match(portal, /CoordinatorOverview/);
assert.match(portal, /AcademicCycleDashboard api=\{api\} routeBase="\/coordinator\/academic-cycles"/);
assert.match(overview, /api\/v1\/academic-cycles/);
assert.match(overview, /credentials: "include"/);
assert.match(liveList, /No records are available/);
assert.match(liveList, /Retry/);
