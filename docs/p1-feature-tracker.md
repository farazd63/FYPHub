# P1 proposal coverage matrix

> **M1-D.1 update (2026-10-15):** Internal ADMIN-only SHORT/LONG reference metadata and linked academic-rule versioning is now partially implemented in migration `d5e6f7a8b9c0`, template models/schemas/routes, and `test_template_references.py`. It preserves historical versions and unset rule values; six focused tests and the 46-test backend suite pass. UI and policy-dependent publication/storage/activation work remain pending.

> **M1-D.2 update (2026-10-15):** The ADMIN Proposal Templates UI uses labelled typed controls for the supported rule fields and creates immutable initial, metadata, and rule versions. The list endpoint now provides the stable `reference_id` needed to retrieve complete pre-existing history after reload. Browser verification is pending.

This is the source-of-truth P1 Mid coverage record. It was reconciled against the original proposals, not inferred from navigation or endpoint names.

- **Primary requirement source:** *long proposal.pdf*, section 9.3, PDF pages 9-10.
- **P1 boundary:** *long proposal.pdf*, section 10, PDF page 14: P1 Mid is Modules 1-3; Modules 4-6 are P1 Final.
- **Architecture support:** *short proposal.pdf*, PDF page 2: five roles use shared modules through role-based permissions.
- **Status:** **Verified** has automated evidence cited here; **Implemented** has code but lacks sufficient verification; **Partial** covers only part of the requirement; **Not Started** has no implementation. Browser verification is stated separately.

Repository paths below are concrete implementation references. The full-suite result is in `docs/progress.md`; each item cites its own evidence instead of relying on a count.

## M1 - Admin Dashboard & Academic Management

| ID | Source and requirement | Status | Actual implementation / evidence | Missing work or decision |
| --- | --- | --- | --- | --- |
| M1-01 | Long 9.3 p9: manage Students, Supervisors, Coordinators, Panel Members, and Administrators. | Partial | API: `backend/app/main.py` user list/create/role/status; `models/user.py`; UI `frontend/src/AdminUsersRoles.tsx`; `test_admin_users.py`. | Browser demonstration pending; shared-team deactivation remains an unresolved lifecycle policy. |
| M1-02 | Long 9.3 p9: semester and FYP-cycle configuration. | Partial | `AcademicCycle`; migration `3a1f53f17b1c`; admin API and `AdminCycleManager.tsx`; `test_admin_users.py`. | Semester semantics/configuration are not defined or implemented. |
| M1-03 | Long 9.3 p9: group-size policies. | Verified | `AcademicGroupPolicy`, policy API, registration enforcement in `main.py`; `test_team_registration.py`, `test_cycle_concurrency.py`. | Browser verification pending; only a positive maximum is defined. |
| M1-04 | Long 9.3 p9: workflow policies. | Not Started | No model, API, UI, migration, or tests. | Need approved states, transitions, actors, and exception handling. |
| M1-05 | Long 9.3 p9: official short-proposal template management. | Partial | ADMIN-only internal SHORT reference metadata and immutable metadata/rule versions: migration `d5e6f7a8b9c0`, template routes/models/schemas, `AdminTemplateReferences.tsx`, and `test_template_references.py`. | No official blank template file, publication, upload/download, activation/retirement, or approval workflow. Browser verification pending. |
| M1-06 | Long 9.3 p9: official long-proposal template management with versioned academic rules. | Partial | ADMIN-only internal LONG reference metadata and linked immutable academic-rule versions, with strict optional supported fields, history retrieval, rollback, and concurrency coverage. | No official blank template, approved normative rules, publication/storage, activation/retirement, retention policy, or M3 compliance checking. Browser verification pending. |
| M1-07 | Long 9.3 p9: supervisor capacity configuration. | Partial | ADMIN-only capacity policies have one persisted positive maximum per supervisor/cycle: model/migration `e8f9a0b1c2d3`, routes in `backend/app/main.py`, `AdminSupervisorCapacity.tsx`, and `test_supervisor_capacity.py`. Verified: 4 capacity tests, 50 backend tests, clean Alembic current/head/schema check, frontend lint/build, plus screenshots of creation and edit-form population with separate name/email fields. | Update-save, post-save refresh persistence, and mobile browser verification remain pending. This configures limits only; no supervisor-to-group allocation or filled/remaining calculations are implemented. |
| M1-08 | Long 9.3 p9: panel rubric configuration. | Not Started | No rubric model/API/UI/tests. | M1 configuration is distinct from M9 evaluation; need approved rubric definitions. |
| M1-09 | Long 9.3 p9: scoring-criteria configuration. | Not Started | No criteria model/API/UI/tests. | Need criteria, scales, weights, aggregation, and amendment rules. |
| M1-10 | Long 9.3 p9: academic-deadline configuration. | Not Started | No deadline model/API/UI/tests. | Need official dates, timezone, scope, and change authority. |
| M1-11 | Long 9.3 p9: deadline reminder and escalation rules. | Not Started | No rule model, scheduler, delivery integration, UI, or tests. | Need timing, recipients, channels, escalation authority, and delivery service. |
| M1-12 | Long 9.3 p9: immutable audit history of administrative changes. | Partial | `AdminAuditEvent`; migrations `b8d2e4f6a9c1`, `c4e7f1a2b9d3`; append-only trigger; writers in `main.py`; trigger/atomicity tests in `test_admin_users.py`. | No authorized audit-history reader UI/API. Database owners can alter protections; it is not an external immutable ledger. |

## M2 - Student Team & Collaboration Hub

| ID | Source and requirement | Status | Actual implementation / evidence | Missing work or decision |
| --- | --- | --- | --- | --- |
| M2-01 | Long 9.3 pp9-10: FYP group creation and leader/member rules. | Partial | `Team`/`TeamMember`, migration `ce964120f177`; `POST /api/v1/team-registration`; `App.tsx`; `test_team_registration.py`, `test_team_constraints.py`. | Creator/contact-member recording only; no individual member accounts, leader transfer, membership lifecycle, or verification workflow. |
| M2-02 | Long 9.3 p10: group-size enforcement. | Verified | Cycle policy enforcement and locked registration; `test_team_registration.py`, `test_cycle_concurrency.py`. | Minimum/composition policy is unspecified. |
| M2-03 | Long 9.3 p10: verified membership. | Partial | Persisted names, registration numbers, contact emails, one creator, and uniqueness constraints. | “Verified” proof method is unspecified; contact capture is not acceptance or identity verification. |
| M2-04 | Long 9.3 p10: prevent duplicate membership by Student ID/Registration Number and cycle. | Verified | Partial unique indexes and validation; `test_team_constraints.py`, `test_team_registration.py`. | Must cover future request/invitation and individual-account flows. |
| M2-05 | Long 9.3 p10: 8-10 compatibility questions (skills, domain, availability, work style, preferred role, commitment). | Not Started | No questionnaire/profile model, API, UI, or tests. | Need approved questions, consent, visibility, retention, and ranking/explanation policy. |
| M2-06 | Long 9.3 p10: AI teammate compatibility matching. | Not Started | No matching service, AI integration, UI, or tests. | Depends on M2-05 and approved matching/fairness policy. |
| M2-07 | Long 9.3 p10: join requests. | Not Started | No request model/API/UI/test. | Resolve request attribution under shared login. |
| M2-08 | Long 9.3 p10: invitations and accept/reject workflow. | Not Started | No invitation/acceptance model/API/UI/test. | Decide acceptance proof without silently introducing individual logins. |
| M2-09 | Long 9.3 p10: student-to-group matching. | Not Started | No matching/group-placement API/UI/test. | Depends on profiles, requests/invitations, and duplicate guard. |
| M2-10 | Long 9.3 p10: temporary match chat. | Not Started | No chat model/API/UI/test. | Need retention, moderation, expiry, and attribution rules. |
| M2-11 | Long 9.3 p10: seven channels - General, Proposal, Research, Supervisor Discussion, Tasks & Progress, Files & Resources, Announcements & Deadlines. | Not Started | No channel/message/file/task model/API/UI/test. | Need access, supervisor visibility, notifications, retention, and relation to later modules. |
| M2-12 | Long 9.3 p10: group AI chatbot. | Not Started | No chatbot, retrieval source, guardrails, API/UI/test. | Need model/provider, grounding, privacy, logging, and human-authority policy. |

## M3 - Student Proposal & AI Compliance Check

| ID | Source and requirement | Status | Actual implementation / evidence | Missing work or decision |
| --- | --- | --- | --- | --- |
| M3-01 | Long 9.3 p10: short/long proposal creation. | Not Started | No proposal model, API, UI, migration, or test. | Depends on M1-05/M1-06 templates and submitter rules. |
| M3-02 | Long 9.3 p10: proposal upload. | Not Started | No file storage, validation, API/UI, or test. | Need formats, limits, malware handling, storage/retention, and access policy. |
| M3-03 | Long 9.3 p10: draft, submit, resubmit, and lifecycle-status management. | Not Started | No state machine, authorization, API/UI, or test. | Need approved states/transitions, deadline interaction, and return/review ownership. |
| M3-04 | Long 9.3 p10: version history. | Not Started | No version model/API/UI/test. | Need immutable linkage, retention, and author attribution compatible with shared login. |
| M3-05 | Long 9.3 p10: AI-generated change summaries between versions. | Not Started | No AI service, endpoint, or test. | Depends on M3-04 and approved model/prompt/disclosure/evaluation policy. |
| M3-06 | Long 9.3 p10: format checks for font, size, margins, alignment, spacing, headings, numbering, tables, and figures. | Not Started | No parser/checker/rules model/API/UI/test. | Need official templates and exact normative values; submitted project proposals are not such templates. |
| M3-07 | Long 9.3 p10: structural checks for sections/order, headings, references, appendices, and captions. | Not Started | No rules/checker/API/UI/test. | Need approved structure and accepted document formats. |
| M3-08 | Long 9.3 p10: consistency analysis across problem, objectives, methodology, solution, scope, and outcomes. | Not Started | No analysis service/API/UI/test. | Need rubric/prompt/evaluation, disclosure, data handling, and human-review boundary. |
| M3-09 | Long 9.3 p10: authorized supervisor, coordinator, and panel views of the same analysis. | Not Started | No proposal/compliance authorization data/API/UI/test. | Depends on proposal records and role-specific review policy. |

## Cross-cutting proposal boundaries

- The five roles are **Student, Supervisor, FYP Coordinator, Panel Member, and Administrator** (long proposal section 2, p3; short proposal p2). Shared modules must not be duplicated into five role portals.
- M1 configuration is P1 work. Full supervisor matching/allocation is M5; review is M6; scheduling is M8; panel evaluation is M9. Configuration must not be mislabeled as completing those later modules.
- Current team registration uses one shared team login and contact emails for other members, with no invitations at creation. The proposal still requires discovery, matching, join requests/invitations, temporary chat, and collaboration; their identity and attribution design is unresolved.
- No status here claims screenshots. Browser validation is pending unless a later checkpoint records captured evidence.

Report-ready explanations, workflows, demonstrations, source-dependent blockers, and M1-D scope are in [p1-workflows.md](p1-workflows.md).
