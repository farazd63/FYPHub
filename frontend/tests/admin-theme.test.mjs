import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const portal = readFileSync(join(here, "../src/AdminPortal.tsx"), "utf8");
const sidebar = readFileSync(join(here, "../src/AdminSidebar.css"), "utf8");
const shared = readFileSync(join(here, "../src/index.css"), "utf8");
const app = readFileSync(join(here, "../src/App.tsx"), "utf8");
const roleSidebar = readFileSync(join(here, "../src/portals/shared/AdminSidebar.tsx"), "utf8");

assert.match(portal, /import ["].\/AdminSidebar\.css["];/);
assert.match(portal, /AdminSidebar/);
assert.match(portal, /Required Documents/);
assert.match(portal, /\/admin\/document-requirements/);
assert.match(portal, /admin-role/);
assert.match(portal, /onToggleSection/);
assert.match(roleSidebar, /RoleSidebar/);
assert.match(app, /AdminPortal api=\{API\}/);
assert.match(sidebar, /\.admin-sidebar\s*,[\s\S]*background:\s*var\(--fy-surface/);
assert.match(sidebar, /aria-current="page"|\[aria-current="page"\]/);
assert.match(shared, /\.admin-enter/);
assert.doesNotMatch(app, /StudentModule3Actions|Submit Short Proposal|Submit Long Proposal/);

console.log("admin-theme.test.mjs: all assertions passed");
