import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ui = readFileSync(new URL("../src/portals/admin/modules/archive/OldProjectArchiveImport.tsx", import.meta.url), "utf8");
const backend = readFileSync(new URL("../../backend/app/archived_projects.py", import.meta.url), "utf8");
assert.match(ui, /Download official template/);
assert.match(ui, /Preview import/);
assert.match(ui, /Confirm import/);
assert.match(ui, /disabled=\{!cycleId/);
assert.match(backend, /@admin_archive_router\.post\("\/import\/preview"\)/);
assert.match(backend, /@admin_archive_router\.post\("\/import\/confirm"\)/);
assert.match(backend, /academic_cycle_id: int = Form\(\.\.\.\)/);
console.log("archive-import.test.mjs: all assertions passed");
