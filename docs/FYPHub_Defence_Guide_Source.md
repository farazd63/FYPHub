# FYPHub — Complete Technical Defence Guide

Prepared for project defence and viva preparation. Inspection date: 11 November 2026, Asia/Karachi. Repository: FYPHub, workspace F:/p1/fyphub-p1.

This guide explains the implementation actually found in the repository and running PostgreSQL catalog. It distinguishes visible workflows, supporting APIs, alternative source files, and historical database objects. Do not present a file's existence as proof that its feature is exposed in the current portal. The generated appendices provide exact tables, columns, foreign keys, registered endpoints, source-file locations, migration revisions, and test names.

Use the PDF to study and print; use the Word document to add your own speaking notes; use the Markdown version to search exact filenames. The companion technical-inventory.json supports detailed lookups. No account records, passwords, session tokens, private environment values, or uploaded student documents are included.

# Reading map

| Part | What you will learn |
|---|---|
| Chapters 1–3 | Defence introduction, architecture, technologies and repository navigation |
| Chapters 4–5 | Feature-to-file-to-table map and database relationships |
| Chapters 6–9 | Authentication, academic configuration, supervision and real document uploads |
| Chapters 10–13 | Proposal checks/AI, Excel archives/search, progress and evaluation algorithms |
| Chapters 14–17 | Storage/deployment, security, tests and known gaps |
| Chapters 18–20 | Demonstration sequence, read-only SQL, viva questions and revision checklist |
| Appendix A | Inspection scope, counts, migration state and schema differences |
| Appendix B | All installed database tables, columns, constraints, indexes and foreign keys |
| Appendix C | Registered APIs with exact backend handler locations and contract references |
| Appendix D | Every inspected source file, symbols, frontend imports and schema fields |
| Appendix E | Alembic migration revision/parent graph |
| Appendix F | Rebuilding the evidence and generated documents |

# 1. How to study and explain the project

## 1.1 A two-minute introduction

FYPHub is a group-based final-year-project management application. Administrators configure academic cycles, group policies, user access, supervisor capacity, templates and document requirements. Students register a shared group account, submit proposals and required documents, request a supervisor, track project work and search previous projects. Supervisors review requests and inspect their assigned groups. Coordinator and evaluator interfaces expose selected review and evaluation workflows. The backend enforces roles, ownership and workflow state; PostgreSQL stores the academic records and the application stores uploaded files through feature-specific storage mechanisms.

The application is a modular monolith: one React browser application talks to one FastAPI application containing multiple feature routers. PostgreSQL is the common relational database. Docker Compose runs the application, database and local AI service in separate containers. Separate containers do not make each academic feature an independently deployed microservice.

## 1.2 Your universal answer pattern

For every feature, explain five things in this order:

1. Who uses it, and what academic problem it solves.
2. Which React screen collects input or displays results.
3. Which API endpoint handles the request and which backend function owns it.
4. Which table stores the parent record, which tables store versions/history, and which foreign keys connect them.
5. Which authorization, validation, transaction and test checks protect the workflow.

Example: for document submission, name StudentRequiredDocumentsDashboard.tsx, POST /api/v1/student/group/requirements/{id}/upload, document_requirements.upload, document_submissions plus document_submission_versions, the document storage volume, and ownership/deadline/type/size/signature checks.

## 1.3 Suggested preparation order

- First session: architecture, technology stack, role routing, authentication and database relationships.
- Second session: registration, supervisor selection, assignment/capacity, document uploads and discussions.
- Third session: archive import, proposal extraction/compliance, progress and evaluation algorithms.
- Fourth session: deployment, migrations, limitations, demonstration rehearsal and viva questions.
- During rehearsal, navigate to the exact source symbol listed in the appendices instead of memorizing every line.

# 2. Architecture and technology choices

## 2.1 Request flow

```text
Browser: React + TypeScript
    |
    | HTTP fetch, JSON or multipart file, session cookie
    v
Nginx on localhost:5173
    |-- static HTML/CSS/JavaScript from /usr/share/nginx/html
    |-- /api/* and /health/* reverse proxy
    v
FastAPI / Uvicorn, backend:8000 (host localhost:8010)
    |-- Pydantic request validation
    |-- cookie authentication and role/ownership checks
    |-- feature router and workflow functions
    |-- SQLAlchemy request-scoped Session
    v
PostgreSQL 17 + pgvector (db:5432; host localhost:55732)
    |-- relational academic records, JSONB metadata, histories
    |-- some feature document bytes in BYTEA

FastAPI also accesses:
    |-- uploaded-files volume via DOCUMENT_STORAGE_ROOT
    |-- Ollama HTTP service for supported advisory AI workflows
    |-- optional configured Groq provider and SMTP delivery
```

## 2.2 Actual stack and its responsibilities

| Layer | Technology | Why it is used here | Authoritative file |
|---|---|---|---|
| User interface | React 19, React DOM | Components, state, effects and role-specific screens | frontend/src/main.tsx, App.tsx |
| Type checking | TypeScript 6 | Compile-time data contracts and component properties | frontend/tsconfig*.json |
| Frontend toolchain | Vite 8 | Local development, proxy and production asset build | frontend/vite.config.ts |
| Styling | Tailwind CSS 4 plus CSS files | Utility styles, layouts, shared theme and feature-specific presentation | frontend/src/index.css, design-system.css |
| API | FastAPI | HTTP routing, dependencies, input validation and OpenAPI documentation | backend/app/main.py |
| Application server | Uvicorn | Runs app.main:app | backend/Dockerfile |
| Validation | Pydantic / EmailStr | Request schemas, enums, field restrictions and validation | backend/app/schemas/ |
| ORM | SQLAlchemy 2.1 | Explicit SQL queries, transactions and model definitions | backend/app/database.py, models/ |
| Database driver | psycopg 3 | PostgreSQL communication | backend/requirements.txt |
| Persistent database | PostgreSQL 17 | Constraints, transactional records, JSONB and foreign keys | docker-compose.yml |
| Vector extension | pgvector 0.8.6 | Installed database extension; availability is part of readiness | database/init/001_extensions.sql |
| Schema evolution | Alembic | Ordered migration files and installed revision tracking | backend/alembic/ |
| Password hashing | Argon2id | Salted, computationally expensive password verification | backend/app/security.py |
| Excel reading | openpyxl, xlrd | XLSX and legacy XLS import | backend/app/archived_projects.py |
| Documents | pypdf, PyMuPDF, python-docx | Text/format extraction and document handling | backend/app/pdf_extraction.py |
| Report generation | ReportLab | PDF report output | backend/app/evaluations.py, proposal compliance router |
| Advisory AI | Ollama; configurable Groq | Schema-validated feedback/planning with explicit fallback | backend/app/ai_provider.py |
| Deployment | Docker Compose and Nginx | Container startup, networking, persistent volumes and serving | docker-compose.yml, frontend/nginx.conf |

Package versions above are taken from this checkout. They are not recommendations about current public package releases. Consult backend/requirements.txt and frontend/package-lock.json when reproducing the build.

## 2.3 Why PostgreSQL instead of a database per feature

All main academic features share one PostgreSQL database, normally named fyphub_p1. A feature's database is its related tables within this database. There is not one physical database file for each React screen. Tables connect through identifiers such as team_id, academic_cycle_id, supervisor_id, requirement_id and submission_id. This permits integrity checks and atomic updates spanning a request, assignment and audit event.

PostgreSQL manages the physical files inside its Docker data directory. Python model files describe the intended database structure; they do not contain live student data. Alembic migrations change the structure. The SQL backup file at repository root is a historical export, not the live database and not necessarily current.

# 3. Repository map and application entry points

| Location | What to look for | How to explain it |
|---|---|---|
| frontend/src/main.tsx | React root and global CSS imports | Browser application entry point |
| frontend/src/App.tsx | Auth pages, signup steps, login, session restoration and portal selection | Top-level application controller |
| frontend/src/AdminPortal.tsx | Active administrator feature navigation | Which admin screens are actually mounted |
| frontend/src/portals/student/StudentPortal.tsx | Student feature selection and shared group identity | Student workspace shell |
| frontend/src/portals/supervisor/SupervisorPortal.tsx | Requests, assignments, capacity and history | Supervisor workspace shell |
| frontend/src/portals/coordinator/CoordinatorPortal.tsx | Request monitoring and proposal reviewer workspace | Current coordinator screen composition |
| frontend/src/portals/student/modules/StudentEvaluatorPortal.tsx | Active evaluator entry imported by App.tsx | Evaluator role routing |
| frontend/src/portals/shared/ | Sidebar and shared portal pieces | Reusable presentation and navigation |
| backend/app/main.py | FastAPI app, middleware, auth, admin configuration and router inclusion | Backend application entry and substantial governance logic |
| backend/app/models/ | SQLAlchemy table definitions | Where to find each table and relationship |
| backend/app/schemas/ | Request/response contracts | Validation and accepted payload shape |
| backend/app/*.py | Feature routers and helpers | Business logic and security checks |
| backend/app/modules/module_03_proposal/ | Compliance rules, template extraction, reports | Proposal checking implementation |
| backend/alembic/versions/ | Revision graph and DDL changes | History of schema changes |
| database/init/001_extensions.sql | CREATE EXTENSION vector | Initial extension setup, not all feature tables |
| scripts/ | Bootstrap and seed tools | Initial admin and demonstration data setup |
| backend/tests/, frontend/tests/ | Verification source | Evidence of covered scenarios; test existence is not a fresh passing result |
| docs/ | Prior feature documentation and this guide | Useful context; code and live schema take priority when they differ |
| sample-data/, outputs/, tmp/ | Local examples, exports and temporary artifacts | Not application entry points or authoritative databases |

## 3.1 Important naming distinctions

- UI words group and team generally refer to the same teams table. A request may call its identifier group_id while an ORM field is team_id.
- PANEL_MEMBER is the stored role value for evaluator users. Evaluator is a UI label.
- Proposal is not one universal table in this application. Supervisor-request proposal data, proposal compliance submissions, proposal references, archived projects, and foundation proposals/proposal_versions are separate workflows.
- Project information in the supervisor workspace is assembled from the proposal request, group assignment and recorded progress. There is no general projects table in the current ORM. Do not invent a projects.project_id relationship during the defence.
- Files with names Complete, Final, Clean, AllFormats or V2 are not automatically the active version. Imports decide what is rendered.

## 3.2 Frontend routing and state

The application uses React useState/useEffect and manual browser history handling. It does not declare React Router as a dependency. App.tsx restores a session through /api/v1/auth/me and selects a portal from the persisted role. AdminPortal.tsx recognizes certain /admin/... paths. SupervisorAssignedTeams.tsx supports /supervisor/groups/{group_id}. Some screens remain state-driven and do not have complete bookmark/back-button behavior.

The same-origin API base and Nginx/Vite proxies allow the browser to call /api rather than a hardcoded backend container hostname. Fetch requests generally use credentials: include for cookie authentication. Mutations submit JSON or multipart FormData. Responses update local component state; selected supervisor views poll every ten seconds, while group discussions poll every five seconds. This is polling, not WebSocket push.

# 4. Feature-to-file and database map

| Feature | Active frontend or UI owner | Backend implementation | Main tables / storage |
|---|---|---|---|
| Sign in / sign out / session restoration | App.tsx | main.py, auth.py, security.py | users, auth_sessions |
| Shared group signup | App.tsx member and credentials steps | main.py register_student_group / register_team; schemas/team_registration.py | users, teams, team_members, academic_cycles, academic_group_policies |
| Password recovery | App.tsx recovery views | password_reset.py | password_reset_tokens, auth_sessions, users, admin_audit_events |
| Users, roles and account activation | AdminUsersRoles.tsx | main.py admin user handlers | users, auth_sessions, admin_audit_events |
| Student group administration | AdminStudentGroups.tsx | main.py student_group_detail and admin group endpoints | teams, team_members, users, supervisor_assignments, supervisor_requests |
| Academic cycles and group policy | AdminCycleManager.tsx, AcademicCycleDashboard.tsx | main.py, academic_cycle_overview.py | academic_cycles, academic_group_policies |
| Supervisor capacity | AdminSupervisorCapacity.tsx, SupervisorCapacity.tsx | main.py, coordinator_operations.py, supervisor_requests.py | supervisor_capacity_policies, supervisor_assignments |
| Document requirements and submission list | AdminDocumentRequirementManagerClean.tsx | document_requirements.py | document_upload_requirements, document_submissions, document_submission_versions; file volume |
| Student required-document upload/history | StudentRequiredDocumentsDashboard.tsx | document_requirements.py | Same requirement/submission/version tables |
| Proposal template administration | modules/module-3/AdminProposalTemplates.tsx | modules/module_03_proposal/router.py, template_extractor.py | template_references, template_reference_versions, academic_rule_versions; file volume |
| Student proposal compliance | modules/module-3/ProposalComplianceWorkspace.tsx | modules/module_03_proposal/router.py, compliance_engine.py, pdf_extraction.py | proposal_compliance_submissions, proposal_compliance_reports |
| Supervisor selection and request | StudentSupervisorSelection.tsx re-export / StudentSupervisorSelectionPdf.tsx | supervisor_requests.py, pdf_extraction.py | supervisor_requests, supervisor_request_documents, status history, submission-note versions |
| Supervisor request review | SupervisorRequestsPdf.tsx, SupervisorGroupDetails.tsx | supervisor_workspace.py, supervisor_requests.py | Requests joined with group, assignment, progress and document records |
| Assigned group details | SupervisorAssignedTeams.tsx, SupervisorGroupDetails.tsx | supervisor_workspace.py | No new snapshot table; joins existing feature tables |
| Request conversations | RequestConversation.tsx (shared re-exports) | supervisor_request_conversations.py | supervisor_request_messages |
| Assignment-scoped group discussion | SupervisorGroupDetails.tsx, shared/CollaborationChannels.tsx where mounted | collaboration_channels.py | collaboration_channels, collaboration_participants, collaboration_messages |
| Earlier group channels / moderation | group-channel clients and module helpers | group_channels.py, module2_collaboration.py | group_messages, module2_channel_reads, module2_notifications |
| Project progress and meetings | StudentProgressDashboard.tsx, supervisor project tab | project_workflow.py, supervisor_workspace.py | project_milestones, project_tasks, supervision_meetings |
| Historic Excel project import | OldProjectArchiveImport.tsx, AdminArchiveProjects.tsx | archived_projects.py | archive_import_batches, archived_projects JSONB source data |
| Archive search and project detail | student/modules/knowledge-search/KnowledgeSearch.tsx and detail | archived_projects.py | archived_projects, archived_project_documents |
| Proposal reference search | ProposalReferenceSearch variants if mounted | proposal_reference.py | proposal_references, proposal_reference_documents |
| Academic deadlines | AdminDeadlines.tsx when mounted; dashboard deadline components | main.py deadline handlers, module2_collaboration.py | academic_deadlines, academic_deadline_versions |
| Reminder configuration | AdminReminderRules.tsx when mounted | main.py reminder handlers | reminder_rules, reminder_rule_versions |
| Dashboard requirements | components/DashboardDeadlinesRequirements.tsx where mounted | dashboard_requirements.py | dashboard_requirements |
| Defense schedules and panel scoring | EvaluatorWorkflow.tsx, PanelScheduling.tsx if mounted | project_workflow.py | defense_schedules, defense_panel_members, panel_evaluations, panel_evaluation_scores |
| Formal marks and publication | EvaluationMarksWorkspace.tsx where mounted; API | evaluations.py, schemas/evaluations.py | evaluation_records, evaluation_audit_events, evaluation_corrections, evaluation_aggregation_configs |
| Audit history | API / governance screens | audit_history.py, main.py add_admin_audit_event | admin_audit_events; separate evaluation audit table |
| Group AI helper | Supporting backend/UI if mounted | group_ai.py | module2_chatbot_sessions |
| Advisory proposal AI review | Supporting API; not current supervisor compliance screen | ai_provider.py, supervisor_requests.py | proposal_ai_review_runs |
| Agentic supervision foundation | Supervisor navigation removed; backend still registered | agent_supervision.py | supervision_agent_runs, then milestones/tasks only after permitted execution |

# 5. Database design in depth

## 5.1 Central identity and ownership graph

```text
users (shared student login or staff account)
  |-- auth_sessions.user_id
  |-- password_reset_tokens.user_id
  |-- teams.shared_user_id  [one shared login per group]
  |       |-- team_members.team_id
  |       |-- supervisor_requests.team_id
  |       |-- supervisor_assignments.team_id
  |       |-- project_milestones.team_id
  |       |-- project_tasks.team_id
  |       |-- supervision_meetings.team_id
  |       |-- document_submissions.group_id
  |       |-- proposal_compliance_submissions.team_id
  |       |-- defense_schedules.team_id
  |
academic_cycles
  |-- academic_group_policies.academic_cycle_id
  |-- teams.academic_cycle_id
  |-- document_upload_requirements.academic_cycle_id
  |-- supervisor_requests.academic_cycle_id
  |-- supervisor_assignments.academic_cycle_id

supervisor_requests
  |-- supervisor_request_documents.request_id
  |-- supervisor_request_status_history.request_id
  |-- supervisor_request_messages.request_id
  |-- supervisor_request_submission_note_versions.request_id
  |-- assignment_id -> supervisor_assignments.id

supervisor_assignments
  |-- collaboration_channels.assignment_id
          |-- collaboration_participants.channel_id
          |-- collaboration_messages.channel_id

document_upload_requirements
  |-- document_submissions.requirement_id
          |-- document_submission_versions.submission_id
```

## 5.2 Normalization, JSONB and version tables

Relational parent tables provide stable identities and foreign keys. Version tables retain historical content or configuration without silently overwriting the parent identity. For example, a document requirement has a submission parent for a group and multiple document_submission_versions. Template references and rubric definitions likewise have version tables.

JSONB is used for variable data such as imported Excel columns/cells, member arrays in archived records, AI payloads and compliance report structures. This is practical because historical workbooks do not all share one fixed set of columns. Stable fields such as title, year, session and source batch are still stored as explicit columns for search and indexing.

Tradeoff: JSONB permits flexibility but weakens column-level constraints on individual embedded values. The application must validate payload structure and preserve provenance. Editing a JSONB object requires assigning/merging the new value in a way SQLAlchemy detects; do not assume an arbitrary in-place nested mutation is automatically persisted.

## 5.3 Important integrity controls

- users has normalized email/registration checks and uniqueness. Student-role records require a registration value at the database level even though login uses the shared group email.
- teams links to an academic cycle and a shared user. Team status is constrained to forming, complete, locked or dissolved.
- team_members has a composite group/cycle relationship, active-cycle uniqueness checks for registration/email, and a partial uniqueness rule for the creator/leader.
- supervisor_assignments has a partial unique index allowing only one active assignment for a team where ended_at is null.
- supervisor_requests constrains allowed statuses, positive revision numbers, and active request uniqueness. assignment_id provides a reverse link to the created assignment.
- document_submission_versions has a unique submission/version pair. The submission parent is also constrained by requirement/student; group-level selection is additionally performed in code.
- project tasks and milestones constrain completion percentages to 0–100.
- archived_projects has active normalized title/year/group uniqueness; archive_import_batches stores import provenance.
- Many foreign keys use RESTRICT to preserve academic records. Selected child histories or infrastructure use CASCADE/SET NULL. Read each exact delete policy in the generated database appendix.

## 5.4 Model, migration, installed schema and backup are different

| Artifact | Purpose | Where it exists |
|---|---|---|
| Model | Intended ORM mapping, fields and constraints | backend/app/models/*.py |
| Pydantic schema | Accepted/returned API data; not a database table | backend/app/schemas/*.py |
| Migration | A specific schema transition and dependency on earlier revisions | backend/alembic/versions/*.py |
| Live table | Actual installed records and schema | PostgreSQL named volume |
| alembic_version | Installed migration revision tracking | Table inside the same PostgreSQL database |
| SQL dump | Point-in-time backup/export | Root *.sql export or a chosen backup location |
| Uploaded file | Original bytes for relevant features | File volume, or BYTEA for some document tables |

# 6. Authentication, authorization and group signup

## 6.1 Authentication sequence

1. App.tsx submits an email and password to POST /api/v1/auth/login.
2. main.login calls validate_mutating_origin and finds the user by normalized email. Registration-number login is deliberately not accepted by this handler.
3. security.verify_password verifies the Argon2id hash. A dummy hash is used for unknown users to avoid an obviously different hashing path.
4. The account must be active. Student users must have an active shared-group link.
5. A random opaque token is generated. Only its SHA-256 hash is stored in auth_sessions; the browser receives the raw token through an HttpOnly cookie named fyphub_session.
6. Subsequent requests include the cookie. auth.get_current_user joins auth_sessions to users, checks revocation/expiration/activity and verifies the student group link.
7. require_roles checks the stored role. Feature handlers then check ownership of the requested group, document, request or evaluation.
8. GET /api/v1/auth/me supplies safe account and group context, allowing the browser to restore the appropriate portal.

This is server-side session authentication, not JWT authentication. The server can revoke sessions through the database. Passwords are not encrypted and later decrypted; Argon2id is a one-way hash. SHA-256 is appropriate here for high-entropy random tokens, while human passwords need the slower Argon2 password hash.

## 6.2 Cookie, CORS and origin checks

The cookie is HttpOnly, SameSite=Lax, path=/ and Secure when the backend request scheme is HTTPS. The default session lifetime is eight hours. Authentication helpers explicitly permit the local browser origins http://localhost:5173 and http://127.0.0.1:5173. Cross-origin credentials do not use a wildcard origin.

Nginx forwards /api calls to the backend. This avoids many cookie/CORS problems for the local frontend. However, validate_mutating_origin still checks a supplied Origin against a fixed local allowlist. A new LAN hostname or production domain needs appropriate configuration/code review; the same-origin proxy alone does not guarantee that every new Origin is allowed. Trusting forwarded HTTPS headers must also match the reverse-proxy deployment.

Do not describe the current origin check as a complete standalone CSRF-token mechanism. It is an explicit origin policy used with SameSite cookies. Public routes, no-Origin callers and endpoint-specific permission checks have distinct behavior.

## 6.3 Signup and members

The signup form has academic-cycle selection, group members, and shared credentials steps. Each member now supplies full_name, email and registration_number. StudentGroupMemberInput requires a full text name and uses validate_full_name. The backend normalizes emails and registration identifiers and rejects invalid input. The first member or explicitly designated leader becomes the group creator.

register_student_group translates the public group payload into the established register_team transaction. register_team validates registration mode, cycle/policy availability, group limits and duplicate accounts/members. It creates the shared User, Team and TeamMember records, refreshes group status and writes an audit event. A failure rolls back the transaction.

The group members shown in the student overview come from /auth/me member context and GroupMembers.tsx. Changing the signup form does not recover human names that were never stored for older accounts. Staff account creation and role changes belong to administrative APIs, not a public role dropdown.

## 6.4 Password recovery

password_reset.py creates a hashed, expiring reset token, with a fifteen-minute token lifetime and an in-memory limit of five requests per hour per IP. Production responses generally avoid revealing whether an account exists. Development/demo branches can differ; local development reset links are specifically guarded. SMTP delivery uses STARTTLS when configured. A successful reset consumes the token, updates the Argon2id hash and revokes existing sessions.

Limitations to acknowledge: the rate limiter and development-link cache are process memory, so they are not shared between multiple workers and reset after restart. SMTP success is an external dependency. A generic success message is not proof that an email was delivered.

# 7. Academic administration and governance

## 7.1 Academic cycles and group policies

academic_cycles stores code, display name, academic year, session and registration state. academic_group_policies stores minimum/maximum group size, formation deadline and matching configuration. The cycle/policy APIs are in main.py and schemas/academic.py. AdminCycleManager.tsx is the visible management screen.

Opening registration requires a policy. Maximum group size cannot be reduced below an existing active group's size. The backend locks cycle/policy records for sensitive changes. Cycle and policy updates are audited. The database constrains valid years and session values, with unique year/session combinations when both are specified.

The current UI has removed the cycle-delete button, but a backend delete handler still exists. Removing a button is not equivalent to removing an endpoint. Database constraints and the endpoint's role/usage checks remain relevant.

## 7.2 User and group administration

AdminUsersRoles.tsx manages staff/account fields, roles and activity. AdminStudentGroups.tsx presents shared group accounts and member lists. main.py performs role changes, protects critical administrator access, revokes sessions when needed, and writes admin audit records. The current API, not the label on a browser button, determines what a user may do.

Group details are assembled from users, teams, team_members, current supervisor assignment and the latest related request. Group name display is commonly derived from the leader's full name because the Team model does not have a dedicated group_name column. A group_name property in a response is therefore not proof of a separately persisted field.

## 7.3 Deadlines, reminders, templates and rubrics

Academic deadlines have a parent and versions. The preview accepts local wall time, an IANA zone and, when needed, an explicit UTC offset; the inspected version model persists due_at_utc and time_zone. Do not claim that local wall time and UTC offset are separate stored columns. main.resolve_deadline_time uses ZoneInfo and checks round trips to detect nonexistent or ambiguous daylight-saving times rather than guessing an offset.

Reminder rules also have versioned configuration. Their existence does not prove that an independent periodic worker automatically sends scheduled messages: the Compose stack contains no Redis/Celery service or general scheduler. Distinguish a rule definition from an executed notification.

Template references and academic rules preserve version history; active versions are selected for proposal checking. Evaluation rubrics have parent, version and criterion tables. Governance APIs can exist even when their frontend menu entries are currently absent. AdminPortal.tsx contains branches for deadlines/reminders, but its current navigation groups do not expose every branch.

# 8. Supervisor request, capacity and assigned groups

## 8.1 Supervisor request lifecycle

```text
DRAFT -> extraction review/confirmation -> SUBMITTED
SUBMITTED -> ACCEPTED
SUBMITTED -> REJECTED (reason required)
SUBMITTED -> CHANGES_REQUESTED (comment required)
CHANGES_REQUESTED -> revised extraction/confirmation -> SUBMITTED
Eligible open request -> WITHDRAWN
```

supervisor_requests stores title/summary, proposal type, extracted academic fields, the requesting shared user, team, cycle, chosen supervisor, document pointer, status, revision and decision timestamps. supervisor_request_documents stores document versions, original bytes, SHA-256, extracted text/fields and extraction state. supervisor_request_submission_note_versions preserves submitted notes. supervisor_request_status_history records actor, old/new status, comment and time.

The PDF selection component uploads a proposal, displays extracted fields, confirms extraction and submits the request. The backend owns eligibility checks and the accepted upload contract. A browser accept attribute is only a file-picker hint; it is not security validation.

## 8.2 Why acceptance is transactional

decide_request validates the selected supervisor and current request revision. For acceptance it locks the relevant records, verifies active capacity and the team/cycle relation, prevents an already active assignment, creates SupervisorAssignment, ensures the collaboration channel and links request.assignment_id. It then changes request status, writes decision history and audit events, and commits.

If any part fails, rollback prevents a partially accepted request without an assignment or an assignment without its history. A partial unique database index is the final guard against two active assignments for the same team. The revision check also prevents a supervisor acting on a stale browser copy.

## 8.3 Capacity calculation

Capacity policy is stored in supervisor_capacity_policies. _lock_capacity verifies the active supervisor and locks the selected annual/cycle policy. _capacity_used counts active assignments in the relevant academic year, including older assignments whose year is resolved through their cycle. It also counts accepted legacy requests not linked to an assignment. _ensure_capacity compares usage with max_group_capacity.

SupervisorCapacity.tsx displays a read-only breakdown. Administrators configure capacity. Accepted assignment rows now include the academic year/session when available. The live API can combine cycle-specific legacy policies with annual policies, so explain the actual lookup rather than claiming one unconditional row per supervisor.

## 8.4 Supervisor workspace implementation

supervisor_workspace.py provides /api/v1/supervisor/assigned-groups and /groups/{group_id}, plus members, proposal, project, documents, progress and conversation sections. /requests and /requests/{request_id} provide nested group information before a decision. Accept/reject/request-changes endpoints delegate to the existing transactional decision handler.

SupervisorAssignedTeams.tsx displays a group summary and opens SupervisorGroupDetails.tsx. The latter contains overview, members, proposal, project, documents and discussion tabs. SupervisorRequestsPdf.tsx embeds the same details during review. Primary labels show group names, emails and cycle names rather than raw internal IDs.

An assigned group's record is a joined response, not a duplicate database snapshot. It contains the real group, all members, assignment, supervisor, proposal request, required-document submissions and progress records. The related accepted request is prioritized using assignment_id; NULL-aware ordering matters because a later rejected request must not replace the assigned proposal in the display.

Completion is derived from recorded task completion, or from milestones when tasks are absent. The response provides a completion_basis. This derived display is different from a separately stored authoritative project percentage. Empty fields are displayed as not recorded/submitted rather than invented values.

## 8.5 Authorization and refresh

owned_group verifies an active assignment for the logged-in supervisor. owned_request verifies the selected supervisor and excludes drafts. Supervisors cannot use another group's URL to bypass these checks. A pending owned request may inspect related data through that request response without receiving general assigned-group access.

Assigned lists, selected group details and request views refresh on timers; group messages refresh more frequently. Acceptance removes the pending request and the next assigned-list load returns the group. The UI does not use a global live-event bus, so there can be a polling delay. Switching portals or remounting a view fetches fresh data.

# 9. Document requirements, versions and real files

## 9.1 Parent-child structure

- document_upload_requirements: title, instructions, cycle, optional assignee/group, permitted roles, extensions, size, due time, lifecycle and required/late settings.
- document_submissions: the requirement/group/student submission identity, status, late flag, reviewer feedback and timestamps.
- document_submission_versions: each uploaded filename, MIME type, size, uploader, version number and storage reference.
- Original required-document file bytes are written to DOCUMENT_STORAGE_ROOT rather than normally stored in the version content column.

Requirement lifecycle is DRAFT -> PUBLISHED -> CLOSED -> ARCHIVED, with explicit unpublish/reopen behavior. Only unused drafts may be deleted through the current API. A published/history-bearing requirement should be closed/archived according to its supported state transitions.

## 9.2 Upload and download flow

1. StudentRequiredDocumentsDashboard.tsx loads published/closed group requirements and existing submission/version data.
2. The form submits multipart content to the group requirement upload/resubmit endpoint.
3. The backend checks group/cycle visibility, requirement state, deadline/late policy, extension, MIME type, maximum bytes and implemented signature checks.
4. It obtains or creates the submission parent and calculates the next version.
5. It creates a random server storage name, writes a temporary file, renames it, writes version metadata and audits the operation.
6. Successful commit returns all versions. Failed persistence cleans up the temporary/new file in the relevant upload handler.
7. The student sees version history. Admin View submissions lists student/group context and all uploaded versions.
8. The download endpoint verifies the submission/version relationship and role/ownership before returning FileResponse with the original filename.

The storage path is derived and resolved under the configured root to block path traversal. Never trust a user filename as a direct disk path. Opening an arbitrary storage_reference from the database must still pass authorization before returning bytes.

## 9.3 File-type limitations to know before the demo

The active form now lists document, image, video, audio, spreadsheet, presentation, archive and any-supported-format categories. Pydantic accepts an extensive extension set. However, backend _validate does not implement successful signatures for every advertised format: several entries default to false and are not overridden, including legacy XLS/PPT, MP3 and WEBM in the inspected implementation. MIME checks are also strict and browsers can submit different or missing MIME types. Therefore, do not claim that every listed format is end-to-end supported without testing actual files.

Other practical constraints: Nginx has no explicit client_max_body_size in the inspected frontend/nginx.conf, so its own default request-body limit may reject a file before the backend's configured 10/100 MB allowance. A 413 response can originate at the proxy. The student upload UI also disables overdue uploads unconditionally in its current state, while the backend has a late_upload_allowed flag; late reopening requires a UI/backend consistency check before demonstration.

# 10. Proposal extraction, template compliance and AI

## 10.1 Separate proposal workflows

| Workflow | Main record | Purpose |
|---|---|---|
| Supervisor selection | supervisor_requests + supervisor_request_documents | Ask a supervisor to accept the group and discuss the submitted proposal |
| Template compliance | proposal_compliance_submissions + proposal_compliance_reports | Compare an uploaded proposal against active template rules |
| Historical proposal reference | proposal_references + proposal_reference_documents | Advisory title lookup against reference material |
| Previous FYP archive | archived_projects + archived_project_documents | Historic project discovery and imported workbook data |
| Foundation proposal identity | proposals + proposal_versions | Minimal identity/version foundation; not the complete current content store |
| Historical m03 tables | m03_* | Existing database objects absent from current ORM; verify before claiming they power an active feature |

## 10.2 Extraction is local and deterministic

pdf_extraction.py uses pypdf for PDF text, PyMuPDF for measurable layout information and python-docx for DOCX structure/formatting. It computes SHA-256 and returns a structured extraction result with text, fields, page information and extraction metadata. Academic headings/labels are identified by rules and patterns. OCR is not a demonstrated general capability here; an image-only scanned PDF may not provide readable text.

DOCX can expose native formatting such as margins, font runs, paragraph spacing, styles, tables and headings. PDF layout measurement is an estimate from positioned text and document geometry; it is not equivalent to reading original editable Word settings. Some checks must remain UNVERIFIABLE when information is unavailable.

## 10.3 Compliance processing

AdminProposalTemplates.tsx uploads/activates a reference template through the module-3 API. The backend extracts measurable rules and stores the active reference version and rule payload. A student submits PDF/DOCX/TXT through ProposalComplianceWorkspace.tsx. The backend finds an active template for SHORT/LONG, records the next proposal_key/version, saves the original file, extracts fields and builds a report.

build_compliance_report checks rule-provided page layout, font formatting, paragraph properties, heading styles, tables/figures/captions, references, appendices, required sections and sequence. Required-heading matching uses difflib.SequenceMatcher with a threshold of 0.82. Numeric formatting comparisons use a tolerance of 0.05 when both values are numeric. Missing measurable values produce UNVERIFIABLE rather than a fabricated match.

Academic consistency compares token vocabularies between sections. Tokens are case-normalized, filtered and compared by intersection divided by the smaller token-set size. The inspected thresholds are 0.20 for PASS, 0.08 for PARTIAL, otherwise FAIL; missing text is UNVERIFIABLE. This is a lexical heuristic, not proof of semantic correctness or research originality.

The score is round(passed checks / total checks * 100). A report is Compliant only when the logic finds no failures or partial/unverifiable checks; it can be Not Compliant or Review Required. The report JSON stores explanations, violations, sections and version history. Report endpoints expose original, annotated and report PDF outputs subject to access checks. Submission can lock the group's membership through team_lifecycle.lock_team.

The report engine is deterministic Python. build_change_summary labels its source AI_ASSISTED_DETERMINISTIC and model local-change-analyzer, but compares structured values locally. Do not describe this label as evidence that a language model generated the summary.

## 10.4 Optional AI provider layer

ai_provider.py supports configured Ollama and Groq clients, explicit model selection, timeouts, bounded retries, rate limiting and Pydantic JSON-response validation. The prompt tells the model to treat submitted text as data and remain advisory. Proposal review expects exactly seven required section findings in order with actionable text and confidence values.

Invalid configuration, timeouts, provider errors or invalid JSON produce explicit UNAVAILABLE/RATE_LIMITED or deterministic fallback metadata. Ollama can attempt a configured fallback model. API keys remain backend environment settings. Do not promise that a model is available simply because the Ollama container is running; the selected model must be downloaded and responding.

The agent-supervision backend persists plans and requires appropriate human approval before tool execution. Its supervisor navigation/module was removed at the user's request, but the backend router and supervision_agent_runs table remain. Hiding a UI feature does not delete its API or schema.

# 11. Previous-project Excel archive and knowledge search

## 11.1 Why this is project-oriented

AdminArchiveProjects.tsx presents one project card with related information, original import fields, editing and a centered delete confirmation. OldProjectArchiveImport.tsx handles the file selection/import action. ArchiveManagement.tsx is the active wrapper imported by AdminPortal.tsx.

The main database parent is archived_projects. A project title is display/search content, while the numeric primary key is its stable identity. The import grouping key combines cycle, normalized project title and resolved group/block context so repeated member rows can belong to the same project. Do not make title alone globally unique across every year and group.

## 11.2 Parser, grouping and provenance

parse_archive_workbook accepts XLS/XLSX, enforces the configured byte limit, extracts populated columns, removes blank values and known Excel errors, and applies the literal-email end boundary when an email column/value exists. XLSX is read in formula and data-only modes so formulas can be identified and excluded even when they have cached results. Without an email boundary it uses the last literal content row.

Current grouping helpers recognize explicit project-title aliases instead of blindly using the first populated cell as a title. _resolved_import_rows forward-fills merged project context within a worksheet block. _import_group_key combines the academic cycle, normalized title and group/block discriminator. _archive_import_group combines members and academic metadata. Existing matching projects can receive merged non-destructive data and deduplicated members.

archive_import_batches records original filename, uploader, processed/inserted/skipped/invalid counts, status and time. archived_projects.source_metadata preserves columns, cells, worksheet, source rows and row range. Flexible content is retained in JSONB; mapped metadata supports search and normal display. An imported worksheet with many member rows should not necessarily create the same number of projects.

Legacy XLS formula detection is less explicit than the XLSX path: xlrd generally returns cell values and the fallback formula-type comparison is not proof that every cached legacy formula can be excluded. State this as a format limitation and use the fixture tests to demonstrate supported behavior.

## 11.3 Search ranking

The inspected archive search is deterministic, not semantic/vector search. A normalized exact title match scores 100, a prefix/contained title match 80, keyword match 60, summary token overlap 40, scope/technology overlap 30 and remaining-gap overlap 20. Results sort by descending score and stable title/id ordering. The response explicitly reports semantic_search: unavailable and advisory: true.

Search filters include year/session/department/supervisor/technology and supported scope/stage parameters. Student-visible results require active, visible archive records. The pgvector extension's presence does not change this search into embedding similarity. An honest defence answer is that vector capability is installed but the current archive route uses explainable lexical scoring.

## 11.4 Edit, delete and historic documents

The editor preserves original workbook columns and updates stored cells through PATCH. Imported values can be remapped into structured fields for display. Archived project document versions are stored separately in archived_project_documents, including BYTEA content for original PDFs. Download authorization is checked before bytes are returned.

The current archive delete endpoint permanently deletes the selected archive and its stored document versions according to its implementation. The centered frontend confirmation is only UX; backend role/origin checks still enforce access. Visibility/soft-retirement operations also exist separately. Explain which operation the demonstrated button invokes.

# 12. Progress, meetings, discussions and notifications

## 12.1 Progress data and visual timeline

project_workflow.py stores milestones, tasks and supervision meetings. StudentProgressDashboard.tsx loads a permitted group, reads /project-progress/{team_id}, renders summary cards/timeline and submits create/update actions. A task may link to a milestone and an owner. Records include due dates and completion percentages.

The timeline is a CSS grid representation of dates and task/milestone spans. It is not an AI scheduler or a full critical-path scheduling engine. Completion updates are persisted through API calls. The supervisor workspace derives overall completion from task values, falling back to milestone values when appropriate.

_health counts overdue incomplete tasks/milestones: at least three produce Critical; any overdue item or a milestone below 50% produces Attention Required; otherwise On Track. This is a transparent heuristic. It does not infer project quality from code or proposal content.

Meetings record held_at, supervisor, minutes, decisions and optional action items. A stored meeting entry is supervision evidence; it is not proof that calendar invitations were emailed or a video call was created.

## 12.2 Three conversation-related concepts

- supervisor_request_messages is a request-specific conversation used before/after request decisions.
- collaboration_channels/participants/messages is an assignment-specific group discussion. It links to assignment_id, team_id and supervisor_id, so reassignment can archive an older channel instead of merging unrelated histories.
- group_messages and module2_* helpers are an earlier/general group communication and notification foundation. Check which frontend imports/API path the demonstration uses.

The explicit student/supervisor collaboration-message routes are now registered separately. An earlier invalid route pattern had caused 404 errors and was corrected. Backend authorization verifies group/assignment access independently of the URL role prefix.

Student group discussion navigation was intentionally removed earlier. The backend still supports authorized student discussion routes, and request conversation remains separately available. Do not promise an always-visible student discussion button if the current sidebar does not expose it.

## 12.3 Notifications

notifications.py lists recipient-scoped module2_notifications and marks individual notifications read. module2_collaboration.py contains supporting deadline/channel data. Read status is stored; polling is used by relevant UI components. A notification table is not an external email/push service and should be described separately from SMTP password recovery.

# 13. Evaluations, defence scheduling and results

## 13.1 Two related evaluation implementations

project_workflow.py provides defense_schedules, defense_panel_members, panel_evaluations and panel_evaluation_scores. It checks time ordering, student/evaluator scheduling conflicts, assignment scope and panel scoring state. EvaluatorWorkflow.tsx consumes these APIs. PanelScheduling.tsx exists but must be checked against the current coordinator composition before claiming it is reachable.

evaluations.py is a separate formal marks/publication API using evaluation_records, evaluation_audit_events, evaluation_corrections and evaluation_aggregation_configs. EvaluationMarksWorkspace.tsx exists, but its current reachability and role-shell integration should be checked in the frontend appendix. The two scoring stores are not automatically one synchronized table.

## 13.2 Formal evaluation categories

| Category | Maximum marks | Responsible role in the inspected API |
|---|---|---|
| Final presentation | 30 | Assigned PANEL_MEMBER |
| Mid review | 30 | Assigned PANEL_MEMBER |
| Supervisor evaluation | 10 | Assigned SUPERVISOR |
| Project documentation | 20 | ADMIN / COORDINATOR |
| Proposal | 10 | ADMIN / COORDINATOR |
| Total | 100 | Consolidated result calculation |

Formal state progresses through DRAFT, SUBMITTED, RETURNED, APPROVED and PUBLISHED according to the supported handlers. Marks must fit the category maximum. Target input identifies exactly one student or group. Admin correction/publishing creates history rather than pretending the originally submitted mark never existed.

Panel aggregation can use AVERAGE, MAXIMUM or MEDIAN according to active configuration. The result total sums the five category values. In the inspected grade mapping, 90+ gives A+/4.00, 85+ A/3.75, 80+ A-/3.50, 75+ B+/3.25, 70+ B/3.00, 66+ B-/2.75, 63+ C+/2.50, 60+ C/2.00, 55+ C-/1.50, otherwise F/0.00. Incomplete category data produces no final grade/GPA. Published student results select published marks only.

These are application rules in source, not a claim that they match every university's grading policy. Be prepared to point at schemas/evaluations.py and evaluations._grade and explain where a university-approved policy would be configured or changed.

# 14. Storage, deployment and operations

## 14.1 Where the real data lives

| Data | Persistent location | Source configuration |
|---|---|---|
| PostgreSQL records | Named volume fyphub-p1-postgres-data mounted at /var/lib/postgresql/data | docker-compose.yml db service |
| Required-document uploads and compliance files | Named volume fyphub-p1-document-data mounted at /app/storage/document-requirements | DOCUMENT_STORAGE_ROOT and Compose backend volume |
| Supervisor-request PDFs and some historic/reference documents | BYTEA columns in their document tables | Corresponding ORM content fields and download handlers |
| Ollama model files | fyphub-p1-ollama-models mounted at /root/.ollama | Compose ollama service |
| Source code | Repository checkout | Git |
| Served browser assets | Frontend image/container /usr/share/nginx/html | frontend Dockerfile/Nginx |
| Private runtime settings | Root .env and container environment | config.py and Compose env_file |

Document storage can include a feature subdirectory such as document-requirements/{requirement}/{actor}/random.ext beneath DOCUMENT_STORAGE_ROOT. Do not confuse the apparent repeated directory name with a second database. Keep the database and file volume consistent when backing up/restoring.

## 14.2 Containers and ports

PostgreSQL is reachable inside the Docker network as db:5432 and from this computer at 127.0.0.1:55732. The backend listens on container 8000 and is exposed on host 8010. The production frontend serves container port 80 on host 5173. Ollama uses 11434 inside the network. Container-local localhost is not the database container; use service DNS names within Compose.

The backend's health endpoint reports liveness. /health/ready checks SQL access and the vector extension; it does not check every table, migration, stored document or AI model. The migrate service runs alembic upgrade head. The backend depends on successful migration, model initialization and storage initialization under normal Compose startup.

## 14.3 Useful commands for defence preparation

Run these from the repository root unless stated otherwise. They are diagnostic examples; none of the documentation-generation commands reset the database.

```powershell
docker compose ps -a
docker compose logs --tail=100 backend
docker compose logs --tail=100 migrate
Invoke-WebRequest http://localhost:5173
Invoke-WebRequest http://localhost:8010/health/ready
docker compose exec backend alembic heads
docker compose exec backend alembic current
```

Build the frontend from frontend/ using npm.cmd run build on Windows. The dev server uses npm.cmd run dev and Vite's configured /api proxy. A local source edit does not automatically change an already-built production Nginx container. Rebuild/redeploy deliberately and verify the served assets, especially if manual docker cp deployment was used during development.

## 14.4 Migration status found during inspection

The migration repository currently has three heads: fb1c2d3e4f5, qa1b2c3d4e5f and rf9a0b1c2d3e. The running alembic_version table reports rf9a0b1c2d3e. The migrate service is exited with code 255 while the existing application/database services are healthy.

Therefore a fresh docker compose up that runs alembic upgrade head must not be described as verified working from an empty database. Multiple heads make singular head ambiguous and may indicate branches requiring a reviewed merge. This documentation task does not stamp, merge, downgrade or reset the database. Existing application readiness does not resolve migration-history consistency.

Appendix E lists every source revision and parent. Appendix A compares ORM and installed tables. Historical m03_* and team_member_verifications tables remain in the running database although they are absent from current ORM metadata. They may be remnants of earlier modules; do not delete them during defence preparation without a data/migration review.

## 14.5 Backup and recovery principles

A PostgreSQL dump protects database records, including BYTEA files inside the database. It does not automatically protect files stored in the separate uploaded-files volume. Back up that volume too. Ollama models can be backed up separately or downloaded again if network/time permit. Source and environment configuration are separate assets; keep .env private.

Use pg_dump with the configured database/user. Do not display database passwords during a screen recording. Avoid docker compose down -v because it removes persistent volumes. A valid recovery rehearsal restores into an isolated environment and verifies schema, documents and login, rather than overwriting the working defence database.

# 15. Security, transactions and error handling

## 15.1 Controls present in the code

- Authentication resolves a hashed session and active account on the server.
- Role guards use the database role, not a role chosen by the browser.
- Group/request/document access checks restrict cross-group data access.
- Pydantic schemas normalize and validate field types, required values, ranges and allowed enums.
- SQLAlchemy uses parameterized expressions rather than concatenating user input into SQL statements.
- Row locks and partial unique constraints protect allocation/capacity workflows.
- Revision checks reject stale request decisions.
- Origin checks protect mutating browser requests within the configured deployment.
- File handlers enforce the implemented type/size/signature checks, random storage names and resolved root paths.
- Admin and evaluation events store actor, target, action, changed data and timestamps.
- Request middleware adds X-Request-ID and structured timing/status logs.

## 15.2 Error meanings you should explain

| Status | Typical meaning in this application | Example |
|---|---|---|
| 200 / 201 | Successful read/update or creation | Group details / uploaded version |
| 204 | Successful deletion/action without response content | Delete unused draft |
| 400 | Invalid operation-specific input | Bad reset token |
| 401 | No valid authenticated session | Expired/revoked cookie |
| 403 | Authenticated but not permitted | Wrong role or document ownership |
| 404 | Missing or intentionally hidden inaccessible record | Another supervisor's assigned group |
| 409 | Workflow, capacity, concurrency or uniqueness conflict | Full capacity, closed requirement, stale revision |
| 410 | Metadata exists but stored file is absent | Download reference whose file is unavailable |
| 413 | Payload too large | Backend byte limit or proxy request limit |
| 422 | Request validation failure | Missing member name, invalid type/extension |
| 500 / 503 | Internal failure or dependency unavailable | Persistence exception / database readiness failure |

An HTTP fetch rejection is not always a Python error. Network failure, backend startup, proxy resolution, cookie scope, CORS/origin rules, and body limits can all affect requests. Inspect the Network tab and request_id, then correlate Nginx/backend logs. A browser-rendered error message alone is insufficient evidence of its root cause.

## 15.3 Limits of the current implementation

Avoid claiming antivirus scanning, full OCR, automated plagiarism detection, distributed rate limiting, WebSocket delivery, production TLS termination, comprehensive fine-grained permissions or full microservice isolation unless the specific implementation is demonstrated. They are not established by the inspected code alone.

# 16. Testing evidence and how to present it

## 16.1 What the test directories cover

Backend tests include registration/auth/session revocation, password policy/reset, team constraints and compatibility helpers, cycle concurrency, user governance, deadlines, reminder/rubric/template versions, supervisor capacity/requests/assignments, PDF extraction, archive import/persistence, document visibility, group access/collaboration, proposal compliance, AI provider behavior, progress/scheduling, evaluations/results and observability.

The generated file atlas enumerates each test method. Many integration suites connect to fyphub_p1, wrap operations in an outer transaction and use savepoints so data can roll back. Read the test fixture before running it; do not assume every test is an isolated in-memory unit test. The root/backend Python may not have pytest installed even if Docker has the application dependencies. Some suites are unittest-based; others use pytest-style functions.

Frontend tests are Node .mjs sources for selected contracts/visibility. npm build runs TypeScript compilation and Vite production bundling. npm lint runs ESLint. These checks do not prove that every browser interaction was visually tested.

## 16.2 Verification claims for this guide

This documentation task performs read-only runtime schema/route inspection, source parsing/import tracing, and generated-file checks. It does not claim a fresh pass of every existing test. Earlier implementation work verified selected supervisor workspace integration cases and frontend builds, but the current source inventory is a separate snapshot. Record actual new test results if you run a defence rehearsal after this document is generated.

Example targeted commands, subject to the fixture/environment requirements:

```text
Frontend directory: npm.cmd run build
Frontend directory: npm.cmd run lint
Backend directory: python -m unittest tests.test_supervisor_workspace
Backend directory: python -m pytest tests/test_archive_import.py
Repository root: python scripts/build_defence_guide.py --build
```

Tests are not always copied into the backend production image by its Dockerfile. If a container cannot import tests, that is a packaging/path issue rather than proof of a failing academic workflow. Use the documented project test environment or copy/mount tests deliberately.

# 17. Known gaps and honest defence boundaries

| Finding | Evidence | What to say / what it affects |
|---|---|---|
| Multiple Alembic heads; migrate exited 255 | alembic heads/current and Compose status | Existing stack works; clean schema bootstrap needs migration reconciliation |
| Legacy tables remain | Catalog has m03_* / team_member_verifications absent from ORM | Installed schema includes historical objects; current models are the active mapping |
| Agent UI removed, backend remains | Supervisor navigation versus registered agent router | Product exposure and backend capability are different |
| Archive search is lexical | archived_projects.search_archives response and scoring | Explainable deterministic search; no current embedding search |
| Several advertised file formats lack implemented signatures | document_requirements._validate | Verify actual demo file types; dropdown alone is not end-to-end support |
| Proxy upload limit not explicitly set | frontend/nginx.conf | Large uploads may be rejected before FastAPI |
| Some frontend navigation is state-driven | App.tsx and role shells | Refresh/deep links are only supported where coded |
| Coordinator sidebar selection does not switch all content | CoordinatorPortal.tsx fixed content composition | PanelScheduling source exists but current shell does not mount it by page state |
| Multiple evaluation/proposal workflows | Distinct models and routers | Do not claim automatic synchronization between independent stores |
| Supervisor project is assembled/derived | supervisor_workspace.workspace | No standalone general projects table; completion comes from tasks/milestones |
| Group display name is derived | Team model and group serializers | Response group name is usually built from leader data |
| In-memory rate limits | ai_provider.py, password_reset.py | Single-process protection; not a distributed limiter |
| CSS has layered overrides and !important | design-system.css plus feature styles | Current appearance depends on cascade/import order; consolidate for maintainability |
| Compliance uses lexical/format heuristics | compliance_engine.py | Useful automated checks; not a substitute for academic review or semantic proof |
| Student discussion entry removed earlier | StudentPortal phase list | Supported backend discussion does not imply visible navigation everywhere |

This is a preparation report, not an authorization to repair these issues. Keep this table available for viva questions about limitations and future work. State the boundary clearly and describe the appropriate next engineering step.

# 18. Demonstration plan with source and database checkpoints

## 18.1 Pre-demo check

Verify frontend/backend health, known accounts/roles, the chosen academic cycle, configured group limits and supervisor capacity, a published document requirement, an active proposal template and the existence of the actual sample files. Prepare small supported files to avoid proxy/MIME surprises. Keep personal passwords and private .env values off screen.

## 18.2 Main demonstration path

1. Admin shows academic cycle and group policy. Explain academic_cycles/academic_group_policies and the registration guard.
2. Student signs up a group using member names, emails and registrations plus shared credentials. Explain users -> teams -> team_members.
3. Student logs in. Explain cookie/token hashing and show /auth/me response fields without exposing credentials.
4. Student submits a supervisor proposal request, inspects extraction, confirms and submits. Explain request/document/note/history tables.
5. Supervisor opens the request and checks members, proposal, documents and capacity before deciding.
6. Supervisor accepts. Explain transaction, row locks, unique active assignment and request.assignment_id.
7. Supervisor opens Assigned Students & Teams and a full group detail route. Explain the joined workspace response.
8. Student uploads a required document. Admin opens View submissions, and an authorized user downloads the original version. Explain metadata versus file bytes.
9. Student creates/updates milestone or task progress. Supervisor view picks it up on the next polling load. Explain completion/health derivation.
10. Show request conversation or supported group discussion and demonstrate a message appearing for the authorized recipient.
11. Admin imports a prepared historic workbook. Explain one project parent, multiple members, source provenance and skipped formulas/blanks.
12. Student searches the archive, opens a project and explains deterministic scoring and visibility.
13. Demonstrate compliance with a configured active template only if the selected sample meets the supported extraction contract.
14. Demonstrate evaluation through its actually mounted UI/API path; explain publication and audit if used. Avoid opening an unmounted placeholder as a promised finished feature.

## 18.3 Read-only SQL questions to practice

These example queries show relationships. Execute them only in an authorized database session. Do not select password_hash, token_hash or private uploaded bytes for a public demonstration.

```sql
-- Find groups and their shared login identity.
SELECT t.id, u.full_name, u.email, c.display_name, t.status
FROM teams t
JOIN users u ON u.id = t.shared_user_id
JOIN academic_cycles c ON c.id = t.academic_cycle_id
ORDER BY t.id DESC;

-- All group members, showing real stored names.
SELECT tm.team_id, tm.full_name, tm.registration_number,
       tm.university_email, tm.is_creator, tm.is_active
FROM team_members tm
ORDER BY tm.team_id, tm.is_creator DESC, tm.id;

-- Active allocations with readable supervisor/cycle values.
SELECT sa.team_id, u.full_name AS supervisor, c.display_name,
       sa.created_at AS assigned_at
FROM supervisor_assignments sa
JOIN users u ON u.id = sa.supervisor_id
JOIN academic_cycles c ON c.id = sa.academic_cycle_id
WHERE sa.ended_at IS NULL;

-- A requirement and its submitted versions.
SELECT r.title, s.group_id, s.status, v.version_number,
       v.original_filename, v.file_size, v.uploaded_at
FROM document_upload_requirements r
JOIN document_submissions s ON s.requirement_id = r.id
JOIN document_submission_versions v ON v.submission_id = s.id
ORDER BY r.id, s.id, v.version_number;

-- Project archive provenance without dumping original private cells.
SELECT p.title, p.academic_year, p.session_name,
       p.source_batch_id, b.original_file_name
FROM archived_projects p
LEFT JOIN archive_import_batches b ON b.batch_id = p.source_batch_id
WHERE p.is_active = TRUE;

-- Show installed migration state and installed extensions.
SELECT version_num FROM alembic_version;
SELECT extname, extversion FROM pg_extension ORDER BY extname;
```

# 19. Viva questions and accurate answers

## 19.1 Architecture and frontend

Q: What architecture does FYPHub use?

A: A modular monolith: a React SPA, one FastAPI backend with feature routers, PostgreSQL, file storage and optional AI. Containers separate deployment processes; academic modules remain in the same application.

Q: Where does execution start?

A: frontend/src/main.tsx mounts App.tsx. Backend Uvicorn imports app.main:app. main.py configures middleware, core handlers and feature routers.

Q: How does the frontend know which portal to show?

A: Login or /auth/me returns the persisted user role and group context. App.tsx selects the matching portal; backend permissions remain independently enforced.

Q: Is hiding a sidebar item security?

A: No. It is UI exposure. Authentication, roles and ownership are enforced by backend dependencies and queries, and some removed UI features still have registered endpoints.

Q: Is this React Router / Redux?

A: The inspected dependency list uses React state/effects and manual history logic. Do not claim React Router or Redux when they are not installed/used.

Q: How do changes appear automatically?

A: The relevant views refetch after actions and use polling timers. This is periodic HTTP refresh, not WebSocket push.

Q: Where is the system color defined?

A: main.tsx imports index.css followed by design-system.css. Feature CSS and utility classes also contribute. The final brand override uses royal blue #124BC4; sign-in/signup retains its photo and translucent form card.

## 19.2 Backend and security

Q: Why use FastAPI and Pydantic?

A: FastAPI provides HTTP routes, dependency injection and OpenAPI. Pydantic validates/normalizes request contracts before workflow logic executes. Database constraints provide a separate integrity layer.

Q: Are passwords stored in plaintext or reversibly encrypted?

A: Neither. security.py hashes passwords with Argon2id and verifies the hash. Responses exclude password_hash.

Q: Are login tokens JWTs?

A: No. The browser stores an opaque HttpOnly cookie, while auth_sessions stores a hash, expiry and revocation state.

Q: How do you stop one supervisor reading another group?

A: owned_group queries an active assignment matching both group and authenticated supervisor. The backend does not trust the group_id or frontend role label.

Q: Why use a revision number for request decisions?

A: It rejects an action based on stale data if the student or another action has changed the request since the supervisor loaded it.

Q: What prevents a race for the last supervisor slot?

A: Locked capacity/user/cycle records, a capacity recheck inside the transaction, and uniqueness constraints for active group assignment. Frontend availability is advisory and can become stale.

Q: What happens if assignment creation succeeds but history writing fails?

A: The transaction rolls back when the handler catches the failure, preserving consistency rather than committing a partial allocation.

Q: Is SQL injection prevented by hiding SQL from users?

A: No. SQLAlchemy parameterized queries keep values separate from SQL structure; validation and authorization are additional protections.

Q: How do you protect uploaded paths?

A: Random server-side filenames, sanitized display names and root-resolved storage references. Access checks happen before serving the original file.

## 19.3 Database and features

Q: Where is the database file for supervisor requests?

A: There is no separate supervisor database file. supervisor_requests and its related tables live in PostgreSQL, whose physical data is in the PostgreSQL volume. The model is backend/app/models/supervisor_request.py.

Q: Why separate submission and version tables?

A: The parent identifies one academic submission; child rows preserve every uploaded version and its metadata. Replacing a file should not erase the version history.

Q: Why do imported projects use JSONB?

A: Different historical workbooks have different columns. JSONB preserves the original flexible structure while mapped relational fields support search and stable parent identity.

Q: Can project titles act as primary keys?

A: No. Titles can repeat across years/groups or be edited. Numeric IDs are stable keys; normalized title plus scope/context is used for import matching and selected uniqueness rules.

Q: Does a PDF download come from React?

A: React requests an authorized backend endpoint. The backend returns actual bytes from file storage or a document BYTEA field, with the correct content type and filename.

Q: What is the difference between group_id and team_id?

A: They are naming aliases in several application contracts for the same teams identity. Check each column/relationship rather than assuming a separate groups table exists.

Q: Where is the project completion stored?

A: Tasks/milestones store completion_percent. Supervisor workspace completion_percentage is derived from those records; archived projects can separately store historic imported completion.

Q: Why is there more than one evaluation implementation?

A: The code contains a panel scheduling/scoring workflow and a separate formal marks/publication workflow. They have different parent tables and must be explained separately until explicitly integrated.

Q: What does a migration do?

A: It applies an ordered structural change to the database. Models describe intended mappings; migrations and installed alembic_version determine which schema transitions were applied.

Q: Does a healthy readiness endpoint guarantee all features are ready?

A: No. It verifies database connectivity and the vector extension. It does not validate every table, file, migration branch, SMTP server or AI model.

## 19.4 AI, extraction and algorithms

Q: Is proposal text extraction AI?

A: The current PDF/DOCX extraction is local deterministic parsing. A separate configured provider can generate advisory feedback; these are different stages.

Q: Is the compliance score an LLM opinion?

A: The compliance engine computes checks and a passed/total percentage with Python rules. Optional advisory AI review is stored separately.

Q: Can your system detect plagiarism?

A: The inspected title/reference search and lexical consistency checks are advisory. They are not a demonstrated full plagiarism or semantic originality engine.

Q: Why is pgvector installed if search is not vector-based?

A: The extension is part of the data platform/readiness requirement. The current archive route explicitly uses deterministic lexical ranking. Installing an extension does not implement embeddings or nearest-neighbor search.

Q: What happens when the AI service is down?

A: The provider layer returns explicit failure/fallback metadata; supported callers use deterministic fallback or an unavailable state. Normal authentication and database operations do not depend on successful AI feedback.

Q: Does temperature zero guarantee correct AI output?

A: No. Schema validation checks structure and constraints; academic correctness still requires review. Prompt instructions and confidence values do not guarantee truth.

Q: Why can a proposal check be UNVERIFIABLE?

A: Some formats do not expose a reliable measurable value, particularly editable formatting lost in PDFs. Marking uncertainty is more accurate than inventing a measurement.

Q: How does the archive avoid thousands of empty rows?

A: It strips blank/error/formula cells, ignores empty rows/columns, finds a content boundary and uses the last literal email where available. Grouping then combines multiple member rows under a project parent.

Q: Are all spreadsheet formulas safely excluded in every format?

A: The XLSX path explicitly compares formula/data-only readings. The legacy XLS reader has weaker formula visibility, so claim the tested behavior and state that format limitation.

## 19.5 Deployment, limitations and future work

Q: Why can localhost work in the browser but fail inside Docker?

A: localhost refers to the current machine/container. Services use Compose DNS names such as db and backend inside the Docker network.

Q: What must be backed up?

A: PostgreSQL plus uploaded-file storage; source/configuration and optionally model downloads are separate. A SQL dump alone does not include filesystem-only uploads.

Q: What are the most important current limitations?

A: Migration branching, partial/legacy UI integration, upload-format/signature gaps, state-driven navigation, lexical rather than semantic search, and separate evaluation/proposal stores. Point to the evidence table and a concrete future change.

Q: What would you improve for production?

A: Reconcile migration heads and test a clean install; consolidate theme/components and API error handling; align upload limits and validators; add distributed rate limiting/background jobs if needed; integrate overlapping workflows; add browser end-to-end coverage; configure real-domain HTTPS/origin handling and verified backups.

# 20. Final revision checklist

- Can every team member explain the full browser -> API -> database/file flow for at least one major feature?
- Can you locate the model, schema, handler, active frontend file and relevant test in under one minute?
- Can you distinguish shared group accounts from member contact records?
- Can you explain the request, assignment and discussion foreign keys without relying on screenshots?
- Can you download the original submitted file and explain where its bytes reside?
- Can you show an actual negative authorization or stale/capacity check?
- Can you explain which algorithms are deterministic and which calls use an external/local model?
- Can you state the known migration and file-format gaps accurately?
- Is your demonstration data prepared, small enough for proxy limits, and free of private credentials on screen?
- Have you checked the current application after the last build rather than relying only on an old screenshot?

The remaining appendices are generated directly from the inspected source and running schema. Use them as the exact lookup reference for file locations, line numbers, API ownership, table columns and database constraints.
