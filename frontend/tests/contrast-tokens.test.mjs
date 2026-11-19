import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (file) => fs.readFileSync(new URL(`../src/${file}`, import.meta.url), "utf8");

const lum = (hex) => {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = Number.parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

const ratio = (a, b) => {
  const [L1, L2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (L1 + 0.05) / (L2 + 0.05);
};

test("portal dark theme is loaded last and remaps light surfaces", () => {
  const main = read("main.tsx");
  assert.match(main, /portals\/shared\/portal-dark\.css/);
  assert.ok(main.indexOf("design-system.css") < main.indexOf("portal-dark.css"));
  const dark = read("portals/shared/portal-dark.css");
  assert.match(dark, /\.bg-white/);
  assert.match(dark, /input\[type="checkbox"\]/);
  assert.match(dark, /\.cycle-overview/);
  assert.match(dark, /\.module3-panel/);
  assert.match(dark, /\.module3-score-ring/);
  assert.match(dark, /\.student-overview__summary/);
  assert.match(dark, /\.supervisor-monitor-summary/);
  assert.match(dark, /\.student-collab/);
  assert.match(dark, /overflow-x:\s*auto/);
  assert.match(dark, /max-width:\s*480px/);
});

test("token pairs meet WCAG AA and projector body threshold", () => {
  const css = read("design-system.css") + read("portals/shared/portal-dark.css");
  const text = css.match(/--fy-text:\s*(#[0-9a-fA-F]{6})/)?.[1];
  const secondary = css.match(/--fy-text-secondary:\s*(#[0-9a-fA-F]{6})/g)?.at(-1)?.match(/#[0-9a-fA-F]{6}/)?.[0];
  const page = css.match(/--fy-page:\s*(#[0-9a-fA-F]{6})/)?.[1];
  const surface = css.match(/--fy-surface:\s*(#[0-9a-fA-F]{6})/)?.[1];
  const brand = css.match(/--fy-brand:\s*(#[0-9a-fA-F]{6})/)?.[1];
  const onBrand = css.match(/--fy-text-on-brand:\s*(#[0-9a-fA-F]{6})/)?.[1];
  assert.ok(text && secondary && page && surface && brand && onBrand);
  assert.ok(ratio(text, page) >= 7, `body on page ${ratio(text, page).toFixed(2)}`);
  assert.ok(ratio(text, surface) >= 7, `body on surface ${ratio(text, surface).toFixed(2)}`);
  assert.ok(ratio(secondary, page) >= 7, `secondary on page ${ratio(secondary, page).toFixed(2)}`);
  assert.ok(ratio(secondary, surface) >= 4.5, `secondary on surface ${ratio(secondary, surface).toFixed(2)}`);
  assert.ok(ratio(brand, page) >= 4.5, `brand on page ${ratio(brand, page).toFixed(2)}`);
  assert.ok(ratio(onBrand, brand) >= 4.5, `on-brand on brand ${ratio(onBrand, brand).toFixed(2)}`);
});

test("legacy light admin card rules are not reintroduced in index.css", () => {
  const index = read("index.css");
  assert.doesNotMatch(index, /\.admin-enter[^{]*\{[^}]*color:\s*#183047/);
  assert.doesNotMatch(index, /\.admin-enter[\s\S]{0,200}background:\s*#fff/);
  assert.doesNotMatch(index, /background:\s*#fbfdff/);
  assert.doesNotMatch(index, /color:\s*#172b4d/);
});
