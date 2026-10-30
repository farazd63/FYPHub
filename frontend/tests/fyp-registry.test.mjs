import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../src/portals/shared/FypRegistryPage.tsx", import.meta.url), "utf8");
const coordinator = readFileSync(new URL("../src/portals/coordinator/modules/fyp-registry/CoordinatorFypRegistry.tsx", import.meta.url), "utf8");
const admin = readFileSync(new URL("../src/portals/admin/modules/fyp-registry/AdminFypRegistry.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/portals/shared/fyp-registry.css", import.meta.url), "utf8");

test("Coordinator and Admin registry wrappers use the shared authorized page", () => {
  assert.match(coordinator, /scope="coordinator"/);
  assert.match(coordinator, /FYP Students & Projects/);
  assert.match(admin, /scope="admin"/);
  assert.match(admin, /FYP Registry & Project Monitoring/);
  assert.match(page, /api\/v1\/fyp-registry/);
  assert.match(page, /credentials: "include"/);
});

test("registry detail safely formats nested values and keeps admin edits scoped", () => {
  assert.match(page, /const readableValue/);
  assert.doesNotMatch(page, /\{selected\.extracted_proposal_fields\}/);
  assert.match(page, /scope === "admin"/);
  assert.match(page, /admin\/metadata/);
  assert.match(page, /correction_reason/);
});

test("registry modal remains usable inside the viewport", () => {
  assert.match(styles, /position:\s*fixed/);
  assert.match(styles, /max-height:\s*calc\(100vh - 32px\)/);
  assert.match(styles, /overflow-y:\s*auto/);
  assert.match(styles, /overflow-x:\s*auto/);
});

test("registry sources contain no legacy API port or mojibake", () => {
  const legacyPort = "80" + "11";
  for (const source of [page, coordinator, admin, styles]) {
    assert.equal(source.includes(legacyPort), false);
    assert.doesNotMatch(source, /[Ãâï¿½]/);
  }
});
