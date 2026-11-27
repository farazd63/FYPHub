/**
 * Contrast crawl across all five portals AND public screens, in BOTH themes.
 * Requires: frontend on :5173, API on :8010, playwright installed.
 * Run: FYPHUB_TEST_PASSWORD=… node --test tests/portal-contrast-crawl.test.mjs
 * Disabled controls are NOT exempt from AA.
 */
import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const API = process.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8010";
const APP = process.env.FYPHUB_APP_URL || "http://127.0.0.1:5173";
const PASSWORD = process.env.FYPHUB_TEST_PASSWORD || "";
const THEMES = ["light", "dark"];

const ACCOUNTS = [
  { role: "ADMIN", email: "23108179@szabist-isb.pk", home: "/admin" },
  { role: "STUDENT", email: "student.demo@gmail.com", home: "/" },
  { role: "SUPERVISOR", email: "hmaza.imran@szabist-isb.pk", home: "/" },
  { role: "COORDINATOR", email: "danish.coordinator@szabist-isb.pk", home: "/" },
  { role: "EVALUATOR", email: "maazmuhammad518@gmail.com", home: "/" },
];

const PUBLIC_PATHS = [
  { nav: "landing", path: "/welcome" },
  { nav: "sign-in", path: "/login" },
  { nav: "sign-up", path: "/signup" },
  { nav: "forgot-password", path: "/recover" },
];

const MEASURE_JS = `(() => {
  const theme=document.documentElement.getAttribute('data-theme')||'light';
  const fallback=theme==='light'?[244,247,254]:[12,14,18];
  const parseColor=(c)=>{if(!c||c==='transparent'||c==='rgba(0, 0, 0, 0)')return null;const m=c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/);if(!m)return null;const a=m[4]===undefined?1:Number(m[4]);if(a<0.05)return null;return [Number(m[1]),Number(m[2]),Number(m[3]),a];};
  const lum=([r,g,b])=>{const f=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b);};
  const blend=(fg,bg)=>{const a=fg[3];return [0,1,2].map(i=>Math.round(fg[i]*a+bg[i]*(1-a)));};
  const bgOf=(el)=>{let n=el;while(n&&n!==document.documentElement){const bg=parseColor(getComputedStyle(n).backgroundColor);if(bg&&bg[3]>=0.95)return bg.slice(0,3);if(bg&&bg[3]>0.05){const parent=bgOf(n.parentElement)||fallback;return blend(bg,parent);}n=n.parentElement;}return fallback.slice();};
  const root=document.querySelector('.admin-shell__content,.student-content,.portal-content,.module3-workspace,.admin-enter,.auth-stage,.welcome-landing')||document.body;
  let total=0,below45=0,samples=[];
  for(const el of root.querySelectorAll('h1,h2,h3,h4,p,span,td,th,label,li,a,button,small,strong,b,legend,dt,dd')){
    const own=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join(' ').trim();
    if(!own)continue;
    const cs=getComputedStyle(el);
    if(cs.visibility==='hidden'||cs.display==='none')continue;
    const r=el.getBoundingClientRect();
    if(r.width<2||r.height<2)continue;
    const fg=parseColor(cs.color); if(!fg)continue;
    const bg=bgOf(el);
    const solid=fg[3]<0.99?blend(fg,bg):fg.slice(0,3);
    const ratio=(Math.max(lum(solid),lum(bg))+0.05)/(Math.min(lum(solid),lum(bg))+0.05);
    const fontSize=parseFloat(cs.fontSize);
    const bold=Number(cs.fontWeight)>=600;
    const large=fontSize>=24||(fontSize>=18.66&&bold);
    const need=large?3:4.5;
    total++;
    if(ratio<need){below45++; if(samples.length<8) samples.push({t:own.slice(0,48),ratio:+ratio.toFixed(2),need,disabled:el.matches(':disabled,[aria-disabled="true"]')});}
  }
  return {path:location.pathname,theme,title:document.title,h1:document.querySelector('h1')?.textContent?.trim()||'',total,below45,samples};
})()`;

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    return null;
  }
}

async function applyTheme(page, theme) {
  await page.evaluate((next) => {
    localStorage.setItem("fyphub-theme", next);
    document.documentElement.setAttribute("data-theme", next);
    document.documentElement.style.colorScheme = next;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", next === "dark" ? "#0c0e12" : "#F4F7FE");
  }, theme);
  await page.waitForTimeout(200);
}

test("source CSS no longer hard-codes navy form-label #344b6b", () => {
  const root = fileURLToPath(new URL("../src/", import.meta.url));
  const walk = (dir, out = []) => {
    for (const name of fs.readdirSync(dir)) {
      const p = `${dir}/${name}`;
      const st = fs.statSync(p);
      if (st.isDirectory()) walk(p, out);
      else if (name.endsWith(".css")) out.push(p);
    }
    return out;
  };
  const hits = walk(root).filter((file) => fs.readFileSync(file, "utf8").includes("#344b6b"));
  assert.deepEqual(hits, [], `leftover #344b6b in ${hits.join(", ")}`);
});

test("progress bars/buttons use theme brand tokens at source", () => {
  const css = fs.readFileSync(new URL("../src/portals/student/student-content.css", import.meta.url), "utf8");
  assert.match(css, /\.progress-bar--violet[\s\S]{0,240}background:\s*var\(--fy-brand\)/);
  assert.match(css, /\.progress-button--violet[\s\S]{0,240}background:\s*var\(--fy-brand\)/);
  assert.match(css, /\.progress-board,\s*\.progress-card[\s\S]{0,200}background:\s*var\(--fy-surface\)/);
  assert.doesNotMatch(css, /background:\s*#bcaeff/);
  const progress = css.slice(css.indexOf("/* Project progress roadmap"));
  assert.doesNotMatch(progress, /background:\s*#fff/);
  assert.doesNotMatch(progress, /background:\s*#[a-fA-F0-9]{3,8}/);
});

test("public and portal contrast crawl runs in both themes", async (t) => {
  const pw = await loadPlaywright();
  if (!pw) {
    t.skip("playwright not installed — run: npm i -D playwright && npx playwright install chromium");
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
    for (const theme of THEMES) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await context.newPage();
      await page.goto(`${APP}/welcome`, { waitUntil: "networkidle" });
      await applyTheme(page, theme);

      for (const pub of PUBLIC_PATHS) {
        await page.goto(`${APP}${pub.path}`, { waitUntil: "networkidle" });
        await applyTheme(page, theme);
        if (pub.nav === "sign-up") {
          for (let step = 1; step <= 3; step++) {
            const next = page.getByRole("button", { name: /^next$/i }).first();
            if (step > 1 && (await next.count()) && !(await next.isDisabled().catch(() => true))) {
              try { await next.click({ timeout: 500 }); await page.waitForTimeout(400); } catch { /* stay */ }
            }
            const result = await page.evaluate(MEASURE_JS);
            report.push({ role: "PUBLIC", theme, nav: `sign-up-step-${step}`, ...result });
            assert.equal(result.below45, 0, `${theme} sign-up step ${step}: ${result.below45} below AA\n${JSON.stringify(result.samples, null, 2)}`);
          }
        } else {
          const result = await page.evaluate(MEASURE_JS);
          report.push({ role: "PUBLIC", theme, nav: pub.nav, ...result });
          assert.equal(result.below45, 0, `${theme} ${pub.nav}: ${result.below45} below AA\n${JSON.stringify(result.samples, null, 2)}`);
        }
      }
      await context.close();

      for (const account of ACCOUNTS) {
        const portalContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        const page = await portalContext.newPage();
        await page.goto(`${APP}/login`, { waitUntil: "networkidle" });
        await applyTheme(page, theme);
        const email = page.getByRole("textbox", { name: /email/i }).first();
        const password = page.getByRole("textbox", { name: /password/i }).first();
        await email.fill(account.email);
        await password.fill(PASSWORD);
        await page.getByRole("button", { name: /^login$/i }).click();
        await page.waitForTimeout(1500);
        assert.match(page.url(), account.role === "ADMIN" ? /\/admin/ : /\/($|\?)/, `${theme} ${account.role} home URL`);
        await applyTheme(page, theme);

        const openNav = async () => {
          const open = page.getByRole("button", { name: /open navigation/i });
          if (await open.count()) {
            try { await open.click({ timeout: 500 }); } catch { /* already open */ }
          }
        };

        await openNav();
        for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
          try { await btn.click({ timeout: 400 }); } catch { /* ignore */ }
        }
        await page.waitForTimeout(300);

        const labels = await page.locator("nav button, nav a").evaluateAll((nodes) =>
          [...new Set(nodes.map((n) => (n.textContent || "").replace(/\s+/g, " ").trim()).filter((t) => t && !["×", "⌄", "›"].includes(t) && t.length < 80))]
        );

        const visited = new Set();
        for (const label of labels) {
          await openNav();
          for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
            try { await btn.click({ timeout: 300 }); } catch { /* ignore */ }
          }
          const target = page.getByRole("button", { name: label, exact: true }).first();
          if (!(await target.count())) continue;
          try {
            await target.click({ timeout: 800 });
          } catch {
            continue;
          }
          await page.waitForTimeout(900);

          const measure = async (navKey) => {
            const key = `${theme}::${account.role}::${navKey}`;
            if (visited.has(key)) return;
            visited.add(key);
            const result = await page.evaluate(MEASURE_JS);
            report.push({ role: account.role, theme, nav: navKey, ...result });
            assert.equal(result.below45, 0, `${theme} ${account.role} / ${navKey}: ${result.below45} below AA\n${JSON.stringify(result.samples, null, 2)}`);
          };

          await measure(label);

          const subviews = [
            /open panel scheduling/i,
            /panel scheduling/i,
            /add criterion/i,
            /score|evaluate|open evaluation/i,
            /view group|open group|open request/i,
            /users|roles/i,
            /capacity/i,
            /proposal review/i,
          ];
          for (const pattern of subviews) {
            const btn = page.getByRole("button", { name: pattern }).first();
            if (!(await btn.count())) continue;
            try {
              await btn.click({ timeout: 600 });
              await page.waitForTimeout(700);
              await measure(`${label} › ${pattern.source.slice(0, 40)}`);
            } catch { /* ignore unavailable */ }
          }
        }

        if (account.role === "ADMIN" && theme === "light") {
          await openNav();
          for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
            try { await btn.click({ timeout: 300 }); } catch { /* */ }
          }
          const usersNav = page.getByRole("button", { name: /users|roles/i }).first();
          if (await usersNav.count()) {
            await usersNav.click({ timeout: 800 }).catch(() => undefined);
            await page.waitForTimeout(900);
            const disabledCheck = await page.evaluate(() => {
              const parseColor = (c) => {
                if (!c || c === "transparent" || c === "rgba(0, 0, 0, 0)") return null;
                const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
                if (!m) return null;
                const a = m[4] === undefined ? 1 : Number(m[4]);
                if (a < 0.05) return null;
                return [Number(m[1]), Number(m[2]), Number(m[3]), a];
              };
              const lum = ([r, g, b]) => {
                const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
                return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
              };
              const blend = (fg, bg) => [0, 1, 2].map((i) => Math.round(fg[i] * fg[3] + bg[i] * (1 - fg[3])));
              const bgOf = (el) => {
                let n = el;
                while (n && n !== document.documentElement) {
                  const bg = parseColor(getComputedStyle(n).backgroundColor);
                  if (bg && bg[3] >= 0.95) return bg.slice(0, 3);
                  if (bg && bg[3] > 0.05) {
                    const parent = bgOf(n.parentElement) || [255, 255, 255];
                    return blend(bg, parent);
                  }
                  n = n.parentElement;
                }
                return [255, 255, 255];
              };
              const fails = [];
              for (const el of document.querySelectorAll('button:disabled, [aria-disabled="true"]')) {
                const text = (el.textContent || "").replace(/\s+/g, " ").trim();
                if (!/remove access|previous|next|deactivate|activate/i.test(text)) continue;
                const cs = getComputedStyle(el);
                const fg = parseColor(cs.color);
                if (!fg) continue;
                const bg = bgOf(el);
                const solid = fg[3] < 0.99 ? blend(fg, bg) : fg.slice(0, 3);
                const ratio = (Math.max(lum(solid), lum(bg)) + 0.05) / (Math.min(lum(solid), lum(bg)) + 0.05);
                if (ratio < 4.5) fails.push({ text: text.slice(0, 40), ratio: +ratio.toFixed(2), opacity: cs.opacity });
              }
              return fails;
            });
            report.push({ role: "ADMIN", theme: "light", nav: "Users & Roles › disabled", below45: disabledCheck.length, samples: disabledCheck, total: disabledCheck.length });
            assert.equal(disabledCheck.length, 0, `light ADMIN Users disabled controls below AA\n${JSON.stringify(disabledCheck, null, 2)}`);
          }
        }

        await portalContext.close();
      }
    }
  } finally {
    await browser.close();
    const out = new URL("../../docs/audit/ui-redesign/light-mode/contrast-crawl-both-themes.json", import.meta.url);
    fs.mkdirSync(new URL(".", out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify(report, null, 2));
    const summary = {};
    for (const row of report) {
      const key = `${row.theme || "?"}::${row.role}`;
      if (!summary[key]) summary[key] = { screens: 0, belowAA: 0 };
      summary[key].screens += 1;
      summary[key].belowAA += row.below45 || 0;
    }
    fs.writeFileSync(
      new URL("../../docs/audit/ui-redesign/light-mode/contrast-crawl-summary.json", import.meta.url),
      JSON.stringify(summary, null, 2),
    );
  }
});
