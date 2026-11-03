import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const portal = readFileSync(join(here, "../src/AdminPortal.tsx"), "utf8");
const sidebar = readFileSync(join(here, "../src/AdminSidebar.css"), "utf8");
const shared = readFileSync(join(here, "../src/index.css"), "utf8");
const app = readFileSync(join(here, "../src/App.tsx"), "utf8");

assert.match(portal, /import ["].\/AdminSidebar\.css["];/);
assert.match(portal, /admin-nav-group-toggle/);
assert.match(portal, /aria-expanded=\{Boolean\(expanded\[group\.id\]\)\}/);
assert.match(portal, /Required Documents/);
assert.match(portal, /\/admin\/document-requirements/);
assert.doesNotMatch(portal, /aria-disabled="true"/);
assert.match(portal, /admin-sidebar-toggle/);
assert.match(portal, /disabled=\{!allowed\}/);
assert.match(app, /AdminPortal api=\{API\}/);
assert.match(sidebar, /\.admin-sidebar\s*\{[\s\S]*background:\s*#10244a/);
assert.match(sidebar, /\.admin-sidebar nav button\[aria-current="page"\]/);
assert.match(sidebar, /\.admin-sidebar \.admin-nav-icon/);
assert.match(shared, /\.admin-enter > section\[aria-labelledby\]/);
assert.match(shared, /\.admin-enter > section:not\(\[aria-labelledby\]\)/);
assert.doesNotMatch(app, /StudentModule3Actions|Submit Short Proposal|Submit Long Proposal/);

console.log("admin-theme.test.mjs: all assertions passed");
