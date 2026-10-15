# Project Progress

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
- Sign In remains disabled; no session or automatic login is created.
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
