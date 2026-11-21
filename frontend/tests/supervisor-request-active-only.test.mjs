import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(here, "..", "src", "portals", "supervisor", "modules", "supervisor-requests", "SupervisorRequestsPdf.tsx"), "utf8");

assert.match(source, /\/api\/v1\/supervisor\/requests`/);
assert.doesNotMatch(source, /supervisor\/requests\?include_history=true/);
assert.match(source, /setSelectedId\(\(current\) => current !== null && !nextRows\.some/);
assert.match(source, /Completed decisions are available in Decision History/);
console.log("supervisor-request-active-only.test.mjs: all assertions passed");
