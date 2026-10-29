import assert from "node:assert/strict";
import fs from "node:fs";

const admin = fs.readFileSync(new URL("../src/modules/module_03_proposal/components/AdminTemplateUploadModal.tsx", import.meta.url), "utf8");
const student = fs.readFileSync(new URL("../src/modules/module_03_proposal/ProposalComplianceView.tsx", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../src/modules/module_03_proposal/module03.css", import.meta.url), "utf8");
assert.match(admin, /module-03\/admin\/templates/);
assert.match(admin, /extracted_rules/);
assert.match(student, /student\/proposals\/upload/);
assert.match(student, /student\/proposals\/\$\{proposal\.proposal_id\}\/audit/);
assert.match(student, /check_1/);
assert.match(student, /check_2/);
assert.match(student, /check_3/);
assert.match(student, /advisory/);
assert.match(css, /module03-card/);
console.log("module03-proposal.test.mjs: all assertions passed");
