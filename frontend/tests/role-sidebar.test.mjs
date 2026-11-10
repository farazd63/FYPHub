import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const shared = fs.readFileSync(new URL("portals/shared/RoleSidebar.tsx", root), "utf8");
const supervisor = fs.readFileSync(new URL("portals/supervisor/SupervisorSidebar.tsx", root), "utf8");
const evaluator = fs.readFileSync(new URL("portals/evaluator/EvaluatorSidebar.tsx", root), "utf8");
const coordinator = fs.readFileSync(new URL("portals/coordinator/CoordinatorPortal.tsx", root), "utf8");
const coordinatorSidebar = fs.readFileSync(new URL("portals/coordinator/CoordinatorSidebar.tsx", root), "utf8");
const styles = fs.readFileSync(new URL("portals/shared/role-sidebar.css", root), "utf8");
const profile = fs.readFileSync(new URL("portals/shared/SidebarProfile.tsx", root), "utf8");

test("role sidebars use the shared soft navigation shell", () => {
  assert.match(supervisor, /RoleSidebar/);
  assert.match(evaluator, /RoleSidebar/);
  assert.match(coordinator, /CoordinatorSidebar/);
  assert.match(shared, /aria-current=\{active === item\.id \? "page"/);
  assert.match(shared, /title=\{collapsed \? item\.label/);
  assert.match(shared, /student-sidebar__overlay/);
  assert.match(shared, /student-sidebar__collapse/);
  assert.match(shared, /<svg/);
  assert.match(shared, /SidebarIcon/);
  assert.match(profile, /floating-sidebar__profile/);
  assert.doesNotMatch(supervisor, /icon: "[A-Z]+"/);
  assert.doesNotMatch(evaluator, /\["overview", "Overview"/);
});

test("existing role navigation IDs remain present", () => {
  for (const id of ["overview", "requests", "review", "conversations", "history"]) assert.match(supervisor, new RegExp(`id: "${id}"`));
  for (const id of ["assigned", "capacity", "agent-supervision"]) assert.doesNotMatch(supervisor, new RegExp(`id: "${id}"`));
  for (const id of ["overview", "proposal", "schedule", "history"]) assert.match(evaluator, new RegExp(`id: "${id}"`));
  assert.match(coordinator, /CoordinatorSidebar/);
  for (const label of ["People & Access", "Workspace"]) assert.match(coordinatorSidebar, new RegExp(label.replace(/[&]/g, "\\&")));
});

test("sidebar styling keeps mobile drawer and collapsed tooltip behavior", () => {
  assert.match(styles, /student-sidebar--collapsed/);
  assert.match(styles, /@media \(max-width:767px\)/);
  assert.match(shared, /student-sidebar__overlay--open/);
  assert.match(styles, /role-sidebar__section-heading/);
});

console.log("role-sidebar.test.mjs: all assertions passed");
