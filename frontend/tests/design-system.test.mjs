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
  assert.doesNotMatch(fs.readFileSync(new URL("../index.html", import.meta.url), "utf8"), /fonts\.googleapis\.com/);
  assert.ok(main.indexOf('import "./index.css";') < main.indexOf('import "./design-system.css";'));
});

test("design tokens define dark academic surfaces and gold brand", () => {
  const css = read("design-system.css");
  assert.match(css, /--fy-page:\s*#0c0e12/);
  assert.match(css, /--fy-surface:\s*#151922/);
  assert.match(css, /--fy-brand:\s*#e0a85c/);
  assert.match(css, /--fy-success:\s*#7ddea0/);
  assert.match(css, /--fy-warning:\s*#e0a85c/);
  assert.match(css, /--fy-danger:\s*#f07178/);
  assert.match(css, /--fy-radius-card:\s*0\.75rem/);
  assert.match(css, /--fy-radius-control:\s*0\.5rem/);
  assert.match(css, /button:focus-visible/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
});

test("Tailwind theme exposes fy colour tokens for shared components", () => {
  const index = read("index.css");
  assert.match(index, /@theme\s*\{/);
  assert.match(index, /--color-fy-brand:\s*#e0a85c/);
  assert.match(index, /--color-fy-page:\s*#0c0e12/);
  assert.match(index, /--radius-fy-card:\s*0\.75rem/);
});

test("auth stage uses dark studio unified panel with glass dock", () => {
  const app = read("App.tsx");
  const auth = read("auth.css");
  assert.match(app, /auth-stage/);
  assert.match(app, /auth-stage__panel/);
  assert.match(app, /import "\.\/auth\.css"/);
  assert.match(auth, /\.auth-stage/);
  assert.match(auth, /--fy-brand/);
  assert.match(auth, /\.auth-stage__panel/);
  assert.match(auth, /backdrop-filter:\s*blur/);
  assert.match(app, /bg-fy-brand/);
});
