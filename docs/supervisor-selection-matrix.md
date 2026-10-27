# Supervisor Selection and Proposal Request Matrix

Audit checkpoint: **SUPERVISOR-A** (2026-10-27)

The original proposal PDFs referenced by the tracker are not stored in this checkout. This matrix therefore uses the approved workflow request, `docs/p1-feature-tracker.md`, `docs/p1-workflows.md`, and the current source tree. It is a boundary record, not a claim that proposal-submission or review features already exist.

## Requirement matrix

| Requirement | Existing foundation | Status before this checkpoint | Implementation boundary |
| --- | --- | --- | --- |
| Select an active academic cycle | `AcademicCycle`, public cycle read API, registration state | Partial | Reuse existing cycle records; only cycles open for registration are selectable. |
| Discover eligible supervisors | `User` roles and `SupervisorCapacityPolicy`; no student list API | Missing | Add a student-authorized, cycle-scoped safe list with name, stored department/scope when available, capacity, assigned, remaining, and availability. |
| Create a supervisor request from a proposal PDF | Request model/API now exists; no document extraction before this update | Partial | Student uploads exactly one readable one-page PDF; local `pypdf` extraction is the source of truth. Manual title/summary entry is not part of the flow. |
| Save a draft | Request lifecycle and ownership checks | Partial | Upload creates a draft with an immutable document/extraction snapshot; replacement uploads create a new document version. |
| Submit a request | Request lifecycle and locked validation | Partial | Student must confirm extracted required fields before submission; cycle/team ownership, active supervisor, capacity, and duplicate state remain transactional. |
| Persist lifecycle states | No request status model | Missing | Add `DRAFT`, `SUBMITTED`, `CHANGES_REQUESTED`, `ACCEPTED`, `REJECTED`, and `WITHDRAWN`; preserve timestamps and reviewer fields. |
| Persist comments and status history | Existing append-only admin audit, request history | Partial | Upload, extraction, confirmation, submission, review, and status changes write safe audit events atomically; document snapshots are append-only. |
| Supervisor queue and decisions | Existing supervisor role and assignment read patterns; no request queue | Missing | Only the selected active supervisor can review; accept rechecks capacity and active assignment transactionally. |
| Student request list/status/withdraw/resubmit | No request API/UI | Missing | Student can see only own/team requests and permitted comments/history; withdraw only in allowed states; resubmit only after changes requested. |
| Admin monitoring | Existing read-only audit and capacity screens | Missing | Add a read-only request monitor with cycle, supervisor, status, date filters, details, history, capacity, and audit trail. |
| Coordinator monitoring | No request-monitoring endpoint/UI | Missing | Add read-only cycle-scoped monitoring; no supervisor impersonation or decision override. |
| Authorization and isolation | Session roles, team creator/roster records, cycle constraints | Partial | Add explicit role, team ownership, selected-supervisor, cycle, active-account, and stale-state checks. |
| Concurrency and rollback | Existing lock ordering and audit rollback patterns | Partial | Reuse cycle/supervisor locking conventions; add duplicate/capacity race tests and audit rollback tests. |

## Workflow matrix

| Action | Allowed actor | Preconditions | Result |
| --- | --- | --- | --- |
| Upload/extract draft | Student/team owner | Active student session, eligible team/cycle, selected eligible supervisor, PDF-only, configured size limit, exactly one readable page | `DRAFT` with immutable original PDF, extracted text/fields, source-page references, runtime, and `EXTRACTED` status. |
| Confirm extraction | Student/team owner | Required extracted fields are detected and the student reviews the preview | `CONFIRMED`; no manual retyping and no assignment is created. |
| Submit | Student/team owner | Confirmed extraction, no active duplicate, supervisor capacity available | `SUBMITTED`; submitted timestamp and history/audit record. |
| Withdraw | Student/team owner | Request is `DRAFT` or `SUBMITTED` (not decided) | `WITHDRAWN`; history/audit record. |
| Resubmit | Student/team owner | Current status is `CHANGES_REQUESTED`, fields valid, capacity still available | `SUBMITTED`; new submitted timestamp and history/audit record. |
| Accept | Selected supervisor only | `SUBMITTED`, active supervisor, capacity and active assignment rechecked under lock | `ACCEPTED`; assignment created atomically with history/audit. |
| Reject | Selected supervisor only | `SUBMITTED`, required comment | `REJECTED`; history/comment/audit atomically. |
| Request changes | Selected supervisor only | `SUBMITTED`, required comment | `CHANGES_REQUESTED`; history/comment/audit atomically. |
| Monitor | Admin or authorized coordinator | Authenticated role and permitted cycle scope | Read-only request data; no decision mutation. |

## Current source map

- Cycle and capacity models: `backend/app/models/academic.py`
- Existing assignment model/routes: `backend/app/models/supervisor_assignment.py`, `backend/app/supervisor_assignments.py`
- Session and role authorization: `backend/app/auth.py`, `backend/app/main.py`
- Existing Admin capacity UI: `frontend/src/AdminSupervisorCapacity.tsx`
- Student shell: `frontend/src/portals/student/`
- Existing audit infrastructure: `backend/app/models/audit_event.py`, `add_admin_audit_event` in `backend/app/main.py`
- PDF extraction/storage: `backend/app/pdf_extraction.py`, `SupervisorRequestDocument`, `d6e7f8a9b0c1_add_supervisor_request_documents.py`

## SUPERVISOR-H source map

- Decision/monitor routes and lifecycle enforcement: `backend/app/supervisor_requests.py` (`/decision`, `/supervisor/queue`, `/admin/monitor`, `/coordinator/monitor`).
- Archived reference metadata and separate PDFs: `backend/app/models/proposal_reference.py`, `backend/app/proposal_reference.py`, `scripts/seed_proposal_references.py`.
- Request conversation authorization and append-only messages: `backend/app/models/supervisor_request_conversation.py`, `backend/app/supervisor_request_conversations.py`.
- Student reference/conversation UI: `frontend/src/portals/student/modules/supervisor-selection/ProposalReferenceSearch.tsx`, `RequestConversation.tsx`; role-folder re-exports are under the Supervisor, Admin, and Coordinator supervisor-request modules.
- Migration and verification: `backend/alembic/versions/e7f8a9b0c1d2_add_proposal_references_and_request_conversations.py`, `backend/tests/test_proposal_reference_and_conversation.py`, `frontend/tests/supervisor-request-workflow.test.mjs`.
