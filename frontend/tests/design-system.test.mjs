import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (file) => fs.readFileSync(new URL(`../src/${file}`, import.meta.url), "utf8");

test("shared design system is loaded after the base styles", () => {
  const main = read("main.tsx");
  assert.match(main, /import "\.\/index\.css";/);
  assert.match(main, /import "\.\/design-system\.css";/);
  assert.match(main, /@fontsource\/ibm-plex-sans\/400\.css/);
  assert.match(main, /@fontsource\/ibm-plex-sans\/600\.css/);
  assert.match(main, /@fontsource\/ibm-plex-sans\/700\.css/);
  assert.match(main, /ThemeProvider/);
  assert.doesNotMatch(fs.readFileSync(new URL("../index.html", import.meta.url), "utf8"), /fonts\.googleapis\.com/);
  assert.ok(main.indexOf('import "./index.css";') < main.indexOf('import "./design-system.css";'));
});

test("design tokens define light default and dark charcoal gold themes", () => {
  const css = read("design-tokens.css");
  assert.match(css, /:root\[data-theme="light"\]|:root,\s*:root\[data-theme="light"\]/);
  assert.match(css, /:root\[data-theme="dark"\]/);
  assert.match(css, /--fy-page:\s*var\(--fy-bg\)|--fy-bg:\s*#f4f7fe/i);
  assert.match(css, /--fy-primary:\s*#243ffa/i);
  assert.match(css, /--fy-page:\s*#0c0e12/);
  assert.match(css, /--fy-surface:\s*#151922/);
  assert.match(css, /--fy-brand:\s*#e0a85c/);
  assert.match(css, /--fy-success:\s*#7ddea0/);
  assert.match(css, /--fy-warning:\s*#e0a85c/);
  assert.match(css, /--fy-danger:\s*#f07178/);
  assert.match(css, /--fy-radius-card:\s*1\.25rem/);
  assert.match(css, /--fy-shell-sidebar-top/);
});

test("FOUC script applies theme before paint and defaults to light", () => {
  const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
  assert.match(html, /fyphub-theme/);
  assert.match(html, /data-theme/);
  assert.match(html, /"light"/);
  assert.match(html, /theme-color/);
});

test("Tailwind theme exposes fy colour tokens via CSS variables", () => {
  const index = read("index.css");
  assert.match(index, /@theme\s+inline\s*\{/);
  assert.match(index, /--color-fy-brand:\s*var\(--fy-brand\)/);
  assert.match(index, /--color-fy-page:\s*var\(--fy-page\)/);
  assert.match(index, /--radius-fy-card:\s*var\(--fy-radius-card\)/);
});

test("auth stage keeps studio panel and theme toggle", () => {
  const app = read("App.tsx");
  const auth = read("auth.css");
  assert.match(app, /auth-stage/);
  assert.match(app, /auth-stage__panel/);
  assert.match(app, /ThemeToggle/);
  assert.match(app, /import "\.\/auth\.css"/);
  assert.match(auth, /\.auth-stage/);
  assert.match(auth, /--fy-brand/);
  assert.match(auth, /\.auth-stage__panel/);
  assert.match(auth, /backdrop-filter:\s*blur/);
  assert.match(app, /bg-fy-brand/);
});

test("portal-dark remaps are scoped to dark theme only", () => {
  const css = read("portals/shared/portal-dark.css");
  assert.match(css, /html\[data-theme="dark"\]/);
});
