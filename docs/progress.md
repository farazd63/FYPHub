# Project Progress

## M1-H.1 Reminder and Escalation Rule Configuration

- Added cycle-fixed rule identities and numbered configuration versions linked to exact deadline versions, under migration `b3c4d5e6f7a8`. No rules are seeded; recording a newer deadline does not relink existing rules.
- ADMIN-only list, history, create, version and preview use explicit BEFORE/AFTER positive elapsed minutes, calculated in UTC and displayed in the deadline timezone. Elapsed minutes are durations, not local calendar days or university policy. Writes and audit events commit atomically.
- Added the existing Admin navigation destination with configuration, server preview, history and stale-preview protection. No recipients, channels, jobs, delivery or escalation actions are implemented.
- Verified four focused tests, 67 full backend tests, Alembic current/head `b3c4d5e6f7a8` and clean schema check, pip check, frontend lint/build, and git diff check. Browser preview invalidation, save/history and mobile checks remain pending.
- Scheduling, delivery, recipients, operational authority, triggers, stopping conditions, retries and escalation execution remain pending. M1 and P1 remain Partial.

## M1-G.1 Academic Deadline Configuration (2026-10-19)

- Added cycle-fixed `AcademicDeadline` identities and immutable numbered `AcademicDeadlineVersion` records under migration `a2b3c4d5e6f7`. Each version stores an administrator-supplied name, optional description, canonical timezone-aware due instant, IANA timezone, creator, and timestamp; no deadlines were seeded.
- Added ADMIN-only timezone listing, server-authoritative local/UTC preview, cycle-filtered listing, complete history, initial creation, and subsequent-version APIs. Validation rejects unknown zones, offset mismatches, nonexistent local times, and ambiguous local times without an explicit valid offset. Both write endpoints reject naive canonical timestamps without inferring the server timezone. Deployments must provide IANA timezone data; unavailable data yields a sanitized HTTP 503. This environment resolves Asia/Karachi and lists 598 zones using installed tzdata.
- Added the focused **Academic Deadlines** screen in the existing Admin shell with real cycles/timezones, filtering, stale-response protection, required preview invalidation, version selection/history, safe feedback, and duplicate-submit prevention.
- Verified after the timestamp fix: 8 focused deadline tests and 63 full backend tests passed; Alembic current/head are `a2b3c4d5e6f7`, schema check is clean, and `pip check` passed. Frontend lint/build were previously reported as passed. Screenshot evidence confirms the server preview converted **20 October 2026, 17:00 Asia/Karachi** to **12:00 UTC**.
- Browser preview invalidation, save/version-history interactions, and mobile visual verification remain pending.
- This is non-operational configuration only. No submission enforcement, deadline stages, default dates, penalties, grace periods, approval/publication states, reminders, delivery scheduling, or escalation execution exist. M1 and P1 remain Partial.

## M1-F.1 Internal Evaluation Rubric Draft Configuration (2026-10-19)

- Added stable rubric identities with immutable numbered versions and ordered criterion snapshots under Alembic revision `f1a2b3c4d5e6`. Names are required and descriptions optional; no rubric or academic values are seeded.
- Added ADMIN-only list, complete-history, initial-create, and subsequent-version APIs. Mutations enforce browser Origin checks, strict request structure, nonblank names, unique explicit criterion orders, serialized version allocation, and atomic audit persistence.
- Enabled the existing **Evaluation Rubrics** navigation destination and added a focused Draft-labelled Admin screen. It supports history, initial and subsequent versions, criterion add/remove/reorder controls, stable row values and validation mapping, loading/empty/error feedback, and duplicate-submit prevention.
- Verified 5 focused rubric tests and the complete 55-test backend suite. Alembic current/head are `f1a2b3c4d5e6`, schema check is clean, `pip check` passes, and frontend lint/build pass. Browser interaction, responsive visual verification, and the manual demonstration remain pending.
- This is an internal draft-configuration foundation only. Marks, weights, thresholds, evaluation stages, approval/publication/activation/retirement, and panel scoring remain unimplemented pending academic-policy decisions. M1 and P1 remain Partial.

## M1-E.1 Supervisor Capacity Management (verified evidence)

- Added the supervisor-capacity policy model and Alembic revision `e8f9a0b1c2d3`; it has one positive group maximum per supervisor and academic cycle.
- Added ADMIN-only listing, create, and update routes with browser-Origin validation, persisted-role/activity checks, database uniqueness, advisory and row locking, safe failures, and audit events in the same transaction.
- Added the Admin **Supervisor Capacity** screen. User screenshots verify successful policy creation and correct edit-form population, including separate ID-backed supervisor-name selection and read-only supervisor-email display.
- PostgreSQL confirms the applied named `UNIQUE (supervisor_id, academic_cycle_id)` constraint; ORM metadata now declares the same constraint. Alembic current/head are `e8f9a0b1c2d3` and schema check is clean. Capacity tests pass 4/4, the full backend suite passes 50/50, and frontend lint/build pass. Update-save, refreshed-policy persistence, and mobile browser verification remain pending; M1 and P1 remain Partial.

## Admin overview mount (2026-10-16)

- Mounted `AdminOverview` in the existing ADMIN Overview branch. It reads real academic cycles and per-cycle group policies, distinguishes missing policies (`Not configured`) from request failures, and includes loading, empty, retry, and stale-response handling. Browser verification remains pending.

## Admin palette correction (2026-10-16)

- Applied a scoped blue Admin colour system across existing management screens and added a narrower-breakpoint Create Account grid fallback to prevent compressed labels and role text. Browser desktop/mobile verification remains pending.

## Shared theme correction (2026-10-16)

- Added shared application theme tokens and updated shared input, button, focus, and password-strength primitives to use the blue action system. Browser visual verification remains pending; legacy action-colour review remains incomplete.


## M1-D.2 Admin UI (2026-10-15)

- `AdminTemplateReferences.tsx` enables the Proposal Templates destination for ADMIN users. It creates initial references, displays typed supported rule controls, and—after a newly created reference is selected—creates metadata/rule versions and refreshes its returned history. Blank values remain unset and read views show “Not configured”.
- Browser verification remains pending. The list API now returns the stable parent `reference_id` for every metadata-version item, so complete server history can be opened after reload as well as immediately after creation. M1-D remains Partial because publication, storage/download, activation/retirement, and M3 compliance are not implemented.

## M1-D.1 verification (2026-10-15)

- Internal ADMIN-only template-reference and academic-rule versioning is covered by six dedicated tests: strict validation/history, three audit-failure rollbacks, and two-connection metadata allocation.
- The allocation test preserves version 1 and obtains distinct versions 2 and 3 through the production allocator. It stubs audit insertion only for removable concurrency fixtures; audit rollback is tested separately by injected failures.

## Checkpoint finalization (2026-10-16)

- The full backend suite passed 46/46 against `fyphub_p1`; Alembic current and heads are `d5e6f7a8b9c0`, `alembic check` reports no pending operations, and `pip check` passes.
- Frontend lint and production build passed through the installed Node npm executable. Browser interaction and visual verification remain pending; M1-D and P1 remain Partial. No template publication, upload/download, activation/retirement, or M3 compliance checking is implemented.
- The complete backend suite passed: 46 tests. Compilation, Alembic current/heads/check, `pip check`, and `git diff --check` also passed. UI, publication, storage/download, activation/retirement, and M3 compliance remain pending.

## Verified setup

- Project directory created.
- Eight project folders created.
- Git initialized on `main`; no commits yet.
- Python 3.12.10
- Node v24.20.0
- npm 11.19.0
- Git 2.55.0.windows.5
- Docker 29.7.2
- Docker Compose v5.5.1

## Current target

P1 Mid, Modules 1–3.

## Proposal-source reconciliation

- The original `long proposal.pdf` (17 PDF pages) and `short proposal.pdf` (3 PDF pages) were read from `D:\FYP Project` on 2026-10-15.
- The authoritative P1 Mid scope is M1 Admin Dashboard & Academic Management, M2 Student Team & Collaboration Hub, and M3 Student Proposal & AI Compliance Check (long proposal section 9.3, pp9-10; section 10, p14).
- `docs/p1-feature-tracker.md` records every individual M1-M3 proposal feature with source page, implementation/test evidence, gaps, and decisions. `docs/p1-workflows.md` supplies report-ready explanations, actual-versus-proposed workflows, demonstrations, and M1-D blockers.
- M1 and P1 remain incomplete. No screenshots or browser-verification claims were added.

## Implementation status

All module features are not yet implemented.

## Checkpoint 2A

The isolated PostgreSQL + pgvector configuration was created.

## Checkpoint 2B

- Dedicated database container started successfully and its current health is `healthy`.
- Database: `fyphub_p1`.
- Database user: `fyphub_p1_user`.
- Local binding: `127.0.0.1:55732`.
- SQL connection verification passed.
- The `vector` extension was verified at version `0.8.6`.

## Checkpoint 3B

- Minimal FastAPI backend foundation created using `backend/.venv`.
- `GET /health` provides application liveness only and does not claim database connectivity.
- Default Swagger documentation remains available at `/docs`.
- Backend liveness and Swagger/OpenAPI verification passed:
  - `GET /health` returned HTTP 200 with `{"status":"ok","service":"fyphub-p1-api"}`.
  - `GET /docs` returned HTTP 200.
  - `GET /openapi.json` returned HTTP 200, confirmed title `FYPHub API`, and confirmed `GET /health` registration.
- This verification does not verify or claim database connectivity.

## Checkpoint 4A

- Added the PostgreSQL connection foundation using synchronous SQLAlchemy and `postgresql+psycopg`.
- Root `.env` is loaded with an explicit path; its existing password is reused and remains private.
- `GET /health` remains liveness only and does not access the database.
- Added `GET /health/ready`, which verifies `SELECT 1` and the installed `vector` extension, returning a sanitized HTTP 503 response if either check fails.
- Python compilation and dependency integrity checks passed.
- A read-only database check confirmed `fyphub_p1` and `vector` extension version `0.8.6`.
- Runtime endpoint verification passed: `/health` and `/health/ready` both returned HTTP 200.
- An isolated mocked database-failure ASGI request returned the expected sanitized HTTP 503 response; no Docker service or credentials were changed.

## Checkpoint 4B

- Added Alembic migration infrastructure under `backend/alembic` and `backend/alembic.ini`.
- Added the shared SQLAlchemy `Base` and exposed its metadata to Alembic for future models.
- Alembic reuses the application database configuration without storing credentials in `alembic.ini` and supports online and offline modes.
- Python compilation and dependency integrity checks passed.
- Alembic `heads`, `history`, and `current` were verified with no revisions present.
- Database inspection found no public application tables and no `alembic_version` infrastructure table was created.
- Running `/health` and `/health/ready` checks both returned HTTP 200 after the infrastructure changes.

## Checkpoint 5A

- Added the `users` and `user_role` database foundation through Alembic revision `9c227dc337bf`.
- Database rules enforce canonical normalized email and registration-number storage, case-insensitive email uniqueness, registration-number uniqueness when present, valid roles, and required student registration numbers.
- The migration contains no pgvector extension changes and pgvector remains at version `0.8.6`.
- Alembic current matches head; a second autogenerate check found no pending changes.
- Users schema columns, constraints, and indexes were verified. No accounts have been created.
- Running `/health` and `/health/ready` checks both returned HTTP 200 after the migration.
- Authentication, password hashing, account creation, and frontend work remain unimplemented.

## Checkpoint 5B

- Added public `POST /api/v1/auth/register` for student registration only; it cannot assign privileged roles or account activity.
- Added Argon2id password hashing and verification utilities. Passwords are stored only as hashes and are never normalized.
- Duplicate normalized email or registration number handling returns a sanitized HTTP 409 response and rolls back the failed transaction.
- Six database integration tests passed against `fyphub_p1` using rollback-only test transactions; the users table had zero rows before and after the test suite.
- Python compilation and dependency integrity checks passed.
- Running `/health` and `/health/ready` checks both returned HTTP 200 after the registration changes.
- Sign-in, tokens/sessions, authorization, staff creation, and frontend work remain unimplemented.

## Frontend account-flow correction

- Implemented the Create Team Account visual flow with React, Vite, TypeScript, and Tailwind CSS.
- Added local member controls and client-only validation while keeping final submission disabled pending backend team-registration support.
- This supports the P1 Modules 1–3 scope but does not complete any module.
- Added the three-step frontend registration flow and display-only Sign In navigation; API integration remains pending.
- Frontend lint and production build checks passed, and screenshots were reviewed.
- The registration form has a compact numbered three-step progress indicator with completed checkmarks, CSS progress transitions, and a hidden Back button on Step 1.
- Shared-team registration and Sign In remain disabled. Password-strength feedback and backend integration remain pending.
- Animation smoothness remains pending manual confirmation.

## Checkpoint 6A.1

- Added academic cycles and one positive group-size policy per cycle through Alembic revision `3a1f53f17b1c`.
- Read-only cycle and policy APIs are available.
- Module 1 cycle/policy functionality is partial, not complete.

## Local academic configuration bootstrap

- Configured the approved local `FALL-2026` cycle (ID `79`): display name `Fall 2026`, registration open, and maximum group size `3` including the creator.
- The idempotent `scripts/configure_p1_cycle.py` script confirmed target database `fyphub_p1`; a second run made no duplicate records.
- Direct persistence and the running read-only cycle/policy APIs were verified.
- This is local development bootstrap only and does not replace future authenticated Admin configuration.

## Team/member schema verification

- Alembic revision `ce964120f177` is both current and head; `alembic check` found no pending operations.
- The `teams` and `team_members` schema constraints were verified with 9 rollback-isolated constraint tests; the 6 existing registration tests also passed (15 total).
- Test execution targeted `fyphub_p1` and left no test fixture records. The existing demo user remains present.
- Shared-team registration API work is pending. Exactly-one-creator and creator/User consistency will be enforced by that future registration service.

## Shared-team registration API

- Added `POST /api/v1/team-registration` using the applied team/member schema. It locks the selected cycle and policy, validates the actual configured maximum, and commits the shared `STUDENT` user, team, creator, and additional contact-only members atomically.
- Existing users are not adopted or modified. Failures, including a forced late member-insert failure, roll back all newly created records.
- The API returns safe account/team/cycle/member fields and structured, sanitized error codes with field paths where known; passwords, hashes, tokens, and SQL details are never returned.
- All 23 backend tests passed (8 new API tests plus the existing 15); fixture verification confirmed no retained test records in `fyphub_p1`.
- Python compilation, `pip check`, Alembic current/head at `ce964120f177`, and `alembic check` all passed.
- Frontend integration, Admin cycle/policy configuration, sign-in, sessions, and authorization remain pending.

## Shared-team registration frontend integration

- Added non-secret `VITE_API_BASE_URL` configuration and exact-origin backend CORS for `http://127.0.0.1:5174`; wildcard origins and credential support are not enabled.
- The existing three-step form now loads cycles and selected group policies, uses the fetched group maximum including the creator, validates normalized duplicate member identifiers, and submits the exact shared-team registration payload.
- Submission prevents duplicate requests, preserves values after failures, maps safe backend field errors to the affected step and stable member row, and shows a real HTTP `201` confirmation while clearing password fields.
- Sign In now uses the existing cookie-backed session flow; no automatic login is created.
- Frontend lint and production build passed. Backend tests passed: 24 total, including allowed/disallowed CORS verification. Live browser submission and responsive visual verification remain pending.

## Manual shared-team registration verification

- Read-only verification confirmed Team ID `81` in `fyphub_p1` belongs to `FALL-2026`, links to one active `STUDENT` account, and has exactly three active members with one creator.
- The creator registration matches the linked user registration; demo user ID `6` remains active.
- Sign In and session handling remain pending.

## Deadline

Before the 6th; month and year are not yet confirmed.

## Checkpoint 7A

- Added database-backed, opaque browser sessions through Alembic revision `f7a1c3d9e2b4`; only SHA-256 token hashes are persisted, with UTC-aware timestamps, expiry, and revocation.
- Added login, current-user, and idempotent logout APIs. Login uses existing Argon2id verification, a dummy verification for unknown accounts, and session rotation.
- Cookie/CORS/Origin protections are documented in `docs/authentication.md`; the configured lifetime is eight hours and credentialed CORS is exactly `http://127.0.0.1:5174`.
- Added rollback-isolated authentication integration coverage for credentials, cookies, session validation, rotation, logout, origins/CORS, deactivation, and reusable role checks. Pending frontend integration remains intentionally out of scope.

## Role-based login/signup interface

- Implemented the approved role-card login and signup entry screens without replacing the existing shared-team student registration flow.
- Login uses credentialed cookie requests, supports registered email or creator registration number, restores `/auth/me`, validates the selected role against the database role, and offers logout from a minimal authenticated account view. It does not fabricate dashboards.
- Public staff/evaluator/coordinator signup is deliberately restricted pending invitation/admin workflow. Password recovery is displayed but unavailable because email delivery is not configured.
- Frontend lint and production build passed. The later authentication test-repair checkpoint verified the database migration and full backend suite.

## Auth navigation and password-feedback refinement

- Connected public Sign In, signup role selection, and the shared-team registration steps to the browser History API using navigation identifiers only. Browser and in-form Back/Forward restore the mounted screen and step without storing form values; later registration steps revalidate earlier required fields before rendering.
- Refined password creation guidance to show only missing recommendations while retaining the local strength estimate. Sign In remains free of creation guidance.

## Sign In workspace illustration

- Replaced the abstract Sign In background with a balanced image-led layout: branding and the preserved working form are on the desktop left, while a local WebP photo panel with a navy/teal overlay and scoped entrance motion is on the right. The photo is “Students Studying Together while Looking at the Screen of a Laptop” by Yan Krukau, downloaded from Pexels under the Pexels License: https://www.pexels.com/photo/students-studying-together-while-looking-at-the-screen-of-a-laptop-8199761/ . The panel is hidden on narrow screens so the form stays first and scrollable.
- Responsive browser verification at the specified desktop, tablet, and mobile viewports remains manually pending; lint and production-build success are not treated as visual verification.

## Shared public authentication layout

- Added `AuthLayout` to give Sign In, signup selection, restricted-registration, recovery, confirmation, and all team-registration steps one warm-ivory desktop/tablet/mobile shell. It keeps the original brand and form column aligned with the existing local photo panel, while mobile hides the panel and preserves natural form scrolling.
- Compressed the shared five-role selector into consistent horizontal 64px cards; Administrator spans the final row. Existing role values, icons, selections, navigation, and permissions are unchanged. Browser visual verification of every auth state and requested viewport remains manually pending.

## Glass authentication presentation

- Updated the shared `AuthLayout` from separate photo/form panels to a full-photo background with a navy overlay and frosted, fallback-opaque authentication card. Desktop keeps brand and approved copy left of the card; mobile hides that copy and retains the brand/form order. Selected roles and public authentication actions use `#4663FF`; Admin presentation remains unchanged. Browser visual verification remains manually pending.

## Authentication test repair

- Fixed test-only detached fixture access and Content-Type-aware ASGI response parsing.
- Fixed the logout endpoint to explicitly set its HTTP `204` status when returning FastAPI's injected response object; session revocation and cookie deletion are unchanged.
- Migration `f7a1c3d9e2b4` is applied, `alembic check` passes, the focused authentication suite passed 6/6 tests, and the full backend suite passed 30/30 tests. All suite fixtures remain rollback-isolated.

## M1-A: Admin access and portal shell

- Added `GET /api/v1/admin/me`, protected by the persisted `ADMIN` role, and added rollback-isolated tests proving Students receive `403` while a real Admin session succeeds.
- Added a deliberately interactive `scripts/bootstrap_first_admin.py` helper. It prompts locally with `getpass`, refuses unexpected databases, existing Admin accounts, and conflicting emails; it has not been run and created no account.
- Added the protected administrator shell, actual account/logout controls, and an Administrator login entry. The shell deliberately has no fake management data or inactive management actions.
- Added `docs/p1-feature-tracker.md` and `docs/admin-portal.md`; M1-A remains Partial pending a manually provisioned Admin and browser verification. M1-B through M1-I remain unimplemented.
- Refined the Admin shell into a responsive full-width layout with a 240px desktop sidebar, mobile navigation control, teal/sage active state, and real Academic Cycles overview data fetched from existing APIs. No management actions or synthetic statistics were added.
- Established the finalized Admin portal as the visual baseline for future role portals while preserving role-specific navigation, backend authorization, and honest incomplete states. No additional role portal was created before its real functionality exists.
- Implemented a further Admin visual correction in source: compact shell/header, refined sidebar and cycle list, responsive mobile overlay, and reduced-motion-safe micro-interactions. Visual review remains pending user approval.
- M1-B now provides ADMIN-only paginated account listing, controlled account creation, role/status mutation, active-session revocation, shared-team protection, and concurrent last-active-ADMIN protection. Migration `b8d2e4f6a9c1` adds append-only audit events with PostgreSQL UPDATE/DELETE trigger protection. Six rollback-isolated M1-B tests and the complete 37-test backend suite pass; browser review remains pending. Shared-team deactivation is currently rejected as an implementation safeguard; its intended lifecycle behavior remains an unresolved policy decision.
- M1-C.1 adds ADMIN cycle and policy management with audit targets under `c4e7f1a2b9d3`; no real configuration was changed during isolated tests. Two controlled, bounded tests now use separate database sessions to prove registration precedes a waiting closure and that a waiting policy reduction rejects after seeing the committed team without partial account/team/member/audit writes. Semester and unspecified workflow policies remain separate; browser review remains pending.
