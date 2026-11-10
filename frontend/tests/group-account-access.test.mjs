import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

test("public signup is a shared student group account flow", () => {
  assert.match(app, /Create Student Group Account/);
  assert.match(app, /confirm_password: login\.confirm/);
  assert.match(app, new RegExp("/api/v1/team-registration"));
  assert.match(app, /Leader is Member 1/);
  assert.match(app, /minimum/);
  assert.match(app, /Add Member/);
  assert.match(app, /Remove/);
  assert.doesNotMatch(app, /Single Student/);
  assert.doesNotMatch(app, /RoleCards/);
  assert.doesNotMatch(app, /label="University email"/);
  assert.doesNotMatch(app, /registration_number: identifier/);
  assert.match(app, /const payload = \{ email: normalizeEmail\(identifier\), password/);
});

test("local API host follows the browser hostname for cookie sessions", () => {
  assert.match(app, /localBrowserHost/);
  assert.match(app, /configuredApi\.replace/);
});
