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

test("design tokens define a default Noir theme and a light alternate", () => {
  const css = read("design-tokens.css");
  assert.match(css, /:root\[data-theme="light"\]|:root,\s*:root\[data-theme="light"\]/);
  assert.match(css, /:root\[data-theme="dark"\]/);
  assert.match(css, /--fy-bg:\s*#f4f7fe/i);
  assert.match(css, /--fy-primary:\s*#243ffa/i);
  assert.match(css, /--noir-bg:\s*#0B0D0F/);
  assert.match(css, /--noir-surface:\s*#121518/);
  assert.match(css, /--noir-accent:\s*#D7A25F/);
  assert.match(css, /--noir-success:\s*#3FB984/);
  assert.match(css, /--noir-warning:\s*#D9A441/);
  assert.match(css, /--noir-danger:\s*#D66B6B/);
  assert.match(css, /--fy-page:\s*#0B0D0F/);
  assert.match(css, /--fy-surface:\s*#121518/);
  assert.match(css, /--fy-brand:\s*#D7A25F/);
  assert.match(css, /--fy-radius-card:\s*1\.25rem/);
  assert.match(css, /--fy-shell-sidebar-top/);
});

test("FOUC script applies theme before paint and defaults to Noir", () => {
  const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
  assert.match(html, /fyphub-theme/);
  assert.match(html, /data-theme/);
  assert.match(html, /"dark"/);
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

test("public welcome landing is wired for logged-out home routes", () => {
  const app = read("App.tsx");
  assert.ok(fs.existsSync(new URL("../src/pages/WelcomeLanding.tsx", import.meta.url)));
  assert.match(app, /WelcomeLanding/);
  assert.match(app, /page === "welcome"/);
  assert.match(app, /\/welcome|"welcome"/);
  assert.match(app, /isLandingPath|pathname === "\/"/);
});
