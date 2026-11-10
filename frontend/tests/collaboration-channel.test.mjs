import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ui = readFileSync(new URL("../src/portals/shared/CollaborationChannels.tsx", import.meta.url), "utf8");
const student = readFileSync(new URL("../src/portals/student/StudentPortal.tsx", import.meta.url), "utf8");
const supervisor = readFileSync(new URL("../src/portals/supervisor/SupervisorPortal.tsx", import.meta.url), "utf8");
const backend = readFileSync(new URL("../../backend/app/collaboration_channels.py", import.meta.url), "utf8");
assert.match(ui, /Group Collaboration Channel/);
assert.match(ui, /No supervisor has accepted this group yet/);
assert.match(ui, /No assigned groups are available/);
assert.match(ui, /sender_name/);
assert.match(student, /CollaborationChannels api=\{api\} role="student"/);
assert.match(supervisor, /CollaborationChannels api=\{api\} role="supervisor"/);
assert.match(backend, /ensure_collaboration_channel/);
assert.match(backend, /Archived collaboration channels cannot receive new messages/);
console.log("collaboration-channel.test.mjs: all assertions passed");
