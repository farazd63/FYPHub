import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (file) => fs.readFileSync(new URL(`../src/${file}`, import.meta.url), "utf8");

test("shared Soft SaaS design system is loaded after the base styles", () => {
  const main = read("main.tsx");
  assert.match(main, /import "\.\/index\.css";/);
  assert.match(main, /import "\.\/auth\.css";/);
  assert.match(main, /import "\.\/design-system\.css";/);
  assert.ok(main.indexOf('import "./index.css";') < main.indexOf('import "./design-system.css";'));
});

test("shared design system defines the floating-shell tokens and accessible surfaces", () => {
  const css = read("design-system.css");
  assert.match(css, /--app-primary:\s*#4169e1/);
  assert.match(css, /--app-page:\s*#f4f7fb/);
  assert.match(css, /border-radius:\s*18px/);
  assert.match(css, /button:focus-visible/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
});

test("authentication uses the light centered card shell without the photo asset", () => {
  const app = read("App.tsx");
  assert.match(app, /className=\{`auth-saas/);
  assert.match(app, /auth-saas__card auth-card/);
  assert.doesNotMatch(app, /signInStudentsImage/);
  assert.match(app, /function AuthPhotoBackground\(\) \{\s+return null;/);
});
