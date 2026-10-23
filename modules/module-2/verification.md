# Verification

Audit on 23 October 2026, from the current working tree. The Long Proposal section 9.3 on pages 9?10 was extracted directly from `D:/FYP Project/long proposal.pdf`.

| Directory | Command | Result |
| --- | --- | --- |
| `backend` | `.\.venv\Scripts\python.exe -m unittest discover -s tests` | 149 passed after updating invitation tests for the existing transactional outbox. The initial run had two failures: an obsolete SMTP rollback expectation and a concurrency fixture missing an SMTP-accepted outbox record. |
| `frontend` | `npm run lint` | Passed. |
| `frontend` | `npm run build` | Passed. |
| `frontend` | `node --test tests/*.test.mjs` | 2 passed. |
| root | `git diff --check` | Passed with existing line-ending warnings; Git does not include untracked files in this check. |

The backend tests use mocked email; they do not verify actual SMTP delivery. Browser/mobile flows and a live local AI model were not tested. No migration operation was performed. The concurrency fixture asserts the database is `fyphub_p1` before its isolated test data is created and removed. Historical results in project records are not new verification.

## Student-to-group matching review

Current-tree review: `python -m unittest tests.test_team_matching tests.test_anonymous_verification tests.test_join_requests tests.test_invitations` passed 35 tests; frontend `npm run lint` and `npm run build` passed. These verify existing flows, not individual student-to-group matching. Live SMTP, AI, and browser/mobile checks were not performed. No migration was run.

## Student-to-group implementation

The user approved reusing existing team opt-in and deterministic comparison for roster-verified individual discovery, returning team IDs and category results. The full backend suite passed 158 tests; the subsequent focused `python -m unittest tests.test_student_matching` passed 13 tests after adding cross-cycle and expiry checks (the count includes imported/inherited tests). Frontend lint, production build and two match-chat tests passed. Database `fyphub_p1` was confirmed before applying additive migration `b2c3d4e5f6a7`; Alembic current is head and `alembic check` found no schema drift. SMTP is mocked; live SMTP, live AI and browser/mobile checks were not performed.

## Current checkpoint verification

Current working tree, 23 October 2026: focused `python -m unittest tests.test_student_matching tests.test_anonymous_verification tests.test_team_matching tests.test_join_requests tests.test_invitations` passed 48 tests. Full `python -m unittest discover -s tests` passed 162 tests. Frontend `npm run lint` and `npm run build` passed. Root `git diff --check` passed with existing line-ending warnings; it excludes untracked files. The browser inventory was empty and the in-app browser was unavailable, so desktop and mobile discovery remain unverified. SMTP host and sender, and local AI URL and model, were not configured in the current process environment; no live delivery or live AI request was performed. No migration was run.

### Manual functional browser verification (pending)

Use an isolated test environment with an approved test roster student, an opted-in same-cycle test team with known answers, a team in a different cycle, and a test SMTP service delivering to a mailbox you control. Configure SMTP privately in the backend environment; do not put secrets in this document. Start the backend from the repository root with `& '.\backend\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010`, and start the frontend from `frontend` with `npm run dev -- --host 127.0.0.1 --port 5174`. Open `http://127.0.0.1:5174` on a desktop browser. Expand **Find a group**, enter the test student's cycle ID, registration number, roster email and eight answers, request the code, retrieve it from the controlled mailbox, and select **Verify and find groups**. Check that only opted-in teams from the same cycle appear, that displayed category outcomes agree with the test answers, and that no team answer text or student contact data appears in results. Repeat with an opted-out team, mismatched roster identity, and an expired or reused code; verify no unauthorized result is returned. Repeat the same flow using the browser's mobile device emulation and check that controls and results remain usable without horizontal clipping. Record actual browser, viewport and outcomes when performed. Do not use real student data.

## Discovery verification follow-up

On 23 October 2026, `python -m unittest tests.test_student_matching tests.test_anonymous_verification tests.test_team_matching` passed 19 tests. Tests use mocked OTP delivery and cover roster verification, two-category comparison, opt-out and cross-cycle filtering, result shape, missing/expired/replayed proof and wrong-cycle rejection. They do not establish the full eight-answer browser flow. The browser inventory was empty and the in-app browser was unavailable; SMTP host and sender were not configured. No live SMTP delivery, desktop or mobile browser verification was performed. The manual steps above remain pending; include all eight answers and verify the expired or replayed proof and wrong-cycle rejection. No OTPs, real emails or secrets were recorded.

## User-performed visual check

The user reports that the student-to-group discovery flow looked good in both desktop and mobile views. This is a user-performed visual check; browser details and viewport sizes were not supplied. The report does not establish live SMTP or AI operation, nor specify outcomes for every functional or negative-path check listed above.
