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
const portalShell = fs.readFileSync(new URL("portals/shared/PortalShell.tsx", root), "utf8");
const navStyles = fs.readFileSync(new URL("portals/shared/dashboard-nav.css", root), "utf8");

test("all dashboard shells load the shared floating vertical navigation presentation", () => {
  assert.match(main, /dashboard-theme\.css/);
  assert.match(main, /dashboard-nav\.css/);
  for (const source of [admin, student, supervisor, coordinator, evaluatorSidebar]) assert.match(source, /RoleSidebar|AdminSidebar|StudentSidebar|SupervisorSidebar|CoordinatorSidebar/);
  assert.match(roleSidebar, /student-sidebar--collapsed/);
  assert.match(portalShell, /data-sidebar=\{collapsed \? "collapsed" : "expanded"\}/);
  assert.match(portalShell, /portal-header__left/);
  assert.match(navStyles, /\.student-shell \.student-body,/);
  assert.match(navStyles, /flex-direction: row/);
  assert.match(navStyles, /admin-shell \.admin-sidebar/);
  assert.match(navStyles, /student-shell \.student-sidebar/);
  assert.match(navStyles, /border-radius: 24px/);
  assert.match(navStyles, /margin: 16px 0 16px 16px/);
  assert.match(navStyles, /@media \(max-width: 767px\)/);
  assert.match(navStyles, /overflow-y: auto/);
  assert.match(navStyles, /border-radius: 22px/);
  assert.match(navStyles, /width: 236px/);
  assert.match(navStyles, /width: 70px/);
  assert.match(navStyles, /scrollbar-width: thin/);
});

test("role navigation sources retain their existing route data", () => {
  for (const label of ["Workspace", "People & Access", "Academic Setup", "Requirements & Review", "Governance"]) assert.match(admin, new RegExp(label.replace(/[&]/g, "\\&")));
  for (const id of ["overview", "requests", "review", "conversations", "history"]) assert.match(supervisor, new RegExp(id));
  for (const id of ["overview", "queue", "proposal", "schedule", "history"]) assert.match(evaluator, new RegExp(id));
  assert.match(evaluatorSidebar, /student-sidebar__icon/);
  assert.doesNotMatch(evaluatorSidebar, /\[\["overview"[^\]]*"O"/);
  assert.match(student, /StudentSidebar/);
  assert.match(coordinatorSidebar, /Supervisor Requests/);
});

console.log("dashboard-navigation.test.mjs: all assertions passed");
