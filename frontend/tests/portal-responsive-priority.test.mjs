/**
 * Priority responsive checks for remaining overflow screens.
 * Run: FYPHUB_TEST_PASSWORD=… node --test tests/portal-responsive-priority.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";

const API = process.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8010";
const APP = process.env.FYPHUB_APP_URL || "http://127.0.0.1:5173";
const PASSWORD = process.env.FYPHUB_TEST_PASSWORD || "";
const WIDTHS = [390, 768, 1024];

const TARGETS = [
  { role: "ADMIN", email: "23108179@szabist-isb.pk", nav: /capacity/i, label: "Supervisor Capacity" },
  { role: "ADMIN", email: "23108179@szabist-isb.pk", nav: /users|roles/i, label: "Users & Roles" },
  { role: "COORDINATOR", email: "danish.coordinator@szabist-isb.pk", nav: /request/i, label: "Supervisor Requests", openDetail: true },
  { role: "EVALUATOR", email: "maazmuhammad518@gmail.com", nav: /proposal/i, label: "Proposal Review" },
];

async function loadPlaywright() {
  try { return await import("playwright"); } catch { return null; }
}

test("priority portal screens do not overflow at 390/768/1024", async (t) => {
  const pw = await loadPlaywright();
  if (!pw) { t.skip("playwright not installed"); return; }
  if (!PASSWORD) { t.skip("FYPHUB_TEST_PASSWORD not set"); return; }
  const health = await fetch(APP).then((r) => r.ok).catch(() => false);
  const apiOk = await fetch(`${API}/docs`).then((r) => r.ok).catch(() => false);
  if (!health || !apiOk) { t.skip(`servers not up`); return; }

  const browser = await pw.chromium.launch({ headless: true });
  const report = [];
  try {
    for (const target of TARGETS) {
      for (const width of WIDTHS) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage();
        await page.goto(`${APP}/login`, { waitUntil: "networkidle" });
        await page.evaluate(() => {
          localStorage.setItem("fyphub-theme", "light");
          document.documentElement.setAttribute("data-theme", "light");
        });
        await page.getByRole("textbox", { name: /email/i }).fill(target.email);
        await page.getByRole("textbox", { name: /password/i }).fill(PASSWORD);
        await page.getByRole("button", { name: /^login$/i }).click();
        await page.waitForTimeout(1400);

        const open = page.getByRole("button", { name: /open navigation/i });
        if (await open.count()) { try { await open.click({ timeout: 400 }); } catch { /* */ } }
        for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
          try { await btn.click({ timeout: 250 }); } catch { /* */ }
        }
        const navBtn = page.getByRole("button", { name: target.nav }).first();
        assert.ok(await navBtn.count(), `${target.label} nav missing`);
        await navBtn.click({ timeout: 800 });
        await page.waitForTimeout(800);

        if (target.openDetail) {
          const detail = page.getByRole("button", { name: /not detected|view|open|team|proposal/i }).first();
          if (await detail.count()) {
            try { await detail.click({ timeout: 600 }); await page.waitForTimeout(600); } catch { /* */ }
          }
        }

        const close = page.getByRole("button", { name: /close navigation/i });
        if (await close.count()) { try { await close.click({ timeout: 400 }); } catch { /* */ } }
        await page.waitForTimeout(200);

        const measure = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
          overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        }));
        report.push({ role: target.role, screen: target.label, width, ...measure });
        assert.equal(
          measure.overflow,
          false,
          `${target.role} ${target.label} @${width}: scrollWidth ${measure.scrollWidth} > ${measure.innerWidth}`,
        );
        await context.close();
      }
    }
  } finally {
    await browser.close();
    const out = new URL("../../docs/audit/ui-redesign/light-mode/responsive-priority.json", import.meta.url);
    fs.mkdirSync(new URL(".", out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify(report, null, 2));
  }
});

const CLIP_JS = `(() => {
  const interesting = [...document.querySelectorAll('p, span, small, strong, button, a, h1, h2, h3, .proposal-ai-summary__body, .proposal-ai-summary__text')];
  const clipped = [];
  const overflowAncestor = (el) => {
    let n = el.parentElement;
    while (n && n !== document.body) {
      const cs = getComputedStyle(n);
      const ox = cs.overflowX;
      const oy = cs.overflowY;
      if (/(hidden|clip)/.test(ox) || /(hidden|clip)/.test(cs.overflow)) return n;
      n = n.parentElement;
    }
    return null;
  };
  for (const el of interesting) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
    if (text.length < 2) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const ancestor = overflowAncestor(el);
    if (!ancestor) continue;
    const ar = ancestor.getBoundingClientRect();
    // Ignore intentional horizontal scroll containers (tables)
    const ancestorCs = getComputedStyle(ancestor);
    if (ancestorCs.overflowX === 'auto' || ancestorCs.overflowX === 'scroll') continue;
    if (r.right > ar.right + 1.5) {
      clipped.push({
        text: text.slice(0, 48),
        tag: el.tagName,
        right: Math.round(r.right),
        ancestorRight: Math.round(ar.right),
        ancestor: (ancestor.className || ancestor.tagName).toString().slice(0, 60),
      });
      if (clipped.length >= 8) break;
    }
  }
  return {
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    clipped,
  };
})()`;

test("no clipped text/buttons at 390 on Proposal Review and Coordinator requests", async (t) => {
  const pw = await loadPlaywright();
  if (!pw) { t.skip("playwright not installed"); return; }
  if (!PASSWORD) { t.skip("FYPHUB_TEST_PASSWORD not set"); return; }
  const health = await fetch(APP).then((r) => r.ok).catch(() => false);
  const apiOk = await fetch(`${API}/docs`).then((r) => r.ok).catch(() => false);
  if (!health || !apiOk) { t.skip("servers not up"); return; }

  const browser = await pw.chromium.launch({ headless: true });
  const report = [];
  try {
    const cases = [
      { email: "maazmuhammad518@gmail.com", nav: /proposal/i, label: "Evaluator Proposal Review", openDetail: false },
      { email: "danish.coordinator@szabist-isb.pk", nav: /request/i, label: "Coordinator Supervisor Requests", openDetail: true },
    ];
    for (const target of cases) {
      const context = await browser.newContext({ viewport: { width: 390, height: 900 } });
      const page = await context.newPage();
      await page.goto(`${APP}/login`, { waitUntil: "networkidle" });
      await page.evaluate(() => {
        localStorage.setItem("fyphub-theme", "light");
        document.documentElement.setAttribute("data-theme", "light");
      });
      await page.getByRole("textbox", { name: /email/i }).fill(target.email);
      await page.getByRole("textbox", { name: /password/i }).fill(PASSWORD);
      await page.getByRole("button", { name: /^login$/i }).click();
      await page.waitForTimeout(1400);
      const open = page.getByRole("button", { name: /open navigation/i });
      if (await open.count()) { try { await open.click({ timeout: 400 }); } catch { /* */ } }
      for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
        try { await btn.click({ timeout: 250 }); } catch { /* */ }
      }
      await page.getByRole("button", { name: target.nav }).first().click({ timeout: 800 });
      await page.waitForTimeout(900);
      if (target.openDetail) {
        const detail = page.getByRole("button", { name: /not detected|view|open|team|proposal/i }).first();
        if (await detail.count()) {
          try { await detail.click({ timeout: 600 }); await page.waitForTimeout(700); } catch { /* */ }
        }
      }
      const close = page.getByRole("button", { name: /close navigation/i });
      if (await close.count()) { try { await close.click({ timeout: 400 }); } catch { /* */ } }
      await page.waitForTimeout(250);
      const result = await page.evaluate(CLIP_JS);
      report.push({ screen: target.label, ...result });
      assert.equal(result.scrollWidth <= result.innerWidth + 1, true, `${target.label} page overflow ${result.scrollWidth}>${result.innerWidth}`);
      assert.equal(result.clipped.length, 0, `${target.label} clipped nodes:\n${JSON.stringify(result.clipped, null, 2)}`);
      await context.close();
    }
  } finally {
    await browser.close();
    const out = new URL("../../docs/audit/ui-redesign/light-mode/responsive-no-clip.json", import.meta.url);
    fs.mkdirSync(new URL(".", out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify(report, null, 2));
  }
});
