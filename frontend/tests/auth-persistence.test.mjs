import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const app = fs.readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const sourceFiles = fs.globSync ? fs.globSync("src/**/*.{ts,tsx}") : [];

test("login and session validation use the shared API and cookie credentials", () => {
  assert.match(app, /export const API/);
  assert.match(app, /http:\/\/127\.0\.0\.1:8010/);
  assert.match(app, /auth\/login[\s\S]{0,300}credentials: "include"/);
  assert.match(app, /auth\/me[\s\S]{0,160}credentials: "include"/);
  assert.match(app, /sessionResponse\.status === 401/);
  assert.match(app, /Sign-in succeeded, but the browser session could not be confirmed/);
  assert.doesNotMatch(app, /sessionResponse\.status === 401[\s\S]{0,300}signOut\(/);
  assert.doesNotMatch(app, /localStorage|sessionStorage|Authorization:.*Bearer/);
});

test("frontend source does not contain a second local API origin", () => {
  for (const file of sourceFiles) {
    const contents = fs.readFileSync(file, "utf8");
    assert.doesNotMatch(contents, /http:\/\/localhost:8010/);
    if (!file.endsWith("src\\App.tsx") && !file.endsWith("src/App.tsx")) assert.doesNotMatch(contents, /http:\/\/127\.0\.0\.1:8010/);
  }
});

test("academic-cycle bootstrap uses the supported endpoint, response shape, and credentials", () => {
  assert.match(app, /api\/v1\/academic-cycles/);
  assert.match(app, /academic-cycles[\s\S]{0,180}credentials: "include"/);
  assert.match(app, /const data: Cycle\[\] = await response\.json\(\)/);
  assert.match(app, /401:.*session has expired/);
  assert.match(app, /403:.*not authorized/);
  assert.match(app, /404:.*endpoint was not found/);
  assert.match(app, /500:.*backend could not load/);
});

test("development observability captures safe request IDs and categories", () => {
  const observability = fs.readFileSync(new URL("../src/observability.ts", import.meta.url), "utf8");
  assert.match(observability, /X-Request-ID/);
  assert.match(observability, /NETWORK_ERROR/);
  assert.match(observability, /AUTHENTICATION_ERROR/);
  assert.match(observability, /AI_PROVIDER_ERROR/);
  assert.doesNotMatch(observability, /response\.text\(|response\.json\(\)/);
  assert.doesNotMatch(observability, /response\.text\(|response\.json\(\)|localStorage|sessionStorage/);
});
