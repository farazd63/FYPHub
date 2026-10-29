import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const policy = readFileSync(join(here, "../src/passwordPolicy.ts"), "utf8");
const field = readFileSync(join(here, "../src/PasswordField.tsx"), "utf8");
const app = readFileSync(join(here, "../src/App.tsx"), "utf8");
const adminUsers = readFileSync(join(here, "../src/AdminUsersRoles.tsx"), "utf8");
const shell = readFileSync(join(here, "../src/portals/student/student.css"), "utf8");
const supervisor = readFileSync(join(here, "../src/portals/supervisor/SupervisorPortal.tsx"), "utf8");
const supervisorSidebar = readFileSync(join(here, "../src/portals/supervisor/SupervisorSidebar.tsx"), "utf8");
const coordinator = readFileSync(join(here, "../src/portals/coordinator/CoordinatorPortal.tsx"), "utf8");
const evaluator = readFileSync(join(here, "../src/portals/evaluator/EvaluatorPortal.tsx"), "utf8");
const evaluatorSidebar = readFileSync(join(here, "../src/portals/evaluator/EvaluatorSidebar.tsx"), "utf8");

assert.match(policy, /Weak/);
assert.match(policy, /Fair/);
assert.match(policy, /Strong/);
assert.match(policy, /Very Strong/);
assert.match(policy, /uppercase/i);
assert.match(policy, /lowercase/i);
assert.match(policy, /number/i);
assert.match(policy, /special character/i);
assert.match(field, /from "\.\/passwordPolicy"/);
assert.match(field, /type=\{visible \? "text" : "password"\}/);
assert.match(field, /Show.*Hide|Hide.*Show/);
assert.match(app, /passwordPolicyError\(single\.password\)/);
assert.match(app, /autoComplete="current-password"\s+guidance/);
assert.match(adminUsers, /passwordPolicyError\(form\.password\)/);
assert.match(shell, /#10244a/);
assert.match(shell, /student-sidebar__item\[aria-current=page\]/);
assert.match(shell, /prefers-reduced-motion/);
assert.match(supervisor, /Escape/);
for (const portal of [supervisorSidebar, coordinator]) {
  assert.match(portal, /student-sidebar__collapse/);
  assert.match(portal, /student-sidebar__overlay/);
}
assert.match(coordinator, /Escape/);
assert.match(evaluatorSidebar, /student-sidebar__collapse/);
assert.match(evaluatorSidebar, /student-sidebar__overlay/);
assert.match(evaluator, /Escape/);
assert.match(app, /authUser\?\.role === "PANEL_MEMBER"/);
assert.doesNotMatch(field, /Medium/);

console.log("password-policy.test.mjs: all assertions passed");
