import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const adminPortal = await readFile(new URL("../src/AdminPortal.tsx", import.meta.url), "utf8");

test("demo registration status is fetched only by the authenticated admin shell", () => {
  assert.match(adminPortal, /\/api\/v1\/admin\/registration-mode/);
  assert.match(adminPortal, /credentials:\"include\"/);
  assert.match(adminPortal, /demoWarning/);
  assert.match(adminPortal, /demo_warning/);
  assert.match(adminPortal, /role=\"status\"/);
});

test("registration form behavior remains unchanged and public pages do not fetch mode", async () => {
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /\/api\/v1\/auth\/register/);
  assert.match(app, /\/api\/v1\/team-registration/);
  assert.doesNotMatch(app, /registration-mode/);
  assert.match(app, /emailValidationMessage/);
  assert.match(app, /type=\"submit\"/);
});
