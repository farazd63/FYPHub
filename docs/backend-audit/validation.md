# Backend orphan audit validation

Baseline: `59215f6f630420a6f962c40d6930d4c5700b5dc3`, inspected on 2026-11-11.

## Results

| Check | Result | Evidence |
|---|---|---|
| Frontend production build: `npm run build` | PASS, exit 0; existing large-chunk warning | [Build log](frontend-build.log) |
| Frontend TypeScript: `npx tsc -b --pretty false` | PASS, exit 0 | [Typecheck log](frontend-typecheck.log); successful command produces no output |
| Frontend lint: `npm run lint` | PASS, exit 0; 0 errors, 14 warnings | [Lint log](frontend-lint.log) |
| Full backend suite | FAIL: 183 passed, 48 failed, 33 skipped; 63 subtests passed | [Full failures and tracebacks](backend-tests.log) |
| Live API health | GET `http://localhost:8010/health`: 200 | Checked against running backend |
| Live database readiness | GET `http://localhost:8010/health/ready`: 200 | Checked against running backend |
| Live API definition | GET `http://localhost:8010/openapi.json`: 200 | Runtime route snapshots |
| Served frontend | GET `http://localhost:5173/`: 200 | Checked against running frontend |
| Frontend authentication proxy | GET `http://localhost:5173/api/v1/auth/me` without a session: 401 | Expected protected response |
| Unauthenticated GET sweep | 134 routes: 9 returned 200, 124 returned 401, 1 returned 422; no 5xx/network errors | [Per-route results](anonymous-get-smoke.json) |
| API and database structure comparison | PASS: unchanged | [Comparison](contract-comparison.json), [before](before-contract.json), [after](after-contract.json) |
| Application source changes | None | Only audit documents and the read-only audit script were added |

The comparison sorts only unordered SQLAlchemy constraint and foreign-key lists. Raw ordering differs between independent Python processes; route definitions, schemas, dependencies, tables, columns and migration metadata match after that normalization.

The GET sweep substitutes `1` for path parameters and supplies no session or query parameters. Its sole 422 response was `/api/v1/auth/dev/password-reset-link` without the required query input. A 401 confirms an authentication gate responds; it does not verify the authenticated operation. Only GET operations were exercised, with no request bodies or deletion/upload actions.

## Backend test isolation and reproduction

The test database was a separate temporary container, `fyphub-audit-test-db`, using the same PostgreSQL/pgvector image as the application. Its database name was `fyphub_p1` because existing tests check that name. The hostname and storage were isolated. Only `pg_dump --schema-only --no-owner --no-privileges` was restored; no production records, credentials, uploads or sessions were copied. This intentionally does not reproduce production seed data.

A separate disposable runner used the existing backend image and mounted the backend source read-only at `/audit`. It connected exclusively to the test database, with document storage under `/tmp` and Ollama pointing to an unused loopback port. No production AI service or email credentials were supplied. Pytest 9.2.0 was installed only in this disposable runner; project dependencies were not changed. Container pip initially encountered a certificate error, so wheels were downloaded with the host's verified pip connection and installed offline in the runner.

The successful collection command was:

```text
PYTHONPATH=/audit:/audit/tests python -m pytest -p no:cacheprovider tests --tb=short -q
```

Both import roots are necessary because an existing test imports `test_archive_import` as a top-level module. The first collection attempt without `/audit/tests` failed; the final full-suite log replaces that unsuccessful attempt. No test source was edited.

The full suite exited 1 after 21.83 seconds. These are baseline results with zero cleanup changes, not evidence of cleanup regressions. They also do not establish that all failures occur in a populated deployment: missing seed data and the isolated environment affect some tests. Examples include a Fall 2027 fixture not present in the empty database, assertions expecting student authorization 403 that receive authentication 401, and old authentication/registration/request assertions. The full log records the exact failures; no unrelated authentication, feature or test fixes were made during this audit.

Both temporary containers and their anonymous test volumes were removed after testing. Production containers and database volumes were retained.

## Coverage and limits

The audit maps all 93 frontend source modules, their imports and 206 API request/reference sites, including role-based portal dispatch and inactive source files. It traces 268 runtime backend route registrations to dependency guards, services, schemas, model tables and query source locations. Dynamic URLs and helper calls are conservatively represented; the dependency map is static evidence, not proof that every branch executed. A source query location is not a captured database execution trace.

The frontend build/typecheck cover current page imports. Live health, readiness, frontend serving, API schema and authentication proxy were checked. An additional unauthenticated GET-route sweep is recorded separately. These checks do **not** certify every authenticated dashboard interaction, file upload, download, administrative mutation or external AI operation end to end. Full authenticated browser acceptance was not performed. The backend failures and skipped tests prevent an all-features-pass claim.

No backend Python lint/type-check command is configured in this repository; none was invented. The repository's configured TypeScript check and ESLint command were run as requested.

## Cleanup decision

Confirmed orphan files: **0**. Quarantined files: **0**. Permanently removed files: **0**.

All 80 backend application Python files are either reachable from the application (79 files, including implicit package initialization), or protected by current tests/shared-utility use (`team_compatibility.py`). Active registered APIs remain protected even where a current frontend caller was not found. Backups and stored uploads are data, not orphan code.

There is no reason to create an empty quarantine directory. No removal is justified, and the failing backend suite would independently block permanent deletion under the requested rules. Frontend behavior, API contracts, database schema, working code, migrations and configuration remain unchanged.
