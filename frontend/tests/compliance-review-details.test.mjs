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

test("comparison report displays six clean fields and strict page numbers", () => {
  const report = {
    reportSummary: { score: 79, status: "Review Required", totalIssues: 5, metrics: { passed: 19, failed: 0, partial: 5, total: 24 } },
    reportMetadata: { reportVersion: "2.0", templateName: "Short University Template", analysisDate: "2026-11-19T00:00:00Z" },
    documentDifferenceIssues: [
      { id: "page-count", category: "Page Layout", severity: "critical", issue: "Page Count", originalTemplate: "1 page", studentDocument: "3 pages", difference: "+2 pages — page limit violated", affectedPages: [1, 2, 3], requiredAction: "Submit exactly one page.", status: "failed" },
      { id: "page-size", category: "Page Layout", severity: "critical", issue: "Page Size", originalTemplate: "A4", studentDocument: "Letter", difference: "Wrong page size", affectedPages: [1, 2, 3], requiredAction: "Convert the document to A4.", status: "failed" },
      { id: "page-numbering", category: "Headers and Footers", severity: "critical", issue: "Page Numbering", originalTemplate: "Page number required on every page", studentDocument: "Page number missing on Page 2", difference: "Page numbering requirement violated", affectedPages: [2], requiredAction: "Add the correct page number.", status: "failed" },
      { id: "font", category: "Font Formatting", severity: "warning", issue: "Font Family", originalTemplate: "Computer Modern", studentDocument: "Arial", difference: "Does not match the approved university template.", affectedPages: [1], requiredAction: "Update the document to match the approved template font family rule.", status: "warning" },
      { id: "heading", category: "Heading Styles", severity: "passed", issue: "Heading Style", originalTemplate: "Heading 1", studentDocument: "Heading 1", difference: "Matches the approved university template.", affectedPages: [1], requiredAction: "No action required.", status: "passed" },
    ],
    categories: [],
    sectionCompliance: [], violations: [], missingSections: [],
    document: { selectedPage: 1, pageCount: 3, filename: "proposal.pdf", previewText: "Proposal" },
    proposal: { id: 1, title: "Project", version: 1 },
    finalResults: { totalChecks: 24, passed: 19, failed: 0, partial: 5, totalViolations: 0, severityBreakdown: { major: 0, minor: 0, info: 0 } },
  };
  const markup = renderToStaticMarkup(React.createElement(exports.ReportView, { report, submissions: [] }));
  for (const label of ["Total Issues", "Critical Issues", "Warnings", "Submission Status", "Critical Violations", "Passed Checks", "Issue", "Original / University Template", "Student Document", "Difference", "Strict Page Number", "Required Action", "Pages 1-3", "Page 2", "Preview Correction Report"]) assert.ok(markup.includes(label), label);
  assert.doesNotMatch(markup, /Raw JSON|document_level|Evidence \/ reason|Not available|Unknown page/);
  assert.doesNotMatch(css, /metric:has\([^}]*partial[^}]*\)\{display:none/);
  assert.doesNotMatch(css, /final-metrics>span:nth-child\(4\)[^{]*\{display:none/);
});
