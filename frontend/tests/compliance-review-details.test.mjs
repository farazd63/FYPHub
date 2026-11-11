import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const source = fs.readFileSync(new URL("../src/modules/module-3/ProposalComplianceWorkspace.tsx", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../src/modules/module-3/module-3.css", import.meta.url), "utf8");
const compiled = ts.transpileModule(source.replace("function ReportView(", "export function ReportView("), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const require = createRequire(import.meta.url);
const exports = {};
new Function("require", "exports", compiled)(id => id.endsWith(".css") ? {} : id.includes("ProposalAiSummary") ? { ProposalAiSummary: () => null } : require(id), exports);

test("79 percent report displays all five unresolved checks with evidence", () => {
  const report = {
    reportSummary: { score: 79, status: "Review Required", totalIssues: 5, metrics: { passed: 19, failed: 0, partial: 5, total: 24 } },
    categories: [{ name: "Formatting", status: "PARTIAL", detail: "Review", checks: Array.from({ length: 5 }, (_, index) => ({ id: String(index), name: `Check ${index}`, status: "UNVERIFIABLE", expected: "A4", actual: null, evidence: `Reason ${index}: cannot measure.` })) }],
    sectionCompliance: [], violations: [], missingSections: [],
    document: { selectedPage: 1, pageCount: 1, filename: "proposal.pdf", previewText: "Proposal" },
    proposal: { id: 1, title: "Project", version: 1 },
    finalResults: { totalChecks: 24, passed: 19, failed: 0, partial: 5, totalViolations: 0, severityBreakdown: { major: 0, minor: 0, info: 0 } },
  };
  const markup = renderToStaticMarkup(React.createElement(exports.ReportView, { report, submissions: [] }));
  assert.match(markup, /19 of 24 checks passed/);
  assert.match(markup, /0 failed, 5 partial or unverifiable/);
  for (let index = 0; index < 5; index++) assert.ok(markup.includes(`Reason ${index}: cannot measure.`));
  assert.ok(markup.includes("No confirmed failed violations. Partial or unverifiable checks still need attention above."));
  assert.doesNotMatch(markup, /No compliance issues were detected/);
  assert.doesNotMatch(css, /metric:has\([^}]*partial[^}]*\)\{display:none/);
  assert.doesNotMatch(css, /final-metrics>span:nth-child\(4\)[^{]*\{display:none/);
});
