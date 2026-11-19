/**
 * Phase 2 review capture: screenshots + layout width checks + phone overflow.
 * Requires FE :5173, API :8010, playwright.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const APP = process.env.FYPHUB_APP_URL || "http://127.0.0.1:5173";
const PASSWORD = process.env.FYPHUB_TEST_PASSWORD || "";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/audit/ui-redesign/phase-2");
fs.mkdirSync(OUT, { recursive: true });

async function login(page, email) {
  await page.goto(`${APP}/login`, { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: /email/i }).first().fill(email);
  await page.getByRole("textbox", { name: /password/i }).first().fill(PASSWORD);
  await page.getByRole("button", { name: /^login$/i }).click();
  await page.waitForTimeout(1600);
}

async function openNavItem(page, name) {
  const open = page.getByRole("button", { name: /open navigation/i });
  if (await open.count()) {
    try { await open.click({ timeout: 400 }); } catch { /* open */ }
  }
  for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
    try { await btn.click({ timeout: 250 }); } catch { /* ignore */ }
  }
  const target = page.getByRole("button", { name }).first();
  await target.click({ timeout: 2000 });
  await page.waitForTimeout(900);
}

async function layoutMetrics(page) {
  return page.evaluate(() => {
    const shell = document.querySelector(".admin-shell, .student-shell, main") || document.body;
    const content = document.querySelector(".student-content__inner, .admin-enter, .portal-content__inner");
    const rect = content?.getBoundingClientRect();
    return {
      viewport: window.innerWidth,
      shellWidth: shell.getBoundingClientRect().width,
      contentLeft: rect ? Math.round(rect.left) : null,
      contentRight: rect ? Math.round(rect.right) : null,
      contentWidth: rect ? Math.round(rect.width) : null,
      deadRight: rect ? Math.round(window.innerWidth - rect.right) : null,
    };
  });
}

const shots = [];
const layouts = [];
const phone = [];

const browser = await chromium.launch({ headless: true });
try {
  // Screenshots + layout
  const targets = [
    { email: "hmaza.imran@szabist-isb.pk", nav: /Supervisor Capacity/i, file: "supervisor-capacity.png", role: "SUPERVISOR" },
    { email: "student.demo@gmail.com", nav: /Project Progress/i, file: "student-project-progress.png", role: "STUDENT" },
    { email: "maazmuhammad518@gmail.com", nav: /Scoring & Feedback/i, file: "evaluator-scoring-feedback.png", role: "EVALUATOR" },
    { email: "danish.coordinator@szabist-isb.pk", nav: /Panel Scheduling/i, file: "coordinator-panel-scheduling.png", role: "COORDINATOR" },
  ];

  for (const t of targets) {
    const page = await browser.newPage({ viewport: { width: 1680, height: 1000 } });
    await login(page, t.email);
    await openNavItem(page, t.nav);
    const file = path.join(OUT, t.file);
    await page.screenshot({ path: file, fullPage: true });
    shots.push({ role: t.role, file: t.file, url: page.url(), h1: await page.locator("h1").first().textContent().catch(() => "") });
    for (const w of [1366, 1680, 1920]) {
      await page.setViewportSize({ width: w, height: 1000 });
      await page.waitForTimeout(200);
      layouts.push({ role: t.role, screen: t.file, ...(await layoutMetrics(page)) });
    }
    // phone form check
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);
    phone.push({ role: t.role, screen: t.file, overflowX: overflow });
    await page.close();
  }

  // Login URL + logout email clear smoke (admin)
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await login(page, "23108179@szabist-isb.pk");
    const afterLogin = page.url();
    await page.getByRole("button", { name: /^logout$/i }).first().click();
    await page.waitForTimeout(800);
    const afterLogout = page.url();
    const emailVal = await page.getByRole("textbox", { name: /email/i }).first().inputValue().catch(() => "missing");
    fs.writeFileSync(path.join(OUT, "auth-url-smoke.json"), JSON.stringify({ afterLogin, afterLogout, emailVal }, null, 2));
    await page.close();
  }
} finally {
  await browser.close();
}

fs.writeFileSync(path.join(OUT, "layout-width-check.json"), JSON.stringify(layouts, null, 2));
fs.writeFileSync(path.join(OUT, "phone-form-check.json"), JSON.stringify(phone, null, 2));
fs.writeFileSync(path.join(OUT, "screenshot-index.json"), JSON.stringify(shots, null, 2));
console.log(JSON.stringify({ shots, layouts, phone }, null, 2));
