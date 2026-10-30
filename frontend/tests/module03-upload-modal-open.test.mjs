import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const modal = fs.readFileSync(
  new URL("../src/modules/module_03_proposal/components/AdminTemplateUploadModal.tsx", import.meta.url),
  "utf8",
);

test("clicking Upload dynamic baseline opens the Module 03 upload modal", () => {
  assert.match(modal, /const \[isUploadModalOpen, setIsUploadModalOpen\] = useState\(false\)/);
  assert.match(modal, /const openUploadModal = \(\) => \{\s*setIsUploadModalOpen\(true\)/);
  assert.match(modal, /Upload dynamic baseline<\/button>\{isUploadModalOpen && createPortal\(dialog, document\.body\)\}/);
  assert.match(modal, /onClick=\{openUploadModal\}/);
  assert.match(modal, /const dialog = isUploadModalOpen \?/);
});

test("close controls and dialog events cannot immediately dismiss an open modal", () => {
  assert.match(modal, /const closeUploadModal = \(\) => setIsUploadModalOpen\(false\)/);
  assert.match(modal, /onClick=\{closeUploadModal\}/);
  assert.match(modal, /onMouseDown=\{\(event\) => event\.stopPropagation\(\)\}/);
});
