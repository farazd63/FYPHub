import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(here, "..");
const extensions = new Set([".tsx", ".ts", ".css", ".html", ".json", ".md"]);
const suspicious = new RegExp(
  `[${String.fromCodePoint(0x00c2, 0x00c3, 0x00e2, 0x00ef, 0xfffd)}]`,
  "u",
);

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === "dist") return [];
      return walk(file);
    }
    return extensions.has(path.extname(entry.name)) ? [file] : [];
  });
}

const failures = [];
for (const file of walk(frontendRoot)) {
  const content = fs.readFileSync(file, "utf8");
  if (suspicious.test(content)) failures.push(path.relative(frontendRoot, file));
}

assert.deepEqual(failures, [], `Mojibake or replacement characters found in: ${failures.join(", ")}`);
console.log("encoding.test.mjs: all assertions passed");
