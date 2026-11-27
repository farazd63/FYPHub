import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const section = readFileSync(new URL("announcements/AnnouncementSection.tsx", root), "utf8");
const bell = readFileSync(new URL("announcements/AnnouncementBell.tsx", root), "utf8");
const backend = readFileSync(new URL("../../backend/app/announcements.py", import.meta.url), "utf8");
const schema = readFileSync(new URL("../../backend/app/schemas/announcements.py", import.meta.url), "utf8");
const model = readFileSync(new URL("../../backend/app/models/announcement.py", import.meta.url), "utf8");
const migration = readFileSync(new URL("../../backend/alembic/versions/y6n7o8p9q0_announcements.py", import.meta.url), "utf8");

test("announcement dashboard UI supports latest, detail, read, and scoped creation", () => {
  for (const value of ["/api/v1/announcements/latest", "/api/v1/announcements/permissions", "/read`, { method: \"POST\"", "cycles: AnnouncementScopeOption[]", "groups: AnnouncementScopeOption[]", "projects: AnnouncementScopeOption[]", "View details", "View all", "Create announcement"]) assert.match(section, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(section, /latest\?limit=\$\{resultLimit\}/);
  assert.match(section, /announcementRows\.slice\(0, resultLimit\)/);
  assert.match(section, /announcement-card--expanded/);
  assert.match(section, /mostRecentUnreadId/);
  assert.match(section, /highlightedId/);
  assert.match(bell, /mostRecentUnreadId/);
  assert.match(bell, /announcement-bell__item--unread/);
  assert.match(bell, /row\.author_name/);
  assert.match(bell, /row\.author_role/);
  assert.match(section, /aria-expanded=\{expanded\}/);
  assert.doesNotMatch(section, /role=\"dialog\"/);
});

test("announcement backend exposes lifecycle endpoints and central visibility checks", () => {
  for (const value of ["_visible", "status == \"PUBLISHED\"", "expires_at", "announcement_id", "/publish", "/archive", "Students cannot create announcements"]) assert.match(backend, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  for (const value of ["class Announcement", "class AnnouncementRead", "uq_announcement_reads_announcement_user"]) assert.match(model, new RegExp(value));
  for (const value of ["AnnouncementScopeOption", "base.groups", "base.projects"]) assert.match(schema + backend, new RegExp(value));
  for (const value of ["announcements", "announcement_reads", "ck_announcements_status"]) assert.match(migration, new RegExp(value));
});

test("administrator dashboard respects recipient privacy while management stays separate", () => {
  assert.match(backend, /Administrative recipient visibility is intentionally separate from/);
  assert.match(backend, /if role == UserRole\.ADMIN\.value:/);
  assert.match(backend, /if row\.target_type == "ALL_USERS":/);
  assert.match(backend, /if row\.target_type == "ROLE":/);
  assert.match(backend, /return False/);
  assert.match(backend, /if not _visible\(row, actor, session, now\)/);
});
