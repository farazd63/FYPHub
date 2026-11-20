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

const pick = (block, name) => {
  const direct = block.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`, "i"));
  if (direct) return direct[1].toLowerCase();
  return null;
};

const resolveBrand = (block) => {
  const brand = pick(block, "--fy-brand");
  if (brand) return brand;
  const primary = pick(block, "--fy-primary");
  return primary;
};

test("portal dark theme is loaded last and remaps light surfaces", () => {
  const main = read("main.tsx");
  assert.match(main, /portals\/shared\/portal-dark\.css/);
  assert.ok(main.indexOf("design-system.css") < main.indexOf("portal-dark.css"));
  const dark = read("portals/shared/portal-dark.css");
  assert.match(dark, /html\[data-theme="dark"\]/);
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

test("dark token pairs meet WCAG AA and projector body threshold", () => {
  const css = read("design-tokens.css");
  const block = css.split(':root[data-theme="dark"]')[1] || "";
  const text = pick(block, "--fy-text");
  const secondary = pick(block, "--fy-text-secondary") || pick(block, "--fy-text-muted");
  const page = pick(block, "--fy-page") || pick(block, "--fy-bg");
  const surface = pick(block, "--fy-surface");
  const brand = resolveBrand(block);
  const onBrand = pick(block, "--fy-text-on-brand") || pick(block, "--fy-on-primary");
  assert.ok(text && secondary && page && surface && brand && onBrand);
  assert.ok(ratio(text, page) >= 7, `dark body on page ${ratio(text, page).toFixed(2)}`);
  assert.ok(ratio(text, surface) >= 7, `dark body on surface ${ratio(text, surface).toFixed(2)}`);
  assert.ok(ratio(secondary, page) >= 7, `dark secondary on page ${ratio(secondary, page).toFixed(2)}`);
  assert.ok(ratio(secondary, surface) >= 4.5, `dark secondary on surface ${ratio(secondary, surface).toFixed(2)}`);
  assert.ok(ratio(brand, page) >= 4.5, `dark brand on page ${ratio(brand, page).toFixed(2)}`);
  assert.ok(ratio(onBrand, brand) >= 4.5, `dark on-brand on brand ${ratio(onBrand, brand).toFixed(2)}`);
});

test("light token pairs meet WCAG AA for body text", () => {
  const css = read("design-tokens.css");
  const block = (css.split(':root[data-theme="light"]')[1] || css.split(":root,")[1] || "").split(':root[data-theme="dark"]')[0];
  const text = pick(block, "--fy-text");
  const muted = pick(block, "--fy-text-muted") || pick(block, "--fy-text-secondary");
  const page = pick(block, "--fy-bg") || pick(block, "--fy-page");
  const surface = pick(block, "--fy-surface");
  const primary = pick(block, "--fy-primary") || resolveBrand(block);
  const onPrimary = pick(block, "--fy-on-primary") || pick(block, "--fy-text-on-brand");
  assert.ok(text && muted && page && surface && primary && onPrimary);
  assert.ok(ratio(text, page) >= 4.5, `light body on page ${ratio(text, page).toFixed(2)}`);
  assert.ok(ratio(text, surface) >= 4.5, `light body on surface ${ratio(text, surface).toFixed(2)}`);
  assert.ok(ratio(muted, page) >= 4.5, `light muted on page ${ratio(muted, page).toFixed(2)}`);
  assert.ok(ratio(muted, surface) >= 4.5, `light muted on surface ${ratio(muted, surface).toFixed(2)}`);
  assert.ok(ratio(onPrimary, primary) >= 4.5, `light on-primary on primary ${ratio(onPrimary, primary).toFixed(2)}`);
});

test("legacy light admin card rules are not reintroduced in index.css", () => {
  const index = read("index.css");
  assert.doesNotMatch(index, /\.admin-enter[^{]*\{[^}]*color:\s*#183047/);
  assert.doesNotMatch(index, /\.admin-enter[\s\S]{0,200}background:\s*#fff/);
  assert.doesNotMatch(index, /background:\s*#fbfdff/);
  assert.doesNotMatch(index, /color:\s*#172b4d/);
});
