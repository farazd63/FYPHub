import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const sourceFiles = [
  "../src/AdminPortal.tsx",
  "../src/AdminEvaluationRubrics.tsx",
  "../src/App.tsx",
  "../src/portals/evaluator/EvaluatorPortal.tsx",
  "../src/portals/evaluator/EvaluatorSidebar.tsx",
  "../src/portals/evaluator/EvaluatorOverview.tsx",
].map((file) => readFileSync(join(here, file), "utf8"));

const visibleForbiddenLabels = [
  "evaluation rubrics",
  "evaluation rubric",
  "rubric management",
  "rubric configuration",
  "draft rubrics",
  "new rubric",
  "loading draft rubrics",
  "rubric history",
  "rubric name",
  "rubric service",
  "draft rubric",
  "initial draft rubric",
  "create draft rubric",
];

for (const source of sourceFiles) {
  const lower = source.toLowerCase();
  for (const label of visibleForbiddenLabels) {
    assert.equal(lower.includes(label), false, `forbidden user-facing label remains: ${label}`);
  }
  const userFacingCandidate = source
    .replace(/\b\w*rubric\w*\b/gi, "")
    .replace(/evaluation-rubrics?/gi, "")
    .replace(/["']rubrics?["']/gi, "");
  assert.doesNotMatch(userFacingCandidate, /\brubrics?\b/i, "a visible Rubric label remains");
}

assert.match(sourceFiles[0], /["']Evaluation Criteria["']/);
assert.match(sourceFiles[1], /Evaluation Criteria/);
assert.match(sourceFiles[4], /["']Evaluation Criteria["']/);
assert.match(sourceFiles[5], /["']Evaluation Criteria["']/);
assert.match(sourceFiles[1], /evaluation-rubrics/);
assert.match(sourceFiles[1], /Create draft version/);

console.log("evaluation-criteria-labels.test.mjs: all assertions passed");
