/**
 * Responsive overflow + select-clipping crawl across portal screens.
 * Requires: frontend :5173, API :8010, playwright, FYPHUB_TEST_PASSWORD.
 * Run: FYPHUB_TEST_PASSWORD=… node --test tests/portal-responsive-crawl.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";

const API = process.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8010";
const APP = process.env.FYPHUB_APP_URL || "http://127.0.0.1:5173";
const PASSWORD = process.env.FYPHUB_TEST_PASSWORD || "";
const WIDTHS = [390, 768, 1024];

const ACCOUNTS = [
  { role: "ADMIN", email: "23108179@szabist-isb.pk" },
  { role: "STUDENT", email: "student.demo@gmail.com" },
  { role: "SUPERVISOR", email: "hmaza.imran@szabist-isb.pk" },
  { role: "COORDINATOR", email: "danish.coordinator@szabist-isb.pk" },
  { role: "EVALUATOR", email: "maazmuhammad518@gmail.com" },
];

const MEASURE_JS = `(() => {
  const overflow = document.documentElement.scrollWidth > window.innerWidth + 1;
  const selects = [...document.querySelectorAll('select')].filter((el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 8 && r.height > 8;
  }).slice(0, 40).map((el) => {
    const cs = getComputedStyle(el);
    const padRight = parseFloat(cs.paddingRight) || 0;
    const text = el.options[el.selectedIndex]?.text || '';
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.font = cs.font;
    const textWidth = ctx.measureText(text).width;
    const inner = Math.max(0, el.clientWidth - padRight - 8);
    return {
      clipped: textWidth > inner + 1,
      text: text.slice(0, 40),
      textWidth: Math.round(textWidth),
      inner: Math.round(inner),
      width: Math.round(el.getBoundingClientRect().width),
    };
  });
  return {
    path: location.pathname,
    title: document.title,
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflow,
    clippedSelects: selects.filter((s) => s.clipped).slice(0, 6),
  };
})()`;

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    return null;
  }
}

test("portal responsive overflow and select clipping at 390/768/1024", async (t) => {
  const pw = await loadPlaywright();
  if (!pw) {
    t.skip("playwright not installed");
    return;
  }
  if (!PASSWORD) {
    t.skip("FYPHUB_TEST_PASSWORD not set");
    return;
  }
  const health = await fetch(APP).then((r) => r.ok).catch(() => false);
  const apiOk = await fetch(`${API}/docs`).then((r) => r.ok).catch(() => false);
  if (!health || !apiOk) {
    t.skip(`servers not up (app ${APP}, api ${API})`);
    return;
  }

  const browser = await pw.chromium.launch({ headless: true });
  const report = [];
  try {
    for (const account of ACCOUNTS) {
      for (const width of WIDTHS) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage();
        await page.goto(`${APP}/login`, { waitUntil: "networkidle" });
        await page.evaluate(() => {
          localStorage.setItem("fyphub-theme", "light");
          document.documentElement.setAttribute("data-theme", "light");
        });
        await page.getByRole("textbox", { name: /email/i }).first().fill(account.email);
        await page.getByRole("textbox", { name: /password/i }).first().fill(PASSWORD);
        await page.getByRole("button", { name: /^login$/i }).click();
        await page.waitForTimeout(1400);

        const openNav = async () => {
          const open = page.getByRole("button", { name: /open navigation/i });
          if (await open.count()) {
            try { await open.click({ timeout: 500 }); } catch { /* */ }
          }
        };
        await openNav();
        for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
          try { await btn.click({ timeout: 300 }); } catch { /* */ }
        }

        const labels = await page.locator("nav button, nav a").evaluateAll((nodes) =>
          [...new Set(nodes.map((n) => (n.textContent || "").replace(/\s+/g, " ").trim()).filter((t) => t && t.length < 80 && !["×", "⌄", "›"].includes(t)))]
        );

        const visited = new Set();
        for (const label of labels.slice(0, 18)) {
          await openNav();
          for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
            try { await btn.click({ timeout: 250 }); } catch { /* */ }
          }
          const target = page.getByRole("button", { name: label, exact: true }).first();
          if (!(await target.count())) continue;
          try { await target.click({ timeout: 700 }); } catch { continue; }
          await page.waitForTimeout(700);
          const key = `${account.role}::${width}::${label}`;
          if (visited.has(key)) continue;
          visited.add(key);
          const result = await page.evaluate(MEASURE_JS);
          report.push({ role: account.role, width, nav: label, ...result });
          assert.equal(
            result.overflow,
            false,
            `${account.role} @${width} / ${label}: scrollWidth ${result.scrollWidth} > innerWidth ${result.innerWidth}`,
          );
          assert.equal(
            result.clippedSelects.length,
            0,
            `${account.role} @${width} / ${label}: clipped selects ${JSON.stringify(result.clippedSelects)}`,
          );
        }
        await context.close();
      }
    }
  } finally {
    await browser.close();
    const out = new URL("../../docs/audit/ui-redesign/light-mode/responsive-crawl.json", import.meta.url);
    fs.mkdirSync(new URL(".", out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify(report, null, 2));
  }
});
