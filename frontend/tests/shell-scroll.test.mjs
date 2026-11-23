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
  const scroll = read("portal-scroll.css");

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
  assert.match(scroll, /overflow-y:\s*auto\s*!important/);
  assert.match(scroll, /\.student-shell \.student-content[\s\S]*height:\s*auto\s*!important/);
  assert.match(scroll, /supervisor-page\):not\(:has\(\.student-collab\)\)/);

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

  // Fixed headers and sidebars keep dashboard chrome in place while the
  // document scrolls.
  assert.match(index, /\.admin-shell\s*>\s*header[\s\S]*position:\s*fixed/);
  assert.match(tokens, /--fy-shell-sidebar-top:/);
  assert.match(design, /position:\s*fixed\s*!important/);
  assert.doesNotMatch(design, /margin-left:\s*calc\(var\(--fy-shell-pad\)\s*\+\s*var\(--fy-shell-sidebar-width\)\s*\+\s*var\(--fy-shell-pad\)/);
  assert.doesNotMatch(design, /margin-left:\s*calc\(var\(--fy-shell-pad\)\s*\+\s*var\(--fy-shell-sidebar-collapsed-width\)\s*\+\s*var\(--fy-shell-pad\)/);
  assert.match(design, /Final shell geometry[\s\S]*left:\s*0\s*!important[\s\S]*border-radius:\s*0\s*!important/);
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
  assert.match(design, /\.student-shell \.student-sidebar\.role-sidebar\s*\{[\s\S]*position:\s*fixed\s*!important/);
  assert.match(design, /margin-left:\s*calc\(var\(--fy-shell-pad\) \+ var\(--fy-shell-sidebar-width\)/);
  assert.match(tokens, /--fy-shell-sidebar-width:\s*348px/);
});

test("conversation and supervisor workspaces fill the available pane", () => {
  const layout = read("portals/shared/conversation-layout.css");
  const supervisor = read("portals/supervisor/supervisor-group-workspace.css");
  const scroll = read("portal-scroll.css");

  assert.match(layout, /\.group-ai-page,\s*\.student-collab\s*\{[\s\S]*width:\s*100%;[\s\S]*max-width:\s*none/);
  assert.match(layout, /:has\(\.group-ai-page\) > \.student-body[\s\S]*height:\s*100dvh\s*!important/);
  assert.doesNotMatch(layout, /\.student-shell:has\(\.supervisor-page\) > \.student-body/);
  assert.match(scroll, /supervisor-page\):not\(:has\(\.student-collab\)\)[\s\S]*overflow:\s*visible\s*!important/);
  assert.match(supervisor, /:has\(\.supervisor-page\) \.supervisor-page[\s\S]*width:\s*100%/);
});
