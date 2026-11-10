import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const app = fs.readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const admin = fs.readFileSync(new URL("../src/AdminUsersRoles.tsx", import.meta.url), "utf8");

test("student group signup remains available and preserves its success state", () => {
  assert.match(app, /\/api\/v1\/student\/group-registration/);
  assert.match(app, /Academic Cycle/);
  assert.match(app, /Group Members/);
  assert.match(app, /Group Credentials/);
  assert.match(app, /group_email/);
  assert.match(app, /members\.map/);
  assert.doesNotMatch(app, /requested_role/);
  assert.doesNotMatch(app, /role-selection/);
  assert.match(app, /setSuccess\(\{\s*teamId/);
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

test("Admin account creation validates email and conditionally sends registration number", () => {
  assert.match(admin, /const \[emailTouched, setEmailTouched\]/);
  assert.match(admin, /setEmailTouched\(true\)/);
  assert.match(admin, /form\.email\.trim\(\)\s*\?\s*emailValidationMessage\(form\.email\)/);
  assert.match(admin, /const emailError = emailTouched/);
  assert.match(admin, /\{emailError && \(/);
  assert.match(admin, /form\.role === "STUDENT" && \(/);
  assert.match(admin, /nextRole === "STUDENT" \? \{\} : \{ registration_number: "" \}/);
  assert.match(admin, /\.\.\.\(form\.role === "STUDENT"/);
  assert.doesNotMatch(admin, /registration_number: form\.registration_number\.trim\(\) \|\| null/);
});

test("registration number is student-only for every other role", () => {
  for (const role of ["SUPERVISOR", "PANEL_MEMBER", "COORDINATOR", "ADMIN"]) {
    assert.match(admin, new RegExp(`"${role}"`));
  }
  assert.match(admin, /\{form\.role === "STUDENT" && \(/);
  assert.match(admin, /nextRole === "STUDENT" \? \{\} : \{ registration_number: "" \}/);
});
