import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const main = fs.readFileSync(new URL("main.tsx", root), "utf8");
const admin = fs.readFileSync(new URL("AdminPortal.tsx", root), "utf8");
const student = fs.readFileSync(new URL("portals/student/StudentPortal.tsx", root), "utf8");
const supervisor = fs.readFileSync(new URL("portals/supervisor/SupervisorPortal.tsx", root), "utf8");
const coordinator = fs.readFileSync(new URL("portals/coordinator/CoordinatorPortal.tsx", root), "utf8");
const coordinatorSidebar = fs.readFileSync(new URL("portals/coordinator/CoordinatorSidebar.tsx", root), "utf8");
const evaluator = fs.readFileSync(new URL("portals/student/modules/StudentEvaluatorPortal.tsx", root), "utf8");
const evaluatorSidebar = fs.readFileSync(new URL("portals/evaluator/EvaluatorSidebar.tsx", root), "utf8");
const roleSidebar = fs.readFileSync(new URL("portals/shared/RoleSidebar.tsx", root), "utf8");
const academicPro = fs.readFileSync(new URL("academic-pro.css", root), "utf8");

test("all dashboard shells load the shared floating vertical navigation presentation", () => {
  assert.match(main, /dashboard-theme\.css/);
  assert.match(main, /academic-pro\.css/);
  for (const source of [admin, student, supervisor, coordinator, evaluatorSidebar]) assert.match(source, /RoleSidebar|AdminSidebar|StudentSidebar|SupervisorSidebar|CoordinatorSidebar/);
  assert.match(roleSidebar, /student-sidebar--collapsed/);
  assert.match(roleSidebar, /role-sidebar__panel/);
  assert.match(roleSidebar, /aria-current/);
  assert.match(academicPro, /--fy-shell-sidebar-width:\s*248px/);
  assert.match(academicPro, /--fy-shell-sidebar-collapsed-width:\s*72px/);
  assert.match(academicPro, /\.student-sidebar\.role-sidebar/);
  assert.match(academicPro, /@media \(max-width: 767px\)/);
  assert.match(academicPro, /background: var\(--fy-sidebar-bg\)/);
});

test("role navigation sources retain their existing route data", () => {
  for (const label of ["Workspace", "People & Access", "Academic Setup", "Requirements & Review"]) assert.match(admin, new RegExp(label.replace(/[&]/g, "\\&")));
  for (const id of ["overview", "requests", "assigned", "capacity", "history"]) assert.match(supervisor, new RegExp(id));
  for (const id of ["overview", "queue", "proposal", "schedule", "history"]) assert.match(evaluator, new RegExp(id));
  assert.match(evaluatorSidebar, /SidebarIcon/);
  assert.doesNotMatch(evaluatorSidebar, /\[\["overview"[^\]]*"O"/);
  assert.match(student, /StudentSidebar/);
  assert.match(coordinatorSidebar, /Supervisor Requests/);
});

console.log("dashboard-navigation.test.mjs: all assertions passed");
