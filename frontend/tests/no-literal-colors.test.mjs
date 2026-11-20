import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const ALLOWLIST_PATH = fileURLToPath(new URL("./fixtures/literal-color-allowlist.txt", import.meta.url));
const TOKEN_FILES = new Set(["design-tokens.css"]);
const COLOR_RE = /(?:#[0-9a-fA-F]{3,8}\b|(?:rgba?|hsla?)\([^)]*\))/g;

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.(tsx|ts|css|jsx)$/.test(name)) out.push(full);
  }
  return out;
}

function hasLiteral(file) {
  const text = fs.readFileSync(file, "utf8");
  for (const line of text.split(/\n/)) {
    if (/\[class\*=.*#/.test(line) || /\[class\^=.*#/.test(line)) continue;
    COLOR_RE.lastIndex = 0;
    if (COLOR_RE.test(line)) return true;
  }
  return false;
}

test("colour literals only in design-tokens.css (legacy allowlist must shrink, never grow)", () => {
  const allow = new Set(
    fs.readFileSync(ALLOWLIST_PATH, "utf8").split(/\n/).map((s) => s.trim()).filter(Boolean),
  );
  const dirty = [];
  const unexpected = [];
  for (const file of walk(SRC)) {
    const base = path.basename(file);
    const rel = path.relative(SRC, file).replaceAll("\\", "/");
    if (TOKEN_FILES.has(base)) continue;
    if (!hasLiteral(file)) continue;
    dirty.push(rel);
    if (!allow.has(rel)) unexpected.push(rel);
  }
  assert.deepEqual(unexpected, [], `New colour literals outside tokens:\n${unexpected.join("\n")}`);
  // Allowlist must not grow beyond what was recorded
  for (const rel of dirty) assert.ok(allow.has(rel), `not allowlisted: ${rel}`);
});
