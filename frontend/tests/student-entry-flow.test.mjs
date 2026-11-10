import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "../src/App.tsx"), "utf8");

const actualChoiceStart = source.indexOf('studentMode === null');
const choiceEnd = source.indexOf('studentMode === "single")', actualChoiceStart);
const choice = source.slice(actualChoiceStart, choiceEnd);

assert.notEqual(actualChoiceStart, -1, "student choice state should exist");
assert.match(choice, /Single Student/);
assert.match(choice, />Group</);
assert.doesNotMatch(choice, /1-member|2-member|3-member|Member\s+[123]/i);
assert.match(source, /studentMode === "single"/);
assert.match(source, /studentMode === "group"/);
assert.match(source, /\/api\/v1\/auth\/register/);
assert.match(source, /\/api\/v1\/team-registration/);
assert.match(source, /teamSize > maximum/);
assert.match(source, /function validateSingle\(\)/);
assert.match(source, /function nextStep\(\)/);
const loginStart = source.indexOf('if (page === "in")');
assert.notEqual(loginStart, -1, "active login branch should exist");
const login = source.slice(loginStart);
assert.match(login, /RoleCards[\s\S]*value=\{loginRole\}/);
assert.match(login, /onSubmit=\{\(event\) => \{[\s\S]*?void performLogin\(\)/);
assert.match(login, /type="submit"/);
assert.doesNotMatch(login, /StudentMatching|JoinRequestForm|InviteeResponse/);
assert.doesNotMatch(source, /StudentModule3Actions|Submit Short Proposal|Submit Long Proposal|Proposal Versions/);
assert.doesNotMatch(source, /Compliance & Readiness Check|Previous Projects Archive|Supervisor Meetings|Supervisor Conversations|Project Gap Analysis/);

console.log("student-entry-flow.test.mjs: all assertions passed");
