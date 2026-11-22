import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const sourceRoot = new URL("../src/", import.meta.url);
const main = fs.readFileSync(new URL("main.tsx", sourceRoot), "utf8");
const theme = fs.readFileSync(new URL("dashboard-theme.css", sourceRoot), "utf8");
const navigation = fs.readFileSync(new URL("portals/shared/dashboard-nav.css", sourceRoot), "utf8");
const roleSidebar = fs.readFileSync(new URL("portals/shared/role-sidebar.css", sourceRoot), "utf8");
const brand = fs.readFileSync(new URL("portals/shared/FypHubBrand.tsx", sourceRoot), "utf8");

test("all dashboards load the shared reference-inspired theme after base styles", () => {
  assert.match(main, /import "\.\/dashboard-theme\.css";/);
  assert.match(theme, /--dash-canvas:\s*var\(--fy-page/);
  assert.match(theme, /--dash-blue:\s*var\(--fy-brand/);
  assert.match(theme, /student-shell/);
  assert.match(theme, /table/);
  assert.match(theme, /input:not/);
  assert.match(brand, /portal-history-controls/);
  assert.match(theme, /\.portal-history-controls button/);
  assert.match(theme, /border-radius: 7px/);
});

test("shared dashboard navigation keeps the rail, panel, active state, and mobile drawer contract", () => {
  assert.match(navigation, /width: 236px/);
  assert.match(navigation, /width: 70px/);
  assert.match(roleSidebar, /student-sidebar--collapsed/);
  assert.match(roleSidebar, /aria-current="page"|\[aria-current="page"\]/);
  assert.match(roleSidebar, /student-sidebar__overlay--open/);
  assert.match(roleSidebar, /overflow-y: auto/);
  assert.match(roleSidebar, /position: sticky/);
});
