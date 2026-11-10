import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const helper = readFileSync(new URL("../src/emailValidation.ts", import.meta.url), "utf8");
const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const admin = readFileSync(new URL("../src/AdminUsersRoles.tsx", import.meta.url), "utf8");

test("shared email validator covers the required address rules and messages", () => {
  assert.match(helper, /exactly one @|atCount/);
  assert.match(helper, /local.*domain/s);
  assert.match(helper, /domain\.includes\("\.\."\)/);
  assert.match(helper, /domain\.startsWith\("\."\)/);
  assert.match(helper, /domain\.endsWith\("\."\)/);
  assert.match(helper, /domain.*\./s);
  assert.match(helper, /Enter a valid email address\./);
  assert.match(helper, /Email must include a valid domain, for example name@example\.com\./);
  assert.match(helper, /trim\(\)\.toLowerCase\(\)/);
});

test("login accepts only a group email identifier", () => {
  assert.match(app, /identifier\.includes\("@"\)/);
  assert.match(app, /emailValidationMessage\(identifier\)/);
  assert.match(app, /const payload = \{ email: normalizeEmail\(identifier\), password/);
  assert.doesNotMatch(app, /payload\.registration_number = identifier/);
  assert.match(app, /onSubmit=\{\(event\) =>/);
  assert.match(app, /type="submit"/);
  assert.match(app, /authSubmitting \|\|/);
});

test("student group and Admin account creation share the same validation", () => {
  assert.doesNotMatch(app, /emailValidationMessage\(account\.email\)/);
  assert.match(app, /emailValidationMessage\(login\.email\)/);
  assert.doesNotMatch(app, /emailValidationMessage\(address\)/);
  assert.match(admin, /emailValidationMessage\(form\.email\)/);
  assert.match(admin, /normalizeEmail\(form\.email\)/);
  assert.match(admin, /disabled=\{busy !== null \|\| Boolean\(emailError\)\}/);
  assert.match(admin, /emailTouched/);
});
