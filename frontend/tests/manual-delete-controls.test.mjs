import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");

test("manual configuration surfaces expose guarded delete controls", () => {
  const requirements = source("AdminDocumentRequirementManagerClean.tsx");
  const capacity = source("AdminSupervisorCapacity.tsx");
  const cycles = source("AdminCycleManager.tsx");
  assert.match(requirements, /request\("DELETE"/);
  assert.match(requirements, /item\.status === "DRAFT"/);
  assert.match(requirements, /Delete/);
  assert.match(capacity, /supervisor-capacities\/\$\{policy\.id\}/);
  assert.match(capacity, /method: "DELETE"/);
  assert.match(capacity, /Delete/);
  assert.match(cycles, /group-policy.*DELETE/);
  assert.match(cycles, /academic-cycles\/\$\{row\.id\}.*DELETE/);
});
