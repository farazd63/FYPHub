import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const sourceRoot = new URL("../src/", import.meta.url);
const main = fs.readFileSync(new URL("main.tsx", sourceRoot), "utf8");
const theme = fs.readFileSync(new URL("dashboard-theme.css", sourceRoot), "utf8");
const navigation = fs.readFileSync(new URL("portals/shared/dashboard-nav.css", sourceRoot), "utf8");

test("all dashboards load the shared reference-inspired theme after base styles", () => {
  assert.match(main, /import "\.\/dashboard-theme\.css";/);
  assert.match(theme, /--dash-canvas:\s*#e9ebf0/);
  assert.match(theme, /--dash-blue:\s*#4654eb/);
  assert.match(theme, /border-radius:\s*22px/);
  assert.match(theme, /student-shell \.student-sidebar/);
  assert.match(theme, /table/);
  assert.match(theme, /input:not/);
});

test("shared dashboard navigation keeps the rail, panel, active state, and mobile drawer contract", () => {
  assert.match(navigation, /width: 236px/);
  assert.match(navigation, /width: 70px/);
  assert.match(navigation, /margin: 16px 0 16px 16px/);
  assert.match(navigation, /min-height: 42px/);
  assert.match(navigation, /width: 32px/);
  assert.match(navigation, /aria-current="page"/);
  assert.match(navigation, /student-sidebar__overlay--open/);
  assert.match(navigation, /overflow-y: auto/);
});
