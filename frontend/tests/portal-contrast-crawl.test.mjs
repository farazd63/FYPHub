/**
 * Contrast crawl across all five portals.
 * Requires: frontend on :5173, API on :8010, playwright installed.
 * Run: node --test tests/portal-contrast-crawl.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import { pathToFileURL } from "node:url";

const API = process.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8010";
const APP = process.env.FYPHUB_APP_URL || "http://127.0.0.1:5173";
const PASSWORD = process.env.FYPHUB_TEST_PASSWORD || "";

const ACCOUNTS = [
  { role: "ADMIN", email: "23108179@szabist-isb.pk", home: "/admin" },
  { role: "STUDENT", email: "student.demo@gmail.com", home: "/" },
  { role: "SUPERVISOR", email: "hmaza.imran@szabist-isb.pk", home: "/" },
  { role: "COORDINATOR", email: "danish.coordinator@szabist-isb.pk", home: "/" },
  { role: "EVALUATOR", email: "maazmuhammad518@gmail.com", home: "/" },
];

const MEASURE_JS = `(() => {
  const parseColor=(c)=>{if(!c||c==='transparent'||c==='rgba(0, 0, 0, 0)')return null;const m=c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/);if(!m)return null;const a=m[4]===undefined?1:Number(m[4]);if(a<0.05)return null;return [Number(m[1]),Number(m[2]),Number(m[3]),a];};
  const lum=([r,g,b])=>{const f=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b);};
  const blend=(fg,bg)=>{const a=fg[3];return [0,1,2].map(i=>Math.round(fg[i]*a+bg[i]*(1-a)));};
  const bgOf=(el)=>{let n=el;while(n&&n!==document.documentElement){const bg=parseColor(getComputedStyle(n).backgroundColor);if(bg&&bg[3]>=0.95)return bg.slice(0,3);if(bg&&bg[3]>0.05){const parent=bgOf(n.parentElement)||[12,14,18];return blend(bg,parent);}n=n.parentElement;}return [12,14,18];};
  const root=document.querySelector('.admin-shell__content,.student-content,.portal-content,.module3-workspace,.admin-enter')||document.body;
  let total=0,below45=0,samples=[];
  for(const el of root.querySelectorAll('h1,h2,h3,h4,p,span,td,th,label,li,a,button,small,strong,b,legend,dt,dd')){
    const own=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join(' ').trim();
    if(!own)continue;
    const cs=getComputedStyle(el);
    if(cs.visibility==='hidden'||cs.display==='none'||Number(cs.opacity)<0.05)continue;
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
    if(ratio<need){below45++; if(samples.length<8) samples.push({t:own.slice(0,48),ratio:+ratio.toFixed(2),need});}
  }
  return {path:location.pathname,title:document.title,h1:document.querySelector('h1')?.textContent?.trim()||'',total,below45,samples};
})()`;

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    return null;
  }
}

test("source CSS no longer hard-codes navy form-label #344b6b", () => {
  const root = new URL("../src/", import.meta.url);
  const walk = (dir, out = []) => {
    for (const name of fs.readdirSync(dir)) {
      const p = `${dir}/${name}`;
      const st = fs.statSync(p);
      if (st.isDirectory()) walk(p, out);
      else if (name.endsWith(".css")) out.push(p);
    }
    return out;
  };
  const hits = walk(root.pathname).filter((file) => fs.readFileSync(file, "utf8").includes("#344b6b"));
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
  assert.doesNotMatch(progress, /background:\s*#[a-fA-F0-9]{3,8}/); // no raw pastel hex fills
});

test("five-portal contrast crawl visits every nav route", async (t) => {
  const pw = await loadPlaywright();
  if (!pw) {
    t.skip("playwright not installed — run: npm i -D playwright && npx playwright install chromium");
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
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await context.newPage();
      await page.goto(`${APP}/login`, { waitUntil: "networkidle" });
      await page.fill('input[name="email"], input[type="email"], [aria-label="Email"]', account.email).catch(async () => {
        await page.locator("textbox").first().fill(account.email);
      });
      // Prefer labelled fields
      const email = page.getByRole("textbox", { name: /email/i }).first();
      const password = page.getByRole("textbox", { name: /password/i }).first();
      await email.fill(account.email);
      await password.fill(PASSWORD);
      await page.getByRole("button", { name: /^login$/i }).click();
      await page.waitForTimeout(1500);
      assert.match(page.url(), account.role === "ADMIN" ? /\/admin/ : /\/($|\?)/, `${account.role} home URL`);

      const openNav = async () => {
        const open = page.getByRole("button", { name: /open navigation/i });
        if (await open.count()) {
          try { await open.click({ timeout: 500 }); } catch { /* already open */ }
        }
      };

      await openNav();
      // Expand all section toggles
      for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
        try { await btn.click({ timeout: 400 }); } catch { /* ignore */ }
      }
      await page.waitForTimeout(300);

      const labels = await page.locator("nav button, nav a").evaluateAll((nodes) =>
        [...new Set(nodes.map((n) => (n.textContent || "").replace(/\s+/g, " ").trim()).filter((t) => t && !["×", "⌄", "›"].includes(t) && t.length < 80))]
      );

      const visited = new Set();
      for (const label of labels) {
        if (/collapse|close navigation|open navigation|workspace|people|academic|requirements|project journey|knowledge|requests & review|supervision|history|evaluation|schedule/i.test(label) && !/overview|groups|users|capacity|cycles|templates|documents|archive|progress|supervisor selection|compliance|panel|scoring|decision|assigned|queue|criteria|proposal|capacity|requests$/i.test(label)) {
          // still click section headers to expand, but measure leaf pages mainly
        }
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
          const key = `${account.role}::${navKey}`;
          if (visited.has(key)) return;
          visited.add(key);
          const result = await page.evaluate(MEASURE_JS);
          report.push({ role: account.role, nav: navKey, ...result });
          assert.equal(result.below45, 0, `${account.role} / ${navKey}: ${result.below45} below AA\n${JSON.stringify(result.samples, null, 2)}`);
        };

        await measure(label);

        // Sub-views behind buttons (forms / scheduling / empty & loaded states)
        const subviews = [
          /open panel scheduling/i,
          /panel scheduling/i,
          /add criterion/i,
          /score|evaluate|open evaluation/i,
          /view group|open group|open request/i,
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

      // Phone width: portal home + key forms/tables
      const phoneTargets = {
        ADMIN: [/Supervisor Capacity/i, /Users & Roles/i],
        STUDENT: [/Supervisor Selection/i, /Project Progress/i],
        SUPERVISOR: [/Supervisor Capacity/i, /Decision History/i],
        COORDINATOR: [/Panel Scheduling/i, /Supervisor Requests/i],
        EVALUATOR: [/Scoring & Feedback/i, /Evaluation Queue/i],
      };
      for (const target of phoneTargets[account.role] || []) {
        await openNav();
        for (const btn of await page.locator("nav button[aria-expanded='false']").all()) {
          try { await btn.click({ timeout: 300 }); } catch { /* ignore */ }
        }
        const navBtn = page.getByRole("button", { name: target }).first();
        if (await navBtn.count()) {
          try { await navBtn.click({ timeout: 800 }); await page.waitForTimeout(600); } catch { /* ignore */ }
        }
        await page.setViewportSize({ width: 390, height: 844 });
        await page.waitForTimeout(350);
        const overflow = await page.evaluate(() => {
          const doc = document.documentElement;
          return {
            overflowX: Math.max(doc.scrollWidth, document.body.scrollWidth) - doc.clientWidth,
            w: doc.clientWidth,
            h1: document.querySelector("h1")?.textContent?.trim() || "",
          };
        });
        const contrast = await page.evaluate(MEASURE_JS);
        report.push({
          role: account.role,
          nav: `__phone_390__::${overflow.h1 || target}`,
          below45: contrast.below45,
          total: contrast.total,
          overflowX: overflow.overflowX,
          samples: contrast.samples,
        });
        assert.ok(overflow.overflowX <= 1, `${account.role} phone overflow ${overflow.overflowX} on ${overflow.h1}`);
        assert.equal(contrast.below45, 0, `${account.role} phone contrast on ${overflow.h1}`);
        await page.setViewportSize({ width: 1280, height: 900 });
      }

      await context.close();
    }
  } finally {
    await browser.close();
    const out = new URL("../../docs/audit/ui-redesign/phase-2/contrast-crawl-report.json", import.meta.url);
    fs.mkdirSync(new URL(".", out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify(report, null, 2));
  }
});
