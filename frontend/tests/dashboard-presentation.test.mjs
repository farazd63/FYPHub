import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const overview = readFileSync(new URL("../src/AdminOverview.tsx", import.meta.url), "utf8");
const cycles = readFileSync(new URL("../src/AdminCycleManager.tsx", import.meta.url), "utf8");
const adminPortal = readFileSync(new URL("../src/AdminPortal.tsx", import.meta.url), "utf8");
const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const globalStyles = readFileSync(new URL("../src/index.css", import.meta.url), "utf8");
const studentOverview = readFileSync(new URL("../src/portals/student/StudentOverview.tsx", import.meta.url), "utf8");

test("academic cycle overview does not render summary columns or administration eyebrow", () => {
  for (const label of ["Total cycles", "Open registrations", "Closed registrations", "Administration"]) assert.doesNotMatch(overview, new RegExp(label));
});

test("dashboard presentation hides role and section eyebrow labels", () => {
  assert.doesNotMatch(cycles, />Academic management<\/p>/);
  assert.doesNotMatch(app, />Administration<\/p>/);
  assert.match(globalStyles, /\.student-overview__eyebrow/);
  assert.match(globalStyles, /\.supervisor-page-heading > p/);
});

test("student overview is notification-only", () => {
  for (const label of ["available areas", "fully implemented", "partial areas", "Available student features", "Open feature"]) {
    assert.doesNotMatch(studentOverview, new RegExp(label));
  }
  assert.match(studentOverview, /api\/v1\/notifications/);
  assert.match(studentOverview, /Notifications/);
});

test("admin navigation does not expose supervisor request monitoring", () => {
  assert.doesNotMatch(adminPortal, /Supervisor Requests/);
  assert.doesNotMatch(adminPortal, /supervisorRequests/);
});
