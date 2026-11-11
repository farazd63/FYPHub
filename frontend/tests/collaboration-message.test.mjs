import assert from "node:assert/strict";
import test from "node:test";
import { sendsOnEnter, validateCollaborationMessage, mergeCollaborationMessages } from "../src/portals/student/modules/collaboration-message.ts";

test("Enter sends; Shift+Enter and IME composition do not", () => {
  assert.equal(sendsOnEnter({ key: "Enter", shiftKey: false, isComposing: false }), true);
  assert.equal(sendsOnEnter({ key: "Enter", shiftKey: true, isComposing: false }), false);
  assert.equal(sendsOnEnter({ key: "Enter", shiftKey: false, isComposing: true }), false);
});
test("blank and oversized messages are rejected without altering code", () => {
  assert.ok(validateCollaborationMessage(" \n\t"));
  assert.ok(validateCollaborationMessage("x".repeat(4001)));
  assert.equal(validateCollaborationMessage("    function run() {\n        return 1;\n    }\n"), null);
});
test("refresh and history pages merge once in chronological ID order", () => {
  assert.deepEqual(mergeCollaborationMessages([{ id: 2, text: "old" }, { id: 1, text: "earlier" }], [{ id: 2, text: "current" }, { id: 3, text: "new" }]), [{ id: 1, text: "earlier" }, { id: 2, text: "current" }, { id: 3, text: "new" }]);
});
