import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

const root = new URL("../src/", import.meta.url);
const read = (name) => readFileSync(new URL(name, root), "utf8");

test("retired registry, roster and workflow pages are absent from admin navigation", () => {
  const portal = read("AdminPortal.tsx");
  assert.doesNotMatch(portal, /FYP Registry|Student Eligibility|Workflow Policies|Audit History|Evaluation Criteria|AdminStudentRoster|AdminWorkflowPolicies|AdminAuditHistory|AdminEvaluationRubrics/);
});

test("retired collaboration verification UI is no longer rendered", () => {
  const channels = read("GroupChannels.tsx");
  const workspace = read("portals/student/modules/Module2Workspace.tsx");
  for (const source of [channels, workspace]) {
    assert.doesNotMatch(source, /TeamInvitations|TeamJoinRequests|TeamMatching|JoinRequestForm|InviteeResponse/);
  }
});

test("retired feature components are removed", () => {
  for (const path of [
    "AdminStudentRoster.tsx",
    "AdminWorkflowPolicies.tsx",
    "AdminAuditHistory.tsx",
    "AdminEvaluationRubrics.tsx",
    "Invitations.tsx",
    "JoinRequests.tsx",
    "TeamMatching.tsx",
    "StudentMatching.tsx",
    "portals/shared/FypRegistryPage.tsx",
  ]) assert.equal(existsSync(new URL(path, root)), false, path);
});
