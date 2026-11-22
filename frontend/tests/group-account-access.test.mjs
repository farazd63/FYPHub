import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

test("public signup is a shared student group account flow", () => {
  assert.match(app, /Create Student Group Account/);
  assert.match(app, /confirm_password: login\.confirm/);
  assert.match(app, /\/api\/v1\/auth\/group-signup/);
  assert.match(app, /minimum/);
  assert.match(app, /Add member/);
  assert.match(app, /Remove/);
  assert.doesNotMatch(app, /Single Student/);
  assert.doesNotMatch(app, /RoleCards/);
  assert.doesNotMatch(app, /label="University email"/);
  assert.doesNotMatch(app, /registration_number: identifier/);
  assert.match(app, /const payload = \{ email: normalizeEmail\(identifier\), password/);
  assert.match(app, /const sanitizeMemberValue/);
  assert.match(app, /value\.replace\(\/\[\^\\p\{L\} \]\//);
  assert.match(app, /value\.replace\(\/\[\^0-9\]\//);
  assert.match(app, /inputMode="text"/);
  assert.match(app, /inputMode="numeric"/);
  assert.match(app, /pattern="\[0-9\]\*"/);
  assert.match(app, /Name must be 2–100 letters and spaces only/);
  assert.match(app, /Registration number must contain digits only/);
});

test("local API host follows the browser hostname for cookie sessions", () => {
  assert.match(app, /const browserOrigin/);
  assert.match(app, /const isLocalBackendUrl/);
  assert.match(app, /export const API = !configuredApi \|\| isLocalBackendUrl \? browserOrigin : configuredApi/);
});
