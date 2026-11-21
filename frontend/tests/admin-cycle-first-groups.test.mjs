/**
 * Cycle-first behaviour for AdminStudentGroups — no portal screen in this flow mixes
 * multiple cycles in one group list; the client filters by `academic_cycle_id`.
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../src/AdminStudentGroups.tsx", import.meta.url), "utf8");

function groupsForCycle(groups, selectedCycleId) {
  return groups.filter((group) => group.academic_cycle_id === selectedCycleId);
}

const mockGroups = [
  { id: 101, group_name: "Alpha", academic_cycle_id: 1 },
  { id: 102, group_name: "Beta", academic_cycle_id: 1 },
  { id: 201, group_name: "Gamma", academic_cycle_id: 2 },
];

test("groupsForCycle keeps only groups belonging to the selected cycle", () => {
  assert.deepEqual(groupsForCycle(mockGroups, 1).map((g) => g.id), [101, 102]);
  assert.deepEqual(groupsForCycle(mockGroups, 2).map((g) => g.id), [201]);
  assert.equal(groupsForCycle(mockGroups, 99).length, 0);
  assert.match(source, /export function groupsForCycle/);
});

test("mocked API payloads are cycle-scoped before render", () => {
  const fetchForCycle = (cycleId) =>
    Promise.resolve({
      items: [
        { id: 1, group_name: "A-only", academic_cycle_id: 1 },
        { id: 2, group_name: "B-only", academic_cycle_id: 2 },
      ],
    }).then((body) => groupsForCycle(body.items, cycleId));

  return Promise.all([fetchForCycle(1), fetchForCycle(2)]).then(([a, b]) => {
    assert.equal(a.length, 1);
    assert.equal(a[0].group_name, "A-only");
    assert.equal(b.length, 1);
    assert.equal(b[0].group_name, "B-only");
  });
});

test("component source renders cycle cards before a cycle is selected", () => {
  assert.match(source, /aria-label="FYP cycles"/);
  assert.match(source, /selectedCycleId === null && cycles\.length > 0/);
  assert.match(source, /View relevant groups/);
  assert.match(source, /BackButton onClick=\{\(\) => selectCycle\(null\)\}>Back to FYP cycles/);
  assert.doesNotMatch(source, /← Back to FYP cycles/);
  assert.match(source, /onClick=\{\(\) => selectCycle\(null\)\}/);
  assert.match(source, /new URLSearchParams\(\{ cycle_id: String\(selectedCycleId\) \}\)/);
  assert.match(source, /readPositiveId\("cycle_id"\)/);
});

test("cycle-first DOM harness with mocked data", async (t) => {
  let playwright;
  try {
    playwright = await import("playwright");
  } catch {
    t.skip("playwright not installed");
    return;
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><title>Cycle-first harness</title></head>
<body>
    <div id="cycles" aria-label="FYP cycles"></div>
    <section id="groups" hidden>
      <button type="button" id="back">← Back to FYP cycles</button>
      <label>Selected cycle<select id="cycle-select"></select></label>
      <ul id="group-list"></ul>
    </section>
  <script>
    const cycles = [
      { id: 1, display_name: "Cycle A", code: "A" },
      { id: 2, display_name: "Cycle B", code: "B" },
    ];
    const allGroups = [
      { id: 11, group_name: "Group A1", academic_cycle_id: 1 },
      { id: 12, group_name: "Group A2", academic_cycle_id: 1 },
      { id: 21, group_name: "Group B1", academic_cycle_id: 2 },
    ];
    const groupsForCycle = (groups, cycleId) => groups.filter((g) => g.academic_cycle_id === cycleId);
    const params = new URLSearchParams(location.search);
  let selectedCycleId = params.has("cycle_id") ? Number(params.get("cycle_id")) : null;

    const cyclesEl = document.getElementById("cycles");
    const groupsEl = document.getElementById("groups");
    const groupList = document.getElementById("group-list");
    const cycleSelect = document.getElementById("cycle-select");

    function renderCycleCards() {
      cyclesEl.innerHTML = cycles.map((c) => '<button type="button" data-cycle="' + c.id + '">' + c.display_name + '</button>').join("");
      cyclesEl.hidden = false;
      groupsEl.hidden = true;
    }

    function renderGroups(cycleId) {
      const groups = groupsForCycle(allGroups, cycleId);
      groupList.innerHTML = groups.map((g) => "<li>" + g.group_name + "</li>").join("");
      cycleSelect.innerHTML = cycles.map((c) => '<option value="' + c.id + '"' + (c.id === cycleId ? " selected" : "") + ">" + c.display_name + "</option>").join("");
      cyclesEl.hidden = true;
      groupsEl.hidden = false;
    }

    cyclesEl.addEventListener("click", (event) => {
      const button = event.target.closest("[data-cycle]");
      if (!button) return;
      selectedCycleId = Number(button.dataset.cycle);
      renderGroups(selectedCycleId);
    });

    cycleSelect.addEventListener("change", () => {
      selectedCycleId = Number(cycleSelect.value);
      renderGroups(selectedCycleId);
    });

    document.getElementById("back").addEventListener("click", () => {
      selectedCycleId = null;
      renderCycleCards();
    });

    if (selectedCycleId) renderGroups(selectedCycleId);
    else renderCycleCards();
  </script>
</body>
</html>`;

  const browser = await playwright.chromium.launch({ headless: true });
  const page = await browser.newPage();

  await page.setContent(html);
  await page.waitForSelector('[aria-label="FYP cycles"] button');
  assert.equal(await page.locator('[aria-label="FYP cycles"] button').count(), 2);

  await page.click('[data-cycle="1"]');
  await page.waitForSelector("#group-list li");
  assert.deepEqual(await page.locator("#group-list li").allTextContents(), ["Group A1", "Group A2"]);
  assert.equal(await page.locator('#group-list li:has-text("Group B1")').count(), 0);

  await page.selectOption("#cycle-select", "2");
  assert.deepEqual(await page.locator("#group-list li").allTextContents(), ["Group B1"]);

  await page.click("#back");
  await page.waitForSelector('[aria-label="FYP cycles"]:not([hidden])');
  assert.equal(await page.locator('[aria-label="FYP cycles"] button').count(), 2);

  await browser.close();
});
