import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const coordinator = readFileSync(new URL("../src/portals/coordinator/modules/supervisor-requests/CoordinatorRequestsPdf.tsx", import.meta.url), "utf8");
const admin = readFileSync(new URL("../src/portals/admin/modules/supervisor-requests/AdminSupervisorRequestsPdf.tsx", import.meta.url), "utf8");
const conversation = readFileSync(new URL("../src/portals/student/modules/supervisor-selection/RequestConversation.tsx", import.meta.url), "utf8");

test("coordinator and Admin monitoring expose scoped filters and status summaries", () => {
  for (const source of [coordinator, admin]) {
    assert.match(source, /academic_cycle_id/);
    assert.match(source, /supervisor_id/);
    assert.match(source, /from_date/);
    assert.match(source, /to_date/);
    assert.match(source, /CHANGES_REQUESTED/);
    assert.match(source, /capacity_warning/);
    assert.match(source, /status_history/);
  }
  assert.match(coordinator, /coordinator\/monitor/);
  assert.match(admin, /admin\/monitor/);
});

test("monitoring conversations are rendered read-only and no panel controls are added", () => {
  assert.match(coordinator, /<RequestConversation[^>]*readOnly/);
  assert.match(admin, /<RequestConversation[^>]*readOnly/);
  assert.match(conversation, /readOnly = false/);
  assert.match(conversation, /Read-only conversation access/);
});

test("monitoring sources contain no legacy API port or object rendering", () => {
  const legacyPort = "80" + "11";
  for (const source of [coordinator, admin, conversation]) {
    assert.equal(source.includes(legacyPort), false);
    assert.doesNotMatch(source, /\[object Object\]/);
  }
});
