import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (file) => fs.readFileSync(new URL(`../src/${file}`, import.meta.url), "utf8");

test("portal shells unlock document scroll when content is taller than the viewport", () => {
  const index = read("index.css");
  const design = read("design-system.css");
  const tokens = read("design-tokens.css");
  const student = read("portals/student/student.css");
  const portal = read("portals/shared/portal-shell.css");

  // Document-level scroll must be enabled for authenticated shells.
  // Ancestors must stay overflow:visible so sticky header/sidebar keep working.
  assert.match(index, /html:has\(\.admin-shell\)[\s\S]*overflow:\s*visible/);
  assert.match(index, /html:has\(\.student-shell\)[\s\S]*overflow:\s*visible/);
  assert.match(index, /\.admin-shell[\s\S]*overflow:\s*visible/);
  assert.match(index, /\.student-shell[\s\S]*overflow:\s*visible/);
  assert.doesNotMatch(index, /html:has\(\.admin-shell\)[\s\S]{0,180}overflow-x:\s*clip/);

  // Body/content wrappers must not trap scroll with overflow:hidden.
  assert.match(index, /\.admin-shell__body[\s\S]*overflow:\s*visible/);
  assert.match(index, /\.student-shell \.student-body[\s\S]*overflow:\s*visible/);
  assert.match(design, /\.admin-shell__content[\s\S]*overflow:\s*visible\s*!important/);
  assert.match(design, /\.student-shell \.student-content[\s\S]*overflow:\s*visible\s*!important/);
  assert.match(portal, /\.portal-content\s*\{[^}]*overflow:\s*visible/);

  // Fail if the old viewport-lock pattern returns for admin/student shells.
  assert.doesNotMatch(
    index,
    /html:has\(\.admin-shell\)[\s\S]{0,200}overflow:\s*hidden/,
  );
  assert.doesNotMatch(
    index,
    /\.admin-shell\s*>\s*div[\s\S]{0,120}overflow-y:\s*hidden/,
  );

  // Student content historically used overflow:auto; design-system must override it.
  assert.match(student, /\.student-content\{[^}]*overflow:\s*auto/);
  assert.match(design, /overflow:\s*visible\s*!important/);

  // Sticky chrome keeps header/sidebar in place while the document scrolls.
  assert.match(index, /\.admin-shell\s*>\s*header[\s\S]*position:\s*sticky/);
  assert.match(tokens, /--fy-shell-sidebar-top:/);
  assert.match(design, /position:\s*sticky\s*!important/);
});

test("mobile collapsed sidebar does not reserve layout width", () => {
  const design = read("design-system.css");
  const role = read("portals/shared/role-sidebar.css");
  const nav = read("portals/shared/dashboard-nav.css");

  assert.match(design, /@media \(max-width: 767px\)[\s\S]*flex:\s*0 0 0\s*!important/);
  assert.match(role, /@media \(max-width: 767px\)[\s\S]*flex:\s*0 0 0\s*!important/);
  assert.match(nav, /@media \(max-width: 767px\)[\s\S]*flex:\s*0 0 0\s*!important/);
});

test("sidebar uses one shared top offset with content padding", () => {
  const design = read("design-system.css");
  const tokens = read("design-tokens.css");
  const role = read("portals/shared/role-sidebar.css");

  assert.match(tokens, /--fy-shell-header:\s*4rem/);
  assert.match(tokens, /--fy-shell-pad:/);
  assert.match(tokens, /--fy-shell-sidebar-top:\s*calc\(var\(--fy-shell-header\) \+ var\(--fy-shell-pad\)\)/);
  assert.match(role, /top:\s*var\(--fy-shell-sidebar-top/);
  assert.match(design, /top:\s*var\(--fy-shell-sidebar-top\)\s*!important/);
});
