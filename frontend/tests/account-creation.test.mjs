import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const app = fs.readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const admin = fs.readFileSync(new URL("../src/AdminUsersRoles.tsx", import.meta.url), "utf8");

test("single and group account creation preserve real success and failure states", () => {
  assert.match(app, /\/api\/v1\/auth\/register/);
  assert.match(app, /\/api\/v1\/team-registration/);
  assert.match(app, /setIndividualSuccess\(true\)/);
  assert.match(app, /setSuccess\(\{\s*teamId/);
  assert.match(app, /Student account could not be created/);
  assert.match(app, /Team account could not be created/);
  assert.match(app, /Go to Login/);
  assert.match(app, /Your entered details were kept/);
});

test("role-specific accounts are created through the Admin endpoint with fixed role values", () => {
  for (const role of ["SUPERVISOR", "COORDINATOR", "PANEL_MEMBER", "ADMIN"]) {
    assert.match(admin, new RegExp(`\\\"${role}\\\"`));
  }
  assert.match(admin, /\/api\/v1\/admin\/users/);
  assert.match(admin, /credentials: "include"/);
  assert.match(admin, /Account created/);
  assert.match(admin, /setFieldError\(detail\(body\)\)/);
});

test("account creation never renders a success login link before an OK response", () => {
  const singleSuccess = app.indexOf("setIndividualSuccess(true)");
  const singleFailure = app.indexOf("Student account could not be created");
  assert.ok(singleFailure < singleSuccess);
  const teamSuccess = app.indexOf("setSuccess({");
  const teamFailure = app.indexOf("Team account could not be created");
  assert.ok(teamFailure < teamSuccess);
});
