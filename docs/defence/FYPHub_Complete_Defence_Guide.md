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

# Appendix A — Inspection evidence and counts
Inspection: 2026-11-11 (Asia/Karachi). Git snapshot: `f11c5064af86777e2867054de692baef3ca7e11a`. The guide describes source and the running database as inspected, not a claim that every feature was tested during this documentation task.
Inspected source/configuration files in the generated inventory: 352. Live public tables: 70. ORM tables: 58. Registered application route entries: 264. Multiple methods/aliases can share one handler.
Database migration version(s): `rf9a0b1c2d3e`.
Migration repository heads: `fb1c2d3e4f5 (head)`, `qa1b2c3d4e5f (head)`, `rf9a0b1c2d3e (head)`.
Extensions: plpgsql 1.0, vector 0.8.6.
Tables present in database but absent from current ORM metadata: alembic_version, m03_ai_runs, m03_compliance_findings, m03_compliance_reports, m03_proposal_access, m03_proposal_change_summaries, m03_proposal_documents, m03_proposal_records, m03_proposal_submissions, m03_reference_templates, m03_template_rule_sets, team_member_verifications. Historical/retired tables are not proof of active features.
ORM tables absent from the live database: None.

# Appendix B — Complete feature database dictionary
This is generated from the running PostgreSQL catalog. No user rows, passwords, tokens, uploaded content or secrets are included. Locate the model file beside each table; the model declares the intended structure, while the catalog describes the actual installed database.

## Table: academic_cycles
Model source: `backend/app/models/academic.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".academic_cycles_id_seq'::regclass) |
| code | VARCHAR(100) | No | — |
| display_name | VARCHAR(255) | No | — |
| registration_open | BOOLEAN | No | false |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| academic_year | INTEGER | Yes | — |
| session | VARCHAR(16) | Yes | — |
- Check `ck_academic_cycles_code_normalized`: `code::text = upper(btrim(code::text)) AND code::text <> ''::text`.
- Check `ck_academic_cycles_display_name_nonblank`: `display_name::text = btrim(display_name::text) AND display_name::text <> ''::text`.
- Check `ck_academic_cycles_session_valid`: `session IS NULL OR (session::text = ANY (ARRAY['FALL'::character varying, 'SPRING'::character varying]::text[]))`.
- Check `ck_academic_cycles_year_valid`: `academic_year IS NULL OR academic_year >= 1900 AND academic_year <= 2200`.
- Index `uq_academic_cycles_code_normalized`; unique=True; columns/expressions `[None]`; options `{'postgresql_include': []}`.
- Index `uq_academic_cycles_year_session`; unique=True; columns/expressions `['academic_year', 'session']`; options `{'postgresql_where': '((academic_year IS NOT NULL) AND (session IS NOT NULL))', 'postgresql_include': []}`.

## Table: academic_deadline_versions
Model source: `backend/app/models/academic_deadline.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".academic_deadline_versions_id_seq'::regclass) |
| academic_deadline_id | INTEGER | No | — |
| version_number | INTEGER | No | — |
| name | VARCHAR(160) | No | — |
| description | TEXT | Yes | — |
| due_at_utc | TIMESTAMP WITH TIME ZONE | No | — |
| time_zone | VARCHAR(100) | No | — |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `academic_deadline_id` → `academic_deadlines(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_academic_deadline_version`: `academic_deadline_id, version_number`.
- Index `uq_academic_deadline_version`; unique=True; columns/expressions `['academic_deadline_id', 'version_number']`; options `{'postgresql_include': []}`.

## Table: academic_deadlines
Model source: `backend/app/models/academic_deadline.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".academic_deadlines_id_seq'::regclass) |
| academic_cycle_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.

## Table: academic_group_policies
Model source: `backend/app/models/academic.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".academic_group_policies_id_seq'::regclass) |
| academic_cycle_id | INTEGER | No | — |
| max_group_size | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| min_group_size | INTEGER | No | 1 |
| formation_deadline | TIMESTAMP WITH TIME ZONE | Yes | — |
| matching_weights | JSONB | No | '{}'::jsonb |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'CASCADE'}`.
- Unique constraint `academic_group_policies_academic_cycle_id_key`: `academic_cycle_id`.
- Check `ck_academic_group_policies_max_group_size_positive`: `max_group_size > 0`.
- Index `academic_group_policies_academic_cycle_id_key`; unique=True; columns/expressions `['academic_cycle_id']`; options `{'postgresql_include': []}`.

## Table: academic_rule_versions
Model source: `backend/app/models/template_reference.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".academic_rule_versions_id_seq'::regclass) |
| template_reference_version_id | INTEGER | No | — |
| version_number | INTEGER | No | — |
| provenance | VARCHAR(32) | No | — |
| rules | JSONB | No | — |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `template_reference_version_id` → `template_reference_versions(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_academic_rule_version`: `template_reference_version_id, version_number`.
- Index `uq_academic_rule_version`; unique=True; columns/expressions `['template_reference_version_id', 'version_number']`; options `{'postgresql_include': []}`.

## Table: admin_audit_events
Model source: `backend/app/models/audit_event.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".admin_audit_events_id_seq'::regclass) |
| actor_id | INTEGER | No | — |
| affected_user_id | INTEGER | Yes | — |
| action | VARCHAR(64) | No | — |
| changed_values | JSONB | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| target_type | VARCHAR(32) | No | 'USER'::character varying |
| target_id | INTEGER | No | — |
- Foreign key `actor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `affected_user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_admin_audit_events_affected_user_id`; unique=False; columns/expressions `['affected_user_id']`; options `{'postgresql_include': []}`.
- Index `ix_admin_audit_events_created_at`; unique=False; columns/expressions `['created_at']`; options `{'postgresql_include': []}`.

## Table: alembic_version
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: version_num.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| version_num | VARCHAR(32) | No | — |

## Table: archive_import_batches
Model source: `backend/app/models/archive_import_batch.py`.
Primary key: batch_id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| batch_id | VARCHAR(64) | No | — |
| original_file_name | VARCHAR(255) | No | — |
| uploaded_by_id | INTEGER | No | — |
| uploaded_at | TIMESTAMP WITH TIME ZONE | No | now() |
| total_rows | INTEGER | No | 0 |
| inserted_rows | INTEGER | No | 0 |
| skipped_rows | INTEGER | No | 0 |
| invalid_rows | INTEGER | No | 0 |
| import_status | VARCHAR(32) | No | 'PROCESSING'::character varying |
- Foreign key `uploaded_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.

## Table: archived_project_documents
Model source: `backend/app/models/archived_project.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".archived_project_documents_id_seq'::regclass) |
| archived_project_id | INTEGER | No | — |
| document_type | VARCHAR(32) | No | — |
| display_name | VARCHAR(255) | No | — |
| storage_key | VARCHAR(512) | No | — |
| file_hash | VARCHAR(64) | No | — |
| mime_type | VARCHAR(100) | No | — |
| file_size | INTEGER | No | — |
| content | BYTEA | No | — |
| version | INTEGER | No | — |
| uploaded_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| is_active | BOOLEAN | No | true |
- Foreign key `archived_project_id` → `archived_projects(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `uploaded_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_archived_project_documents_project_type`; unique=False; columns/expressions `['archived_project_id', 'document_type', 'version']`; options `{'postgresql_include': []}`.
- Index `uq_archived_project_active_document_type`; unique=True; columns/expressions `['archived_project_id', 'document_type']`; options `{'postgresql_where': '(is_active = true)', 'postgresql_include': []}`.

## Table: archived_projects
Model source: `backend/app/models/archived_project.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".archived_projects_id_seq'::regclass) |
| title | VARCHAR(255) | No | — |
| normalized_title | VARCHAR(255) | No | — |
| abstract_summary | TEXT | No | — |
| keywords | VARCHAR(100)[] | No | '{}'::character varying[] |
| academic_cycle_id | INTEGER | Yes | — |
| academic_year | VARCHAR(64) | No | — |
| department_program | VARCHAR(255) | No | — |
| project_scope | VARCHAR(255) | No | — |
| completion_stage | VARCHAR(100) | No | — |
| implemented_scope | TEXT | No | — |
| remaining_gaps | TEXT | No | — |
| future_work | TEXT | No | — |
| supervisor_display_reference | VARCHAR(255) | Yes | — |
| source_label | VARCHAR(64) | No | — |
| source_metadata | JSONB | No | '{}'::jsonb |
| is_active | BOOLEAN | No | true |
| archived_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| project_code | VARCHAR(120) | Yes | — |
| group_leader_name | VARCHAR(255) | Yes | — |
| group_leader_registration_number | VARCHAR(120) | Yes | — |
| group_members | JSONB | No | — |
| supervisor_name | VARCHAR(255) | Yes | — |
| session_name | VARCHAR(16) | Yes | — |
| problem_statement | TEXT | Yes | — |
| objectives | TEXT | Yes | — |
| methodology | TEXT | Yes | — |
| technologies_used | TEXT | Yes | — |
| main_features | TEXT | Yes | — |
| project_status | VARCHAR(100) | Yes | — |
| completion_percentage | INTEGER | Yes | — |
| outcomes_results | TEXT | Yes | — |
| repository_url | VARCHAR(1000) | Yes | — |
| report_url | VARCHAR(1000) | Yes | — |
| presentation_url | VARCHAR(1000) | Yes | — |
| external_reference | VARCHAR(1000) | Yes | — |
| notes | TEXT | Yes | — |
| is_visible_to_students | BOOLEAN | No | true |
| normalized_group_name | VARCHAR(255) | No | — |
| group_name | VARCHAR(255) | Yes | — |
| source_batch_id | VARCHAR(64) | Yes | — |
| source_row_number | INTEGER | Yes | — |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_archived_projects_active_cycle`; unique=False; columns/expressions `['is_active', 'academic_year']`; options `{'postgresql_include': []}`.
- Index `ix_archived_projects_active_scope`; unique=False; columns/expressions `['is_active', 'project_scope']`; options `{'postgresql_include': []}`.
- Index `ix_archived_projects_cycle_code`; unique=False; columns/expressions `['academic_cycle_id', 'project_code']`; options `{'postgresql_include': []}`.
- Index `ix_archived_projects_normalized_title`; unique=False; columns/expressions `['normalized_title']`; options `{'postgresql_include': []}`.
- Index `ix_archived_projects_source_batch_id`; unique=False; columns/expressions `['source_batch_id']`; options `{'postgresql_include': []}`.
- Index `uq_archived_project_active_title_year_group`; unique=True; columns/expressions `['normalized_title', 'academic_year', 'normalized_group_name']`; options `{'postgresql_where': '(is_active = true)', 'postgresql_include': []}`.

## Table: auth_sessions
Model source: `backend/app/models/auth_session.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".auth_sessions_id_seq'::regclass) |
| user_id | INTEGER | No | — |
| token_hash | VARCHAR(64) | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| expires_at | TIMESTAMP WITH TIME ZONE | No | — |
| revoked_at | TIMESTAMP WITH TIME ZONE | Yes | — |
- Foreign key `user_id` → `users(id)`; options: `{'ondelete': 'CASCADE'}`.
- Unique constraint `auth_sessions_token_hash_key`: `token_hash`.
- Index `auth_sessions_token_hash_key`; unique=True; columns/expressions `['token_hash']`; options `{'postgresql_include': []}`.
- Index `ix_auth_sessions_expires_at`; unique=False; columns/expressions `['expires_at']`; options `{'postgresql_include': []}`.
- Index `ix_auth_sessions_user_id`; unique=False; columns/expressions `['user_id']`; options `{'postgresql_include': []}`.

## Table: collaboration_channels
Model source: `backend/app/models/module2_collaboration.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".collaboration_channels_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| supervisor_id | INTEGER | No | — |
| academic_year | INTEGER | No | — |
| session | VARCHAR(16) | No | — |
| assignment_id | INTEGER | No | — |
| status | VARCHAR(16) | No | 'ACTIVE'::character varying |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `assignment_id` → `supervisor_assignments(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `supervisor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_collaboration_channels_supervisor_status`; unique=False; columns/expressions `['supervisor_id', 'status']`; options `{'postgresql_include': []}`.
- Index `uq_collaboration_channel_active_assignment`; unique=True; columns/expressions `['team_id', 'supervisor_id', 'assignment_id']`; options `{'postgresql_where': "((status)::text = 'ACTIVE'::text)", 'postgresql_include': []}`.

## Table: collaboration_messages
Model source: `backend/app/models/module2_collaboration.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".collaboration_messages_id_seq'::regclass) |
| channel_id | INTEGER | No | — |
| sender_user_id | INTEGER | No | — |
| message_text | TEXT | No | — |
| attachment_reference | VARCHAR(500) | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — |
- Foreign key `channel_id` → `collaboration_channels(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `sender_user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_collaboration_messages_channel_created`; unique=False; columns/expressions `['channel_id', 'created_at', 'id']`; options `{'postgresql_include': []}`.

## Table: collaboration_participants
Model source: `backend/app/models/module2_collaboration.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".collaboration_participants_id_seq'::regclass) |
| channel_id | INTEGER | No | — |
| user_id | INTEGER | Yes | — |
| team_member_id | INTEGER | Yes | — |
| participant_role | VARCHAR(24) | No | — |
| joined_at | TIMESTAMP WITH TIME ZONE | No | now() |
| is_active | BOOLEAN | No | true |
- Foreign key `channel_id` → `collaboration_channels(id)`; options: `{'ondelete': 'CASCADE'}`.
- Foreign key `team_member_id` → `team_members(id)`; options: `{'ondelete': 'CASCADE'}`.
- Foreign key `user_id` → `users(id)`; options: `{'ondelete': 'CASCADE'}`.
- Unique constraint `uq_collaboration_participant_user`: `channel_id, user_id`.
- Index `ix_collaboration_participants_channel_active`; unique=False; columns/expressions `['channel_id', 'is_active']`; options `{'postgresql_include': []}`.
- Index `uq_collaboration_participant_user`; unique=True; columns/expressions `['channel_id', 'user_id']`; options `{'postgresql_include': []}`.

## Table: dashboard_requirements
Model source: `backend/app/models/dashboard_requirement.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".dashboard_requirements_id_seq'::regclass) |
| academic_deadline_id | INTEGER | Yes | — |
| academic_cycle_id | INTEGER | No | — |
| title | VARCHAR(200) | No | — |
| description | TEXT | Yes | — |
| requirement_type | VARCHAR(24) | No | — |
| module | VARCHAR(120) | No | — |
| priority | VARCHAR(16) | No | 'MEDIUM'::character varying |
| role_visibility | JSONB | No | '[]'::jsonb |
| assigned_user_id | INTEGER | Yes | — |
| assigned_group_id | INTEGER | Yes | — |
| due_at | TIMESTAMP WITH TIME ZONE | No | — |
| completion_percent | INTEGER | No | 0 |
| status | VARCHAR(20) | No | 'UPCOMING'::character varying |
| is_required | BOOLEAN | No | true |
| completed_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `academic_deadline_id` → `academic_deadlines(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `assigned_group_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `assigned_user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_dashboard_requirements_cycle`; unique=False; columns/expressions `['academic_cycle_id']`; options `{'postgresql_include': []}`.
- Index `ix_dashboard_requirements_status_due`; unique=False; columns/expressions `['status', 'due_at']`; options `{'postgresql_include': []}`.
- Index `ix_dashboard_requirements_user`; unique=False; columns/expressions `['assigned_user_id']`; options `{'postgresql_include': []}`.

## Table: defense_panel_members
Model source: `backend/app/models/project_workflow.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".defense_panel_members_id_seq'::regclass) |
| schedule_id | INTEGER | No | — |
| user_id | INTEGER | No | — |
| assigned_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `assigned_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `schedule_id` → `defense_schedules(id)`; options: `{'ondelete': 'CASCADE'}`.
- Foreign key `user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_defense_panel_member`: `schedule_id, user_id`.
- Index `uq_defense_panel_member`; unique=True; columns/expressions `['schedule_id', 'user_id']`; options `{'postgresql_include': []}`.

## Table: defense_schedules
Model source: `backend/app/models/project_workflow.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".defense_schedules_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| academic_cycle_id | INTEGER | No | — |
| created_by_id | INTEGER | No | — |
| start_at | TIMESTAMP WITH TIME ZONE | No | — |
| end_at | TIMESTAMP WITH TIME ZONE | No | — |
| room | VARCHAR(255) | Yes | — |
| online_link | VARCHAR(1000) | Yes | — |
| status | VARCHAR(16) | No | 'SCHEDULED'::character varying |
| conflict_note | TEXT | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_defense_schedules_status`: `status::text = ANY (ARRAY['SCHEDULED'::character varying, 'RESCHEDULED'::character varying, 'CANCELLED'::character varying]::text[])`.
- Check `ck_defense_schedules_time_order`: `end_at > start_at`.
- Index `ix_defense_schedules_time`; unique=False; columns/expressions `['start_at', 'end_at']`; options `{'postgresql_include': []}`.

## Table: document_submission_versions
Model source: `backend/app/models/document_requirement.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".document_submission_versions_id_seq'::regclass) |
| submission_id | INTEGER | No | — |
| version_number | INTEGER | No | — |
| original_filename | VARCHAR(255) | No | — |
| stored_filename | VARCHAR(255) | No | — |
| mime_type | VARCHAR(120) | No | — |
| file_size | INTEGER | No | — |
| storage_reference | VARCHAR(500) | No | — |
| content | BYTEA | Yes | — |
| uploaded_by_id | INTEGER | No | — |
| uploaded_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `submission_id` → `document_submissions(id)`; options: `{'ondelete': 'CASCADE'}`.
- Foreign key `uploaded_by_id` → `users(id)`; options: `{}`.
- Unique constraint `document_submission_versions_stored_filename_key`: `stored_filename`.
- Unique constraint `uq_document_submission_version`: `submission_id, version_number`.
- Index `document_submission_versions_stored_filename_key`; unique=True; columns/expressions `['stored_filename']`; options `{'postgresql_include': []}`.
- Index `ix_document_versions_submission`; unique=False; columns/expressions `['submission_id']`; options `{'postgresql_include': []}`.
- Index `uq_document_submission_version`; unique=True; columns/expressions `['submission_id', 'version_number']`; options `{'postgresql_include': []}`.

## Table: document_submissions
Model source: `backend/app/models/document_requirement.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".document_submissions_id_seq'::regclass) |
| requirement_id | INTEGER | No | — |
| student_id | INTEGER | No | — |
| status | VARCHAR(20) | No | — |
| is_late | BOOLEAN | No | false |
| review_comment | TEXT | Yes | — |
| reviewed_by_id | INTEGER | Yes | — |
| reviewed_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| uploaded_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| group_id | INTEGER | Yes | — |
| academic_cycle_id | INTEGER | Yes | — |
| uploaded_by_id | INTEGER | Yes | — |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `group_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `requirement_id` → `document_upload_requirements(id)`; options: `{'ondelete': 'CASCADE'}`.
- Foreign key `reviewed_by_id` → `users(id)`; options: `{}`.
- Foreign key `student_id` → `users(id)`; options: `{}`.
- Foreign key `uploaded_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_document_submission_requirement_student`: `requirement_id, student_id`.
- Index `ix_document_submissions_student`; unique=False; columns/expressions `['student_id']`; options `{'postgresql_include': []}`.
- Index `uq_document_submission_requirement_group`; unique=True; columns/expressions `['requirement_id', 'group_id']`; options `{'postgresql_where': '(group_id IS NOT NULL)', 'postgresql_include': []}`.
- Index `uq_document_submission_requirement_student`; unique=True; columns/expressions `['requirement_id', 'student_id']`; options `{'postgresql_include': []}`.

## Table: document_upload_requirements
Model source: `backend/app/models/document_requirement.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".document_upload_requirements_id_seq'::regclass) |
| title | VARCHAR(200) | No | — |
| description | TEXT | Yes | — |
| academic_cycle_id | INTEGER | No | — |
| module | VARCHAR(120) | No | — |
| visible_to_roles | JSONB | No | — |
| assigned_user_id | INTEGER | Yes | — |
| assigned_group_id | INTEGER | Yes | — |
| allowed_file_types | JSONB | No | — |
| max_file_size_mb | INTEGER | No | — |
| due_at | TIMESTAMP WITH TIME ZONE | No | — |
| reminder_days_before | INTEGER | No | — |
| is_required | BOOLEAN | No | true |
| status | VARCHAR(16) | No | 'DRAFT'::character varying |
| late_upload_allowed | BOOLEAN | No | false |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{}`.
- Foreign key `assigned_group_id` → `teams(id)`; options: `{}`.
- Foreign key `assigned_user_id` → `users(id)`; options: `{}`.
- Foreign key `created_by_id` → `users(id)`; options: `{}`.
- Index `ix_document_requirements_assigned_user`; unique=False; columns/expressions `['assigned_user_id']`; options `{'postgresql_include': []}`.
- Index `ix_document_requirements_status_due`; unique=False; columns/expressions `['status', 'due_at']`; options `{'postgresql_include': []}`.

## Table: evaluation_aggregation_configs
Model source: `backend/app/models/evaluation.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".evaluation_aggregation_configs_id_seq'::regclass) |
| evaluation_category | VARCHAR(32) | No | — |
| method | VARCHAR(16) | No | 'AVERAGE'::character varying |
| is_active | BOOLEAN | No | true |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_evaluation_aggregation_category`: `evaluation_category`.
- Check `ck_evaluation_aggregation_category`: `evaluation_category::text = ANY (ARRAY['FINAL_PRESENTATION'::character varying, 'MID_REVIEW'::character varying]::text[])`.
- Check `ck_evaluation_aggregation_method`: `method::text = ANY (ARRAY['AVERAGE'::character varying, 'MAXIMUM'::character varying, 'MEDIAN'::character varying]::text[])`.
- Index `uq_evaluation_aggregation_category`; unique=True; columns/expressions `['evaluation_category']`; options `{'postgresql_include': []}`.

## Table: evaluation_audit_events
Model source: `backend/app/models/evaluation.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".evaluation_audit_events_id_seq'::regclass) |
| evaluation_id | INTEGER | No | — |
| actor_id | INTEGER | No | — |
| action | VARCHAR(48) | No | — |
| previous_marks | INTEGER | Yes | — |
| new_marks | INTEGER | Yes | — |
| reason | TEXT | Yes | — |
| changed_values | JSONB | No | '{}'::jsonb |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `actor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `evaluation_id` → `evaluation_records(id)`; options: `{'ondelete': 'CASCADE'}`.
- Index `ix_evaluation_audit_record_created`; unique=False; columns/expressions `['evaluation_id', 'created_at']`; options `{'postgresql_include': []}`.

## Table: evaluation_corrections
Model source: `backend/app/models/evaluation.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".evaluation_corrections_id_seq'::regclass) |
| evaluation_id | INTEGER | No | — |
| authorized_by_id | INTEGER | No | — |
| previous_marks | INTEGER | No | — |
| new_marks | INTEGER | No | — |
| reason | TEXT | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `authorized_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `evaluation_id` → `evaluation_records(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_evaluation_corrections_evaluation`; unique=False; columns/expressions `['evaluation_id', 'created_at']`; options `{'postgresql_include': []}`.

## Table: evaluation_records
Model source: `backend/app/models/evaluation.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".evaluation_records_id_seq'::regclass) |
| student_id | INTEGER | Yes | — |
| group_id | INTEGER | Yes | — |
| evaluator_id | INTEGER | No | — |
| evaluator_role | VARCHAR(32) | No | — |
| evaluation_category | VARCHAR(32) | No | — |
| maximum_marks | INTEGER | No | — |
| obtained_marks | INTEGER | Yes | — |
| feedback | TEXT | Yes | — |
| status | VARCHAR(16) | No | 'DRAFT'::character varying |
| returned_reason | TEXT | Yes | — |
| submitted_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| approved_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| published_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `evaluator_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `group_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `student_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_evaluation_group_category_evaluator`: `group_id, evaluation_category, evaluator_id`.
- Unique constraint `uq_evaluation_student_category_evaluator`: `student_id, evaluation_category, evaluator_id`.
- Check `ck_evaluation_category`: `evaluation_category::text = ANY (ARRAY['FINAL_PRESENTATION'::character varying, 'MID_REVIEW'::character varying, 'SUPERVISOR_EVALUATION'::character varying, 'PROJECT_DOCUMENTATION'::character varying, 'PROPOSAL'::character varying]::text[])`.
- Check `ck_evaluation_marks_range`: `obtained_marks IS NULL OR obtained_marks >= 0 AND obtained_marks <= maximum_marks`.
- Check `ck_evaluation_maximum`: `maximum_marks = ANY (ARRAY[30, 10, 20])`.
- Check `ck_evaluation_one_target`: `student_id IS NOT NULL AND group_id IS NULL OR student_id IS NULL AND group_id IS NOT NULL`.
- Check `ck_evaluation_status`: `status::text = ANY (ARRAY['DRAFT'::character varying, 'SUBMITTED'::character varying, 'RETURNED'::character varying, 'APPROVED'::character varying, 'PUBLISHED'::character varying]::text[])`.
- Index `ix_evaluation_records_category_status`; unique=False; columns/expressions `['evaluation_category', 'status']`; options `{'postgresql_include': []}`.
- Index `ix_evaluation_records_evaluator`; unique=False; columns/expressions `['evaluator_id', 'status']`; options `{'postgresql_include': []}`.
- Index `ix_evaluation_records_group`; unique=False; columns/expressions `['group_id']`; options `{'postgresql_include': []}`.
- Index `ix_evaluation_records_student`; unique=False; columns/expressions `['student_id']`; options `{'postgresql_include': []}`.
- Index `uq_evaluation_group_category_evaluator`; unique=True; columns/expressions `['group_id', 'evaluation_category', 'evaluator_id']`; options `{'postgresql_include': []}`.
- Index `uq_evaluation_student_category_evaluator`; unique=True; columns/expressions `['student_id', 'evaluation_category', 'evaluator_id']`; options `{'postgresql_include': []}`.

## Table: evaluation_rubric_criteria
Model source: `backend/app/models/evaluation_rubric.py`.
Primary key: id.
Column-name drift: model-only []; database-only ['max_score', 'weight'].
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".evaluation_rubric_criteria_id_seq'::regclass) |
| rubric_version_id | INTEGER | No | — |
| name | VARCHAR(160) | No | — |
| description | TEXT | Yes | — |
| display_order | INTEGER | No | — |
| max_score | INTEGER | No | 10 |
| weight | DOUBLE PRECISION | No | '1'::double precision |
- Foreign key `rubric_version_id` → `evaluation_rubric_versions(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_evaluation_rubric_criterion_order`: `rubric_version_id, display_order`.
- Check `ck_rubric_criterion_max_score`: `max_score >= 1 AND max_score <= 1000`.
- Check `ck_rubric_criterion_weight`: `weight > 0::double precision AND weight <= 100::double precision`.
- Index `uq_evaluation_rubric_criterion_order`; unique=True; columns/expressions `['rubric_version_id', 'display_order']`; options `{'postgresql_include': []}`.

## Table: evaluation_rubric_versions
Model source: `backend/app/models/evaluation_rubric.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".evaluation_rubric_versions_id_seq'::regclass) |
| rubric_id | INTEGER | No | — |
| version_number | INTEGER | No | — |
| name | VARCHAR(160) | No | — |
| description | TEXT | Yes | — |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `rubric_id` → `evaluation_rubrics(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_evaluation_rubric_version`: `rubric_id, version_number`.
- Index `uq_evaluation_rubric_version`; unique=True; columns/expressions `['rubric_id', 'version_number']`; options `{'postgresql_include': []}`.

## Table: evaluation_rubrics
Model source: `backend/app/models/evaluation_rubric.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".evaluation_rubrics_id_seq'::regclass) |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |

## Table: group_messages
Model source: `backend/app/models/group_message.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".group_messages_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| channel | VARCHAR(32) | No | — |
| author_id | INTEGER | No | — |
| author_kind | VARCHAR(16) | No | — |
| body | TEXT | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| thread_root_id | INTEGER | Yes | — |
| mentions | JSONB | No | '[]'::jsonb |
| attachment_name | VARCHAR(255) | Yes | — |
| attachment_url | VARCHAR(500) | Yes | — |
- Foreign key `author_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_group_messages_team_channel_id`; unique=False; columns/expressions `['team_id', 'channel', 'id']`; options `{'postgresql_include': []}`.

## Table: m03_ai_runs
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_ai_runs_id_seq'::regclass) |
| proposal_id | VARCHAR(128) | No | — |
| report_id | VARCHAR(128) | Yes | — |
| check_name | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | — |
| runtime | VARCHAR(128) | No | — |
| model | VARCHAR(128) | Yes | — |
| result | JSONB | No | '{}'::jsonb |
| error_message | TEXT | Yes | — |
| started_at | TIMESTAMP WITH TIME ZONE | No | now() |
| finished_at | TIMESTAMP WITH TIME ZONE | Yes | — |
- Index `ix_m03_ai_runs_proposal`; unique=False; columns/expressions `['proposal_id']`; options `{'postgresql_include': []}`.

## Table: m03_compliance_findings
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_compliance_findings_id_seq'::regclass) |
| report_id | VARCHAR(128) | No | — |
| check_name | VARCHAR(64) | No | — |
| severity | VARCHAR(16) | No | — |
| rule_reference | VARCHAR(255) | No | — |
| student_value | JSONB | No | '{}'::jsonb |
| baseline_value | JSONB | No | '{}'::jsonb |
| evidence | JSONB | No | '{}'::jsonb |
| remediation | TEXT | No | — |
| confidence | VARCHAR(24) | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Index `ix_m03_findings_report`; unique=False; columns/expressions `['report_id']`; options `{'postgresql_include': []}`.

## Table: m03_compliance_reports
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_compliance_reports_id_seq'::regclass) |
| report_id | VARCHAR(128) | No | — |
| proposal_id | VARCHAR(128) | No | — |
| proposal_document_id | VARCHAR(128) | No | — |
| baseline_template_id | VARCHAR(128) | No | — |
| proposal_type | VARCHAR(16) | No | — |
| report_version | INTEGER | No | — |
| status | VARCHAR(32) | No | — |
| check_1 | JSONB | No | '{}'::jsonb |
| check_2 | JSONB | No | '{}'::jsonb |
| check_3 | JSONB | No | '{}'::jsonb |
| severity_counts | JSONB | No | '{}'::jsonb |
| remediation | JSONB | No | '[]'::jsonb |
| advisory_summary | TEXT | No | — |
| runtime_metadata | JSONB | No | '{}'::jsonb |
| generated_by_user_id | VARCHAR(128) | No | — |
| generated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Unique constraint `m03_compliance_reports_report_id_key`: `report_id`.
- Unique constraint `uq_m03_report_proposal_version`: `proposal_id, report_version`.
- Index `ix_m03_compliance_reports_proposal`; unique=False; columns/expressions `['proposal_id', 'report_version']`; options `{'postgresql_include': []}`.
- Index `m03_compliance_reports_report_id_key`; unique=True; columns/expressions `['report_id']`; options `{'postgresql_include': []}`.
- Index `uq_m03_report_proposal_version`; unique=True; columns/expressions `['proposal_id', 'report_version']`; options `{'postgresql_include': []}`.

## Table: m03_proposal_access
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_proposal_access_id_seq'::regclass) |
| proposal_id | VARCHAR(128) | No | — |
| user_id | INTEGER | No | — |
| granted_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Unique constraint `uq_m03_proposal_access_user`: `proposal_id, user_id`.
- Index `ix_m03_proposal_access_proposal_id`; unique=False; columns/expressions `['proposal_id']`; options `{'postgresql_include': []}`.
- Index `ix_m03_proposal_access_user_id`; unique=False; columns/expressions `['user_id']`; options `{'postgresql_include': []}`.
- Index `uq_m03_proposal_access_user`; unique=True; columns/expressions `['proposal_id', 'user_id']`; options `{'postgresql_include': []}`.

## Table: m03_proposal_change_summaries
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_proposal_change_summaries_id_seq'::regclass) |
| document_id | INTEGER | No | — |
| status | VARCHAR(24) | No | — |
| summary | TEXT | No | — |
| runtime_metadata | JSONB | No | — |
- Unique constraint `uq_m03_change_summary_document`: `document_id`.
- Index `uq_m03_change_summary_document`; unique=True; columns/expressions `['document_id']`; options `{'postgresql_include': []}`.

## Table: m03_proposal_documents
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_proposal_documents_id_seq'::regclass) |
| proposal_id | VARCHAR(128) | No | — |
| proposal_type | VARCHAR(16) | No | — |
| owner_user_id | VARCHAR(128) | No | — |
| team_id | VARCHAR(128) | Yes | — |
| filename | VARCHAR(255) | No | — |
| storage_key | VARCHAR(512) | No | — |
| sha256 | VARCHAR(64) | No | — |
| mime_type | VARCHAR(100) | No | — |
| file_size | INTEGER | No | — |
| content | BYTEA | No | — |
| version | INTEGER | No | — |
| extraction_status | VARCHAR(24) | No | — |
| ast | JSONB | No | '{}'::jsonb |
| extraction_warnings | JSONB | No | '[]'::jsonb |
| is_active | BOOLEAN | No | true |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Unique constraint `uq_m03_proposal_document_version`: `proposal_id, version`.
- Index `ix_m03_proposal_documents_owner`; unique=False; columns/expressions `['owner_user_id', 'is_active']`; options `{'postgresql_include': []}`.
- Index `uq_m03_proposal_document_version`; unique=True; columns/expressions `['proposal_id', 'version']`; options `{'postgresql_include': []}`.

## Table: m03_proposal_records
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | VARCHAR(128) | No | — |
| owner_user_id | VARCHAR(128) | No | — |
| proposal_type | VARCHAR(16) | No | — |
| title | VARCHAR(255) | No | — |
| status | VARCHAR(24) | No | 'DRAFT'::character varying |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Index `ix_m03_proposal_records_owner_user_id`; unique=False; columns/expressions `['owner_user_id']`; options `{'postgresql_include': []}`.

## Table: m03_proposal_submissions
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_proposal_submissions_id_seq'::regclass) |
| proposal_id | VARCHAR(128) | No | — |
| document_id | INTEGER | No | — |
| version | INTEGER | No | — |
| action | VARCHAR(24) | No | — |
| actor_id | VARCHAR(128) | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Unique constraint `uq_m03_submission_document`: `proposal_id, document_id`.
- Index `ix_m03_proposal_submissions_proposal_id`; unique=False; columns/expressions `['proposal_id']`; options `{'postgresql_include': []}`.
- Index `uq_m03_submission_document`; unique=True; columns/expressions `['proposal_id', 'document_id']`; options `{'postgresql_include': []}`.

## Table: m03_reference_templates
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_reference_templates_id_seq'::regclass) |
| template_type | VARCHAR(16) | No | — |
| filename | VARCHAR(255) | No | — |
| storage_key | VARCHAR(512) | No | — |
| sha256 | VARCHAR(64) | No | — |
| mime_type | VARCHAR(100) | No | — |
| file_size | INTEGER | No | — |
| content | BYTEA | No | — |
| version | INTEGER | No | — |
| extraction_status | VARCHAR(24) | No | — |
| extracted_rules | JSONB | No | '{}'::jsonb |
| extraction_warnings | JSONB | No | '[]'::jsonb |
| confidence | VARCHAR(24) | Yes | — |
| is_active | BOOLEAN | No | false |
| uploaded_by_user_id | VARCHAR(128) | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| activated_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| version_kind | VARCHAR(24) | No | 'REFERENCE'::character varying |
| parent_template_id | INTEGER | Yes | — |
| template_metadata | JSONB | No | '{}'::jsonb |
| provenance | VARCHAR(64) | No | 'Observed reference property'::character varying |
| activation_mode | VARCHAR(16) | Yes | — |
- Unique constraint `uq_m03_reference_template_type_version`: `template_type, version`.
- Index `ix_m03_reference_templates_active_type`; unique=False; columns/expressions `['template_type', 'is_active']`; options `{'postgresql_include': []}`.
- Index `ix_m03_reference_templates_parent`; unique=False; columns/expressions `['parent_template_id']`; options `{'postgresql_include': []}`.
- Index `uq_m03_reference_template_type_version`; unique=True; columns/expressions `['template_type', 'version']`; options `{'postgresql_include': []}`.

## Table: m03_template_rule_sets
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".m03_template_rule_sets_id_seq'::regclass) |
| reference_template_id | INTEGER | No | — |
| rule_key | VARCHAR(128) | No | — |
| rule_value | JSONB | No | '{}'::jsonb |
| source | VARCHAR(255) | No | — |
| confidence | VARCHAR(24) | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| rule_version | INTEGER | No | 1 |
| content_hash | VARCHAR(64) | No | ''::character varying |
| provenance | VARCHAR(64) | No | 'Observed reference property'::character varying |
- Unique constraint `uq_m03_template_rule_version_key`: `reference_template_id, rule_version, rule_key`.
- Index `ix_m03_template_rule_sets_template`; unique=False; columns/expressions `['reference_template_id']`; options `{'postgresql_include': []}`.
- Index `ix_m03_template_rule_sets_version`; unique=False; columns/expressions `['reference_template_id', 'rule_version']`; options `{'postgresql_include': []}`.
- Index `uq_m03_template_rule_version_key`; unique=True; columns/expressions `['reference_template_id', 'rule_version', 'rule_key']`; options `{'postgresql_include': []}`.

## Table: module2_channel_reads
Model source: `backend/app/models/module2_collaboration.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".module2_channel_reads_id_seq'::regclass) |
| user_id | INTEGER | No | — |
| team_id | INTEGER | No | — |
| channel | VARCHAR(32) | No | — |
| last_read_message_id | INTEGER | Yes | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'CASCADE'}`.
- Foreign key `user_id` → `users(id)`; options: `{'ondelete': 'CASCADE'}`.
- Unique constraint `uq_module2_channel_read`: `user_id, team_id, channel`.
- Index `uq_module2_channel_read`; unique=True; columns/expressions `['user_id', 'team_id', 'channel']`; options `{'postgresql_include': []}`.

## Table: module2_chatbot_sessions
Model source: `backend/app/models/module2_collaboration.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".module2_chatbot_sessions_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| user_id | INTEGER | No | — |
| title | VARCHAR(200) | No | 'Group assistant'::character varying |
| context | JSON | No | '{}'::json |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'CASCADE'}`.
- Foreign key `user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_module2_chatbot_sessions_team_created`; unique=False; columns/expressions `['team_id', 'created_at']`; options `{'postgresql_include': []}`.

## Table: module2_notifications
Model source: `backend/app/models/module2_collaboration.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".module2_notifications_id_seq'::regclass) |
| recipient_user_id | INTEGER | No | — |
| kind | VARCHAR(64) | No | — |
| payload | JSON | No | '{}'::json |
| read_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `recipient_user_id` → `users(id)`; options: `{'ondelete': 'CASCADE'}`.
- Index `ix_module2_notifications_recipient_created`; unique=False; columns/expressions `['recipient_user_id', 'created_at']`; options `{'postgresql_include': []}`.

## Table: panel_evaluation_scores
Model source: `backend/app/models/project_workflow.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".panel_evaluation_scores_id_seq'::regclass) |
| evaluation_id | INTEGER | No | — |
| criterion_key | VARCHAR(160) | No | — |
| score | INTEGER | No | — |
| max_score | INTEGER | No | — |
| feedback | TEXT | Yes | — |
- Foreign key `evaluation_id` → `panel_evaluations(id)`; options: `{'ondelete': 'CASCADE'}`.
- Unique constraint `uq_panel_evaluation_score_criterion`: `evaluation_id, criterion_key`.
- Check `ck_panel_evaluation_scores_range`: `score >= 0 AND max_score > 0 AND score <= max_score`.
- Index `uq_panel_evaluation_score_criterion`; unique=True; columns/expressions `['evaluation_id', 'criterion_key']`; options `{'postgresql_include': []}`.

## Table: panel_evaluations
Model source: `backend/app/models/project_workflow.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".panel_evaluations_id_seq'::regclass) |
| schedule_id | INTEGER | No | — |
| evaluator_id | INTEGER | No | — |
| status | VARCHAR(24) | No | 'DRAFT'::character varying |
| overall_score | INTEGER | Yes | — |
| overall_feedback | TEXT | Yes | — |
| decision | VARCHAR(64) | Yes | — |
| disagreement_detected | BOOLEAN | No | false |
| resolution_note | TEXT | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `evaluator_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `schedule_id` → `defense_schedules(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_panel_evaluation_schedule_evaluator`: `schedule_id, evaluator_id`.
- Check `ck_panel_evaluations_score`: `overall_score IS NULL OR overall_score >= 0 AND overall_score <= 100`.
- Check `ck_panel_evaluations_status`: `status::text = ANY (ARRAY['DRAFT'::character varying, 'SUBMITTED'::character varying, 'RECHECK_REQUESTED'::character varying, 'RESOLVED'::character varying]::text[])`.
- Index `uq_panel_evaluation_schedule_evaluator`; unique=True; columns/expressions `['schedule_id', 'evaluator_id']`; options `{'postgresql_include': []}`.

## Table: password_reset_tokens
Model source: `backend/app/models/password_reset_token.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".password_reset_tokens_id_seq'::regclass) |
| user_id | INTEGER | No | — |
| token_hash | VARCHAR(64) | No | — |
| expires_at | TIMESTAMP WITH TIME ZONE | No | — |
| used_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| requested_ip | VARCHAR(64) | Yes | — |
- Foreign key `user_id` → `users(id)`; options: `{'ondelete': 'CASCADE'}`.
- Unique constraint `uq_password_reset_tokens_token_hash`: `token_hash`.
- Index `ix_password_reset_tokens_expires_at`; unique=False; columns/expressions `['expires_at']`; options `{'postgresql_include': []}`.
- Index `ix_password_reset_tokens_user_id`; unique=False; columns/expressions `['user_id']`; options `{'postgresql_include': []}`.
- Index `uq_password_reset_tokens_token_hash`; unique=True; columns/expressions `['token_hash']`; options `{'postgresql_include': []}`.

## Table: project_milestones
Model source: `backend/app/models/project_workflow.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".project_milestones_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| created_by_id | INTEGER | No | — |
| title | VARCHAR(255) | No | — |
| description | TEXT | Yes | — |
| due_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| completion_percent | INTEGER | No | 0 |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_project_milestones_completion`: `completion_percent >= 0 AND completion_percent <= 100`.
- Index `ix_project_milestones_team_due`; unique=False; columns/expressions `['team_id', 'due_at']`; options `{'postgresql_include': []}`.

## Table: project_tasks
Model source: `backend/app/models/project_workflow.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".project_tasks_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| milestone_id | INTEGER | Yes | — |
| owner_user_id | INTEGER | Yes | — |
| created_by_id | INTEGER | No | — |
| title | VARCHAR(255) | No | — |
| description | TEXT | Yes | — |
| due_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| completion_percent | INTEGER | No | 0 |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `milestone_id` → `project_milestones(id)`; options: `{'ondelete': 'SET NULL'}`.
- Foreign key `owner_user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_project_tasks_completion`: `completion_percent >= 0 AND completion_percent <= 100`.
- Index `ix_project_tasks_team_due`; unique=False; columns/expressions `['team_id', 'due_at']`; options `{'postgresql_include': []}`.

## Table: proposal_ai_review_runs
Model source: `backend/app/models/proposal_ai_review.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".proposal_ai_review_runs_id_seq'::regclass) |
| proposal_id | VARCHAR(128) | No | — |
| status | VARCHAR(32) | No | — |
| runtime | VARCHAR(128) | No | — |
| model | VARCHAR(128) | Yes | — |
| result | JSONB | No | — |
| error_message | TEXT | Yes | — |
| started_at | TIMESTAMP WITH TIME ZONE | No | now() |
| finished_at | TIMESTAMP WITH TIME ZONE | Yes | — |
- Index `ix_proposal_ai_review_runs_proposal`; unique=False; columns/expressions `['proposal_id']`; options `{'postgresql_include': []}`.

## Table: proposal_compliance_reports
Model source: `backend/app/models/proposal_compliance.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".proposal_compliance_reports_id_seq'::regclass) |
| submission_id | INTEGER | No | — |
| status | VARCHAR(32) | No | — |
| score | INTEGER | No | — |
| total_checks | INTEGER | No | — |
| report | JSONB | No | '{}'::jsonb |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `submission_id` → `proposal_compliance_submissions(id)`; options: `{'ondelete': 'CASCADE'}`.
- Unique constraint `uq_proposal_compliance_report_submission`: `submission_id`.
- Index `ix_proposal_compliance_report_created`; unique=False; columns/expressions `['created_at']`; options `{'postgresql_include': []}`.
- Index `uq_proposal_compliance_report_submission`; unique=True; columns/expressions `['submission_id']`; options `{'postgresql_include': []}`.

## Table: proposal_compliance_submissions
Model source: `backend/app/models/proposal_compliance.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".proposal_compliance_submissions_id_seq'::regclass) |
| proposal_key | VARCHAR(64) | No | — |
| owner_user_id | INTEGER | No | — |
| team_id | INTEGER | Yes | — |
| proposal_type | VARCHAR(5) | No | — |
| title | VARCHAR(200) | No | — |
| version | INTEGER | No | 1 |
| status | VARCHAR(32) | No | 'SUBMITTED'::character varying |
| processing_status | VARCHAR(32) | No | 'QUEUED'::character varying |
| filename | VARCHAR(255) | No | — |
| content_type | VARCHAR(100) | No | — |
| file_size | INTEGER | No | — |
| sha256 | VARCHAR(64) | No | — |
| page_count | INTEGER | No | — |
| storage_key | VARCHAR(500) | No | — |
| extracted_text | TEXT | No | — |
| extracted_fields | JSONB | No | '{}'::jsonb |
| template_reference_version_id | INTEGER | Yes | — |
| error_message | TEXT | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `template_reference_version_id` → `template_reference_versions(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `owner_user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_proposal_compliance_submission_version`: `proposal_key, version`.
- Check `ck_proposal_compliance_submission_type`: `proposal_type::text = ANY (ARRAY['SHORT'::character varying, 'LONG'::character varying]::text[])`.
- Check `ck_proposal_compliance_submission_version_positive`: `version > 0`.
- Index `ix_proposal_compliance_submission_key`; unique=False; columns/expressions `['proposal_key', 'version']`; options `{'postgresql_include': []}`.
- Index `ix_proposal_compliance_submission_owner`; unique=False; columns/expressions `['owner_user_id', 'created_at']`; options `{'postgresql_include': []}`.
- Index `uq_proposal_compliance_submission_version`; unique=True; columns/expressions `['proposal_key', 'version']`; options `{'postgresql_include': []}`.

## Table: proposal_reference_documents
Model source: `backend/app/models/proposal_reference.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".proposal_reference_documents_id_seq'::regclass) |
| reference_id | INTEGER | No | — |
| filename | VARCHAR(255) | No | — |
| content_type | VARCHAR(100) | No | — |
| file_size | INTEGER | No | — |
| sha256 | VARCHAR(64) | No | — |
| content | BYTEA | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `reference_id` → `proposal_references(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `uq_proposal_reference_document_reference`; unique=True; columns/expressions `['reference_id']`; options `{'postgresql_include': []}`.

## Table: proposal_references
Model source: `backend/app/models/proposal_reference.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".proposal_references_id_seq'::regclass) |
| title | VARCHAR(255) | No | — |
| normalized_title | VARCHAR(255) | No | — |
| short_summary | TEXT | No | — |
| academic_cycle_id | INTEGER | Yes | — |
| academic_year | VARCHAR(32) | No | — |
| category_scope | VARCHAR(255) | No | — |
| source_label | VARCHAR(64) | No | — |
| source_metadata | JSONB | No | '{}'::jsonb |
| is_active | BOOLEAN | No | true |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_proposal_references_cycle_active`; unique=False; columns/expressions `['academic_cycle_id', 'is_active']`; options `{'postgresql_include': []}`.
- Index `ix_proposal_references_normalized_title`; unique=False; columns/expressions `['normalized_title']`; options `{'postgresql_include': []}`.

## Table: proposal_versions
Model source: `backend/app/models/proposal.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".proposal_versions_id_seq'::regclass) |
| proposal_id | INTEGER | No | — |
| version_number | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `proposal_id` → `proposals(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_proposal_version_number`: `proposal_id, version_number`.
- Check `ck_proposal_version_positive`: `version_number > 0`.
- Index `uq_proposal_version_number`; unique=True; columns/expressions `['proposal_id', 'version_number']`; options `{'postgresql_include': []}`.

## Table: proposals
Model source: `backend/app/models/proposal.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".proposals_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| proposal_type | VARCHAR(5) | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_proposals_type`: `proposal_type::text = ANY (ARRAY['SHORT'::character varying, 'LONG'::character varying]::text[])`.

## Table: reminder_rule_versions
Model source: `backend/app/models/reminder_rule.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".reminder_rule_versions_id_seq'::regclass) |
| rule_id | INTEGER | No | — |
| version_number | INTEGER | No | — |
| deadline_version_id | INTEGER | No | — |
| name | VARCHAR(160) | No | — |
| description | TEXT | Yes | — |
| category | VARCHAR(16) | No | — |
| direction | VARCHAR(6) | No | — |
| elapsed_minutes | INTEGER | No | — |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `deadline_version_id` → `academic_deadline_versions(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `rule_id` → `reminder_rules(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_reminder_rule_version`: `rule_id, version_number`.
- Check `ck_reminder_rule_category`: `category::text = ANY (ARRAY['REMINDER'::character varying, 'ESCALATION'::character varying]::text[])`.
- Check `ck_reminder_rule_direction`: `direction::text = ANY (ARRAY['BEFORE'::character varying, 'AFTER'::character varying]::text[])`.
- Check `ck_reminder_rule_minutes`: `elapsed_minutes > 0`.
- Index `uq_reminder_rule_version`; unique=True; columns/expressions `['rule_id', 'version_number']`; options `{'postgresql_include': []}`.

## Table: reminder_rules
Model source: `backend/app/models/reminder_rule.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".reminder_rules_id_seq'::regclass) |
| academic_cycle_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.

## Table: supervision_agent_runs
Model source: `backend/app/models/agent_supervision.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervision_agent_runs_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| proposal_request_id | INTEGER | Yes | — |
| created_by_id | INTEGER | No | — |
| approved_by_id | INTEGER | Yes | — |
| state | VARCHAR(32) | No | 'IDLE'::character varying |
| approval_status | VARCHAR(24) | No | 'PENDING'::character varying |
| plan | JSONB | No | '{}'::jsonb |
| tool_calls | JSONB | No | '[]'::jsonb |
| result | JSONB | No | '{}'::jsonb |
| error | TEXT | Yes | — |
| approved_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `approved_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `proposal_request_id` → `supervisor_requests(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_supervision_agent_runs_team_created`; unique=False; columns/expressions `['team_id', 'created_at']`; options `{'postgresql_include': []}`.

## Table: supervision_meetings
Model source: `backend/app/models/project_workflow.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervision_meetings_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| supervisor_id | INTEGER | No | — |
| created_by_id | INTEGER | No | — |
| held_at | TIMESTAMP WITH TIME ZONE | No | — |
| minutes | TEXT | No | — |
| decisions | TEXT | Yes | — |
| action_items | JSONB | No | '[]'::jsonb |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `supervisor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id` → `teams(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_supervision_meetings_team_held`; unique=False; columns/expressions `['team_id', 'held_at']`; options `{'postgresql_include': []}`.

## Table: supervisor_assignments
Model source: `backend/app/models/supervisor_assignment.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervisor_assignments_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| academic_cycle_id | INTEGER | No | — |
| supervisor_id | INTEGER | No | — |
| assigned_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| ended_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| ended_by_id | INTEGER | Yes | — |
| academic_year | INTEGER | Yes | — |
| session | VARCHAR(16) | Yes | — |
- Foreign key `assigned_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `ended_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `supervisor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id, academic_cycle_id` → `teams(id, academic_cycle_id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_supervisor_assignments_session_valid`: `session IS NULL OR (session::text = ANY (ARRAY['FALL'::character varying, 'SPRING'::character varying]::text[]))`.
- Check `ck_supervisor_assignments_year_valid`: `academic_year IS NULL OR academic_year >= 1900 AND academic_year <= 2200`.
- Index `ix_supervisor_assignments_supervisor_year_session`; unique=False; columns/expressions `['supervisor_id', 'academic_year', 'session']`; options `{'postgresql_include': []}`.
- Index `uq_supervisor_assignment_active_team`; unique=True; columns/expressions `['team_id']`; options `{'postgresql_where': '(ended_at IS NULL)', 'postgresql_include': []}`.

## Table: supervisor_capacity_policies
Model source: `backend/app/models/academic.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervisor_capacity_policies_id_seq'::regclass) |
| supervisor_id | INTEGER | No | — |
| academic_cycle_id | INTEGER | Yes | — |
| max_group_capacity | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| academic_year | INTEGER | Yes | — |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `supervisor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_supervisor_capacity_policies_supervisor_year`: `supervisor_id, academic_year`.
- Check `ck_supervisor_capacity_policies_capacity_positive`: `max_group_capacity > 0`.
- Check `ck_supervisor_capacity_policies_year_valid`: `academic_year IS NULL OR academic_year >= 1900 AND academic_year <= 2200`.
- Index `uq_supervisor_capacity_policies_supervisor_year`; unique=True; columns/expressions `['supervisor_id', 'academic_year']`; options `{'postgresql_include': []}`.

## Table: supervisor_request_documents
Model source: `backend/app/models/supervisor_request.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervisor_request_documents_id_seq'::regclass) |
| request_id | INTEGER | No | — |
| version | INTEGER | No | — |
| filename | VARCHAR(255) | No | — |
| content_type | VARCHAR(100) | No | — |
| file_size | INTEGER | No | — |
| sha256 | VARCHAR(64) | No | — |
| page_count | INTEGER | No | — |
| content | BYTEA | No | — |
| extracted_text | TEXT | No | — |
| extracted_fields | JSONB | No | — |
| extraction_status | VARCHAR(16) | No | — |
| extraction_runtime | VARCHAR(100) | No | — |
| extracted_at | TIMESTAMP WITH TIME ZONE | No | — |
| confirmed_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| confirmed_by_id | INTEGER | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `confirmed_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `request_id` → `supervisor_requests(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_supervisor_request_documents_extraction_status`: `extraction_status::text = ANY (ARRAY['PENDING'::character varying, 'EXTRACTED'::character varying, 'FAILED'::character varying, 'CONFIRMED'::character varying]::text[])`.
- Check `ck_supervisor_request_documents_file_size_positive`: `file_size > 0`.
- Check `ck_supervisor_request_documents_one_page`: `page_count = 1`.
- Check `ck_supervisor_request_documents_version_positive`: `version > 0`.
- Index `uq_supervisor_request_document_version`; unique=True; columns/expressions `['request_id', 'version']`; options `{'postgresql_include': []}`.

## Table: supervisor_request_messages
Model source: `backend/app/models/supervisor_request_conversation.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervisor_request_messages_id_seq'::regclass) |
| request_id | INTEGER | No | — |
| sender_id | INTEGER | No | — |
| body | TEXT | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `request_id` → `supervisor_requests(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `sender_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Index `ix_supervisor_request_messages_request_id`; unique=False; columns/expressions `['request_id', 'id']`; options `{'postgresql_include': []}`.

## Table: supervisor_request_status_history
Model source: `backend/app/models/supervisor_request.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervisor_request_status_history_id_seq'::regclass) |
| request_id | INTEGER | No | — |
| actor_id | INTEGER | No | — |
| from_status | VARCHAR(32) | Yes | — |
| to_status | VARCHAR(32) | No | — |
| comment | VARCHAR(2000) | Yes | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `actor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `request_id` → `supervisor_requests(id)`; options: `{'ondelete': 'CASCADE'}`.
- Check `ck_supervisor_request_history_to_status`: `to_status::text = ANY (ARRAY['DRAFT'::character varying, 'SUBMITTED'::character varying, 'CHANGES_REQUESTED'::character varying, 'ACCEPTED'::character varying, 'REJECTED'::character varying, 'WITHDRAWN'::character varying]::text[])`.
- Index `ix_supervisor_request_history_request_created`; unique=False; columns/expressions `['request_id', 'created_at']`; options `{'postgresql_include': []}`.

## Table: supervisor_request_submission_note_versions
Model source: `backend/app/models/supervisor_request.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervisor_request_submission_note_versions_id_seq'::regclass) |
| request_id | INTEGER | No | — |
| version | INTEGER | No | — |
| body | TEXT | No | — |
| created_by_id | INTEGER | No | — |
| submitted_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `request_id` → `supervisor_requests(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_supervisor_request_note_body_nonblank`: `body = btrim(body) AND body <> ''::text`.
- Check `ck_supervisor_request_note_version_positive`: `version > 0`.
- Index `ix_supervisor_request_note_request`; unique=False; columns/expressions `['request_id', 'submitted_at']`; options `{'postgresql_include': []}`.
- Index `uq_supervisor_request_note_version`; unique=True; columns/expressions `['request_id', 'version']`; options `{'postgresql_include': []}`.

## Table: supervisor_requests
Model source: `backend/app/models/supervisor_request.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".supervisor_requests_id_seq'::regclass) |
| academic_cycle_id | INTEGER | No | — |
| requester_user_id | INTEGER | No | — |
| team_id | INTEGER | Yes | — |
| supervisor_id | INTEGER | No | — |
| assignment_id | INTEGER | Yes | — |
| title | VARCHAR(200) | Yes | — |
| summary | TEXT | Yes | — |
| status | VARCHAR(32) | No | 'DRAFT'::character varying |
| revision | INTEGER | No | 1 |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| submitted_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| reviewed_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| reviewer_id | INTEGER | Yes | — |
| document_id | INTEGER | Yes | — |
| extraction_status | VARCHAR(16) | No | 'PENDING'::character varying |
| extraction_confirmed_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| extraction_confirmed_by_id | INTEGER | Yes | — |
| submission_note | TEXT | Yes | — |
| proposal_type | VARCHAR(5) | No | 'SHORT'::character varying |
| problem_statement | TEXT | Yes | — |
| objectives | TEXT | Yes | — |
| scope | TEXT | Yes | — |
| methodology | TEXT | Yes | — |
- Foreign key `document_id` → `supervisor_request_documents(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `extraction_confirmed_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `assignment_id` → `supervisor_assignments(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `requester_user_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `reviewer_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `supervisor_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `team_id, academic_cycle_id` → `teams(id, academic_cycle_id)`; options: `{'ondelete': 'RESTRICT'}`.
- Check `ck_supervisor_requests_extraction_status`: `extraction_status::text = ANY (ARRAY['PENDING'::character varying, 'EXTRACTED'::character varying, 'FAILED'::character varying, 'CONFIRMED'::character varying]::text[])`.
- Check `ck_supervisor_requests_revision_positive`: `revision > 0`.
- Check `ck_supervisor_requests_status`: `status::text = ANY (ARRAY['DRAFT'::character varying, 'SUBMITTED'::character varying, 'CHANGES_REQUESTED'::character varying, 'ACCEPTED'::character varying, 'REJECTED'::character varying, 'WITHDRAWN'::character varying]::text[])`.
- Check `ck_supervisor_requests_summary_nonblank`: `summary IS NULL OR summary = btrim(summary) AND summary <> ''::text`.
- Check `ck_supervisor_requests_title_nonblank`: `title IS NULL OR title::text = btrim(title::text) AND title::text <> ''::text`.
- Index `ix_supervisor_requests_cycle_status`; unique=False; columns/expressions `['academic_cycle_id', 'status']`; options `{'postgresql_include': []}`.
- Index `ix_supervisor_requests_extraction_status`; unique=False; columns/expressions `['extraction_status']`; options `{'postgresql_include': []}`.
- Index `ix_supervisor_requests_supervisor_status`; unique=False; columns/expressions `['supervisor_id', 'status']`; options `{'postgresql_include': []}`.
- Index `uq_supervisor_requests_active_owner_supervisor`; unique=True; columns/expressions `['academic_cycle_id', 'requester_user_id', 'supervisor_id']`; options `{'postgresql_where': "((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'SUBMITTED'::character varying, 'CHANGES_REQUESTED'::character varying, 'ACCEPTED'::character varying])::text[]))", 'postgresql_include': []}`.

## Table: team_member_verifications
Model source: No current ORM class; migration/legacy infrastructure table.
Primary key: member_id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| member_id | INTEGER | No | nextval('"public".team_member_verifications_member_id_seq'::regclass) |
| code_hash | VARCHAR(255) | Yes | — |
| expires_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| sent_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| verified_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| attempts | INTEGER | No | 0 |
| window_started_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| requests | INTEGER | No | 0 |

## Table: team_members
Model source: `backend/app/models/team.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".team_members_id_seq'::regclass) |
| team_id | INTEGER | No | — |
| academic_cycle_id | INTEGER | No | — |
| full_name | VARCHAR(255) | No | — |
| registration_number | VARCHAR(100) | No | — |
| university_email | VARCHAR(320) | No | — |
| is_creator | BOOLEAN | No | false |
| is_active | BOOLEAN | No | true |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Foreign key `team_id, academic_cycle_id` → `teams(id, academic_cycle_id)`; options: `{}`.
- Unique constraint `uq_team_members_registration`: `team_id, registration_number`.
- Check `ck_team_members_email`: `university_email::text = lower(btrim(university_email::text)) AND university_email::text <> ''::text`.
- Check `ck_team_members_name`: `full_name::text = btrim(full_name::text) AND full_name::text <> ''::text`.
- Check `ck_team_members_registration`: `registration_number::text = upper(btrim(registration_number::text)) AND registration_number::text <> ''::text`.
- Index `uq_active_cycle_contact_email`; unique=True; columns/expressions `['academic_cycle_id', None]`; options `{'postgresql_where': 'is_active', 'postgresql_include': []}`.
- Index `uq_active_cycle_registration`; unique=True; columns/expressions `['academic_cycle_id', None]`; options `{'postgresql_where': 'is_active', 'postgresql_include': []}`.
- Index `uq_team_creator`; unique=True; columns/expressions `['team_id']`; options `{'postgresql_where': 'is_creator', 'postgresql_include': []}`.
- Index `uq_team_members_registration`; unique=True; columns/expressions `['team_id', 'registration_number']`; options `{'postgresql_include': []}`.

## Table: teams
Model source: `backend/app/models/team.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".teams_id_seq'::regclass) |
| academic_cycle_id | INTEGER | No | — |
| shared_user_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
| status | VARCHAR(16) | No | 'forming'::character varying |
| locked_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| lock_reason | VARCHAR(64) | Yes | — |
- Foreign key `academic_cycle_id` → `academic_cycles(id)`; options: `{}`.
- Foreign key `shared_user_id` → `users(id)`; options: `{}`.
- Unique constraint `teams_shared_user_id_key`: `shared_user_id`.
- Unique constraint `uq_teams_id_cycle`: `id, academic_cycle_id`.
- Index `teams_shared_user_id_key`; unique=True; columns/expressions `['shared_user_id']`; options `{'postgresql_include': []}`.
- Index `uq_teams_id_cycle`; unique=True; columns/expressions `['id', 'academic_cycle_id']`; options `{'postgresql_include': []}`.

## Table: template_reference_versions
Model source: `backend/app/models/template_reference.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".template_reference_versions_id_seq'::regclass) |
| template_reference_id | INTEGER | No | — |
| version_number | INTEGER | No | — |
| title | VARCHAR(160) | No | — |
| provenance | VARCHAR(32) | No | — |
| source_note | VARCHAR(500) | No | — |
| created_by_id | INTEGER | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| is_active | BOOLEAN | No | false |
| activated_at | TIMESTAMP WITH TIME ZONE | Yes | — |
| activated_by_id | INTEGER | Yes | — |
- Foreign key `activated_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `created_by_id` → `users(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Foreign key `template_reference_id` → `template_references(id)`; options: `{'ondelete': 'RESTRICT'}`.
- Unique constraint `uq_template_reference_version`: `template_reference_id, version_number`.
- Index `uq_template_reference_version`; unique=True; columns/expressions `['template_reference_id', 'version_number']`; options `{'postgresql_include': []}`.

## Table: template_references
Model source: `backend/app/models/template_reference.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".template_references_id_seq'::regclass) |
| template_type | template_type | No | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Unique constraint `template_references_template_type_key`: `template_type`.
- Index `template_references_template_type_key`; unique=True; columns/expressions `['template_type']`; options `{'postgresql_include': []}`.

## Table: users
Model source: `backend/app/models/user.py`.
Primary key: id.
| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | nextval('"public".users_id_seq'::regclass) |
| full_name | VARCHAR(255) | No | — |
| email | VARCHAR(320) | No | — |
| registration_number | VARCHAR(100) | Yes | — |
| password_hash | VARCHAR(255) | No | — |
| role | user_role | No | — |
| is_active | BOOLEAN | No | true |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() |
- Unique constraint `users_registration_number_key`: `registration_number`.
- Check `ck_users_email_normalized`: `email::text = lower(btrim(email::text)) AND email::text <> ''::text`.
- Check `ck_users_registration_number_normalized`: `registration_number IS NULL OR registration_number::text = upper(btrim(registration_number::text)) AND registration_number::text <> ''::text`.
- Check `ck_users_student_registration_required`: `role <> 'STUDENT'::user_role OR registration_number IS NOT NULL`.
- Index `uq_users_email_normalized`; unique=True; columns/expressions `[None]`; options `{'postgresql_include': []}`.
- Index `users_registration_number_key`; unique=True; columns/expressions `['registration_number']`; options `{'postgresql_include': []}`.

# Appendix C — Complete registered backend API map
Routes come from the running FastAPI application. Guards show dependency-based checks; ownership, state and transaction checks also occur inside handlers and helpers. A route with no listed guard may be public or perform authorization internally. Use the source reference to explain it. Browser page URLs and these API URLs are different layers.

## /usr/local/lib/python3.12/site-packages/fastapi/applications.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET, HEAD | `/openapi.json` | `openapi` line 1145 | See handler |
| GET, HEAD | `/docs` | `swagger_ui_html` line 1160 | See handler |
| GET, HEAD | `/docs/oauth2-redirect` | `swagger_ui_redirect` line 1178 | See handler |
| GET, HEAD | `/redoc` | `redoc_html` line 1188 | See handler |
- `GET,HEAD /openapi.json`: body `None`; response `None`; query parameters `[]`. 
- `GET,HEAD /docs`: body `None`; response `None`; query parameters `[]`. 
- `GET,HEAD /docs/oauth2-redirect`: body `None`; response `None`; query parameters `[]`. 
- `GET,HEAD /redoc`: body `None`; response `None`; query parameters `[]`. 

## backend/app/academic_cycle_overview.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/academic-cycles/{cycle_id}/overview` | `cycle_overview` line 37 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
- `GET /api/v1/academic-cycles/{cycle_id}/overview`: body `None`; response `<class 'dict'>`; query parameters `[]`. 

## backend/app/agent_supervision.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| POST | `/api/v1/agent-supervision/{team_id}/runs` | `start_run` line 40 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| GET | `/api/v1/agent-supervision/{team_id}/runs` | `list_runs` line 59 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| POST | `/api/v1/agent-supervision/runs/{run_id}/approval` | `approve_run` line 63 | role_guard: SUPERVISOR; get_current_user; get_db |
| POST | `/api/v1/agent-supervision/runs/{run_id}/execute` | `execute_run` line 71 | role_guard: SUPERVISOR; get_current_user; get_db |
| POST | `/api/v1/agent-supervision/runs/{run_id}/reminder/approve` | `approve_reminder` line 92 | role_guard: SUPERVISOR; get_current_user; get_db |
- `POST /api/v1/agent-supervision/{team_id}/runs`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/agent-supervision/{team_id}/runs`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/agent-supervision/runs/{run_id}/approval`: body `<class 'app.agent_supervision.Approval'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/agent-supervision/runs/{run_id}/execute`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/agent-supervision/runs/{run_id}/reminder/approve`: body `<class 'app.agent_supervision.Approval'>`; response `None`; query parameters `[]`. 

## backend/app/archived_projects.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/archived-projects/search` | `search_archives` line 668 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| GET | `/api/v1/archived-projects/admin/list` | `admin_archive_list` line 723 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/archived-projects/admin/detail/{project_id}` | `admin_archive_detail` line 728 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/archived-projects/{project_id}` | `read_archive` line 736 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| GET | `/api/v1/archived-projects/{project_id}/documents/{document_id}` | `read_archive_document` line 741 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| POST | `/api/v1/archived-projects/admin` | `create_archive` line 754 | role_guard: ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/archived-projects/admin/{project_id}` | `update_archive` line 770 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/archived-projects/admin/{project_id}` | `delete_archive` line 804 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/archived-projects/admin/{project_id}/rollback/{event_id}` | `rollback_archive_metadata` line 823 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/archived-projects/admin/{project_id}/active` | `set_archive_active` line 845 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/archived-projects/admin/{project_id}/documents` | `upload_archive_document` line 857 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/archived-projects/admin/{project_id}/documents/history` | `archive_document_history` line 878 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/archived-projects/admin/{project_id}/documents/{document_id}` | `delete_archive_document` line 886 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/archived-projects/admin/{project_id}/visibility` | `set_archive_visibility` line 1099 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/archive/import/preview` | `archive_import_preview` line 909 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/archive/projects/import` | `archive_import_confirm` line 917 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/archive/import/confirm` | `archive_import_confirm` line 917 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/archive/projects` | `admin_archive_projects` line 1006 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/archive/projects/repair-imported` | `repair_imported_archive` line 1029 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/archive/projects/{project_id}` | `admin_archive_project` line 1067 | role_guard: ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/admin/archive/projects/{project_id}` | `admin_update_archive` line 1074 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/archive/projects/{project_id}` | `admin_delete_archive` line 1079 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/archive/import-batches` | `archive_import_batches` line 1084 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/archive/import-batches/{batch_id}` | `archive_import_batch_detail` line 1091 | role_guard: ADMIN; get_current_user; get_db |
- `GET /api/v1/archived-projects/search`: body `None`; response `None`; query parameters `[{'name': 'q', 'required': False}, {'name': 'academic_year', 'required': False}, {'name': 'session_name', 'required': False}, {'name': 'department', 'required': False}, {'name': 'supervisor', 'required': False}, {'name': 'technology', 'required': False}, {'name': 'project_scope', 'required': False}, {'name': 'completion_stage', 'required': False}]`. 
- `GET /api/v1/archived-projects/admin/list`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/archived-projects/admin/detail/{project_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/archived-projects/{project_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/archived-projects/{project_id}/documents/{document_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/archived-projects/admin`: body `<class 'app.archived_projects.ArchiveCreate'>`; response `None`; query parameters `[]`. 
- `PATCH /api/v1/archived-projects/admin/{project_id}`: body `<class 'app.archived_projects.ArchiveUpdate'>`; response `None`; query parameters `[]`. 
- `DELETE /api/v1/archived-projects/admin/{project_id}`: body `None`; response `None`; query parameters `[]`. Permanently remove an archive record and all of its stored document versions.
- `POST /api/v1/archived-projects/admin/{project_id}/rollback/{event_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/archived-projects/admin/{project_id}/active`: body `<class 'fastapi._compat.v2.Body_set_archive_active_api_v1_archived_projects_admin__project_id__active_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/archived-projects/admin/{project_id}/documents`: body `<class 'fastapi._compat.v2.Body_upload_archive_document_api_v1_archived_projects_admin__project_id__documents_post'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/archived-projects/admin/{project_id}/documents/history`: body `None`; response `None`; query parameters `[]`. 
- `DELETE /api/v1/archived-projects/admin/{project_id}/documents/{document_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/archived-projects/admin/{project_id}/visibility`: body `<class 'fastapi._compat.v2.Body_set_archive_visibility_api_v1_archived_projects_admin__project_id__visibility_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/admin/archive/import/preview`: body `<class 'fastapi._compat.v2.Body_archive_import_preview_api_v1_admin_archive_import_preview_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/admin/archive/projects/import`: body `<class 'fastapi._compat.v2.Body_archive_import_confirm_api_v1_admin_archive_projects_import_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/admin/archive/import/confirm`: body `<class 'fastapi._compat.v2.Body_archive_import_confirm_api_v1_admin_archive_import_confirm_post'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/admin/archive/projects`: body `None`; response `dict[str, object]`; query parameters `[{'name': 'search', 'required': False}, {'name': 'academic_cycle_id', 'required': False}, {'name': 'session_name', 'required': False}, {'name': 'supervisor', 'required': False}, {'name': 'domain', 'required': False}, {'name': 'source_batch_id', 'required': False}, {'name': 'page', 'required': False}, {'name': 'page_size', 'required': False}, {'name': 'sort', 'required': False}, {'name': 'direction', 'required': False}]`. 
- `POST /api/v1/admin/archive/projects/repair-imported`: body `None`; response `dict[str, object]`; query parameters `[]`. Safely consolidate obvious duplicate imported parents.
- `GET /api/v1/admin/archive/projects/{project_id}`: body `None`; response `<class 'dict'>`; query parameters `[]`. 
- `PATCH /api/v1/admin/archive/projects/{project_id}`: body `<class 'app.archived_projects.ArchiveUpdate'>`; response `<class 'dict'>`; query parameters `[]`. 
- `DELETE /api/v1/admin/archive/projects/{project_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/admin/archive/import-batches`: body `None`; response `dict[str, object]`; query parameters `[{'name': 'page', 'required': False}, {'name': 'page_size', 'required': False}]`. 
- `GET /api/v1/admin/archive/import-batches/{batch_id}`: body `None`; response `dict[str, object]`; query parameters `[]`. 

## backend/app/audit_history.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/admin/audit-events` | `list_events` line 88 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/audit-events/{event_id}` | `event_detail` line 112 | role_guard: ADMIN; get_current_user; get_db |
- `GET /api/v1/admin/audit-events`: body `None`; response `None`; query parameters `[{'name': 'actor_id', 'required': False}, {'name': 'action', 'required': False}, {'name': 'target_type', 'required': False}, {'name': 'target_id', 'required': False}, {'name': 'from_at', 'required': False}, {'name': 'to_at', 'required': False}, {'name': 'page', 'required': False}, {'name': 'page_size', 'required': False}]`. 
- `GET /api/v1/admin/audit-events/{event_id}`: body `None`; response `None`; query parameters `[]`. 

## backend/app/collaboration_channels.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/student/collaboration/channels` | `student_channels` line 105 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/supervisor/collaboration/channels` | `supervisor_channels` line 110 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/collaboration/channels/{channel_id}` | `collaboration_channel` line 115 | get_current_user; get_db |
| GET | `/api/v1/student/collaboration/channels/{channel_id}` | `collaboration_channel` line 115 | get_current_user; get_db |
| GET | `/api/v1/supervisor/collaboration/channels/{channel_id}/messages` | `collaboration_messages` line 122 | get_current_user; get_db |
| GET | `/api/v1/student/collaboration/channels/{channel_id}/messages` | `collaboration_messages` line 122 | get_current_user; get_db |
| POST | `/api/v1/supervisor/collaboration/channels/{channel_id}/messages` | `send_collaboration_message` line 130 | get_current_user; get_db |
| POST | `/api/v1/student/collaboration/channels/{channel_id}/messages` | `send_collaboration_message` line 130 | get_current_user; get_db |
- `GET /api/v1/student/collaboration/channels`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/collaboration/channels`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/collaboration/channels/{channel_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/student/collaboration/channels/{channel_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/collaboration/channels/{channel_id}/messages`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/student/collaboration/channels/{channel_id}/messages`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor/collaboration/channels/{channel_id}/messages`: body `<class 'app.collaboration_channels.MessageWrite'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/student/collaboration/channels/{channel_id}/messages`: body `<class 'app.collaboration_channels.MessageWrite'>`; response `None`; query parameters `[]`. 

## backend/app/coordinator_operations.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/coordinator/supervisor-capacity` | `supervisor_capacity` line 15 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/coordinator/audit-history` | `audit_history` line 52 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/coordinator/proposal-templates` | `proposal_templates` line 65 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/coordinator/evaluation-criteria` | `evaluation_criteria` line 77 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
- `GET /api/v1/coordinator/supervisor-capacity`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/coordinator/audit-history`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/coordinator/proposal-templates`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/coordinator/evaluation-criteria`: body `None`; response `None`; query parameters `[]`. 

## backend/app/dashboard_requirements.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/dashboard/deadlines` | `dashboard_requirements` line 34 | get_current_user; get_db |
| GET | `/api/v1/dashboard/requirements` | `dashboard_requirements` line 34 | get_current_user; get_db |
| GET | `/api/v1/dashboard/summary` | `dashboard_summary` line 42 | get_current_user; get_db |
| POST | `/api/v1/dashboard/requirements` | `create_requirement` line 47 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| PATCH | `/api/v1/dashboard/requirements/{requirement_id}` | `update_requirement` line 56 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| DELETE | `/api/v1/dashboard/requirements/{requirement_id}` | `delete_requirement` line 65 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
- `GET /api/v1/dashboard/deadlines`: body `None`; response `list[app.schemas.dashboard_requirements.DashboardRequirementOut]`; query parameters `[]`. 
- `GET /api/v1/dashboard/requirements`: body `None`; response `list[app.schemas.dashboard_requirements.DashboardRequirementOut]`; query parameters `[]`. 
- `GET /api/v1/dashboard/summary`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/dashboard/requirements`: body `<class 'app.schemas.dashboard_requirements.DashboardRequirementWrite'>`; response `<class 'app.schemas.dashboard_requirements.DashboardRequirementOut'>`; query parameters `[]`. 
- `PATCH /api/v1/dashboard/requirements/{requirement_id}`: body `<class 'app.schemas.dashboard_requirements.DashboardRequirementWrite'>`; response `<class 'app.schemas.dashboard_requirements.DashboardRequirementOut'>`; query parameters `[]`. 
- `DELETE /api/v1/dashboard/requirements/{requirement_id}`: body `None`; response `None`; query parameters `[]`. 

## backend/app/document_requirements.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| POST | `/api/v1/document-requirements` | `create_requirement` line 87 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| DELETE | `/api/v1/document-requirements/{requirement_id}` | `delete_requirement` line 112 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/document-requirements` | `list_requirements` line 132 | get_current_user; get_db |
| GET | `/api/v1/document-requirements/{requirement_id}` | `get_requirement` line 137 | get_current_user; get_db |
| PATCH | `/api/v1/document-requirements/{requirement_id}` | `update_requirement` line 145 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/publish` | `publish` line 162 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/unpublish` | `unpublish` line 164 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/close` | `close` line 166 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/archive` | `archive` line 168 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/reopen` | `reopen` line 170 | validate_mutating_origin; role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/document-requirements/student` | `student_requirements` line 210 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/upload` | `upload` line 216 | validate_mutating_origin; role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/document-requirements/{requirement_id}/submission` | `submission` line 246 | get_current_user; get_db |
| GET | `/api/v1/document-requirements/{requirement_id}/submissions` | `all_submissions` line 254 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/document-requirements/{requirement_id}/submission/versions` | `versions` line 273 | get_current_user; get_db |
| GET | `/api/v1/document-requirements/submissions/{submission_id}/versions/{version_id}/download` | `download` line 279 | get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/submissions/{submission_id}/approve` | `approve` line 298 | validate_mutating_origin; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/submissions/{submission_id}/reject` | `reject` line 300 | validate_mutating_origin; get_current_user; get_db |
| POST | `/api/v1/document-requirements/{requirement_id}/submissions/{submission_id}/request-replacement` | `replacement` line 302 | validate_mutating_origin; get_current_user; get_db |
| GET | `/api/v1/student/group/requirements/{requirement_id}` | `get_requirement` line 137 | get_current_user; get_db |
| GET | `/api/v1/student/group/requirements` | `student_requirements` line 210 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/student/document-requirements` | `student_requirements` line 210 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/student/group/requirements/{requirement_id}/resubmit` | `upload` line 216 | validate_mutating_origin; role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/student/group/requirements/{requirement_id}/upload` | `upload` line 216 | validate_mutating_origin; role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/student/group/requirements/{requirement_id}/submission` | `submission` line 246 | get_current_user; get_db |
- `POST /api/v1/document-requirements`: body `<class 'app.schemas.document_requirements.RequirementWrite'>`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `DELETE /api/v1/document-requirements/{requirement_id}`: body `None`; response `None`; query parameters `[]`. Remove an unused draft requirement while preserving published/history records.
- `GET /api/v1/document-requirements`: body `None`; response `list[app.schemas.document_requirements.RequirementOut]`; query parameters `[]`. 
- `GET /api/v1/document-requirements/{requirement_id}`: body `None`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `PATCH /api/v1/document-requirements/{requirement_id}`: body `<class 'app.schemas.document_requirements.RequirementPatch'>`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/publish`: body `None`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/unpublish`: body `None`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/close`: body `None`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/archive`: body `None`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/reopen`: body `None`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `GET /api/v1/document-requirements/student`: body `None`; response `list[app.schemas.document_requirements.RequirementOut]`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/upload`: body `<class 'fastapi._compat.v2.Body_upload_api_v1_document_requirements__requirement_id__upload_post'>`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[]`. 
- `GET /api/v1/document-requirements/{requirement_id}/submission`: body `None`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[]`. 
- `GET /api/v1/document-requirements/{requirement_id}/submissions`: body `None`; response `None`; query parameters `[]`. Return every student's submission and every uploaded version for an admin requirement view.
- `GET /api/v1/document-requirements/{requirement_id}/submission/versions`: body `None`; response `list[app.schemas.document_requirements.VersionOut]`; query parameters `[]`. 
- `GET /api/v1/document-requirements/submissions/{submission_id}/versions/{version_id}/download`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/submissions/{submission_id}/approve`: body `None`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[]`. 
- `POST /api/v1/document-requirements/{requirement_id}/submissions/{submission_id}/reject`: body `None`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[{'name': 'comment', 'required': False}]`. 
- `POST /api/v1/document-requirements/{requirement_id}/submissions/{submission_id}/request-replacement`: body `None`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[{'name': 'comment', 'required': False}]`. 
- `GET /api/v1/student/group/requirements/{requirement_id}`: body `None`; response `<class 'app.schemas.document_requirements.RequirementOut'>`; query parameters `[]`. 
- `GET /api/v1/student/group/requirements`: body `None`; response `list[app.schemas.document_requirements.RequirementOut]`; query parameters `[]`. 
- `GET /api/v1/student/document-requirements`: body `None`; response `list[app.schemas.document_requirements.RequirementOut]`; query parameters `[]`. 
- `POST /api/v1/student/group/requirements/{requirement_id}/resubmit`: body `<class 'fastapi._compat.v2.Body_upload_api_v1_student_group_requirements__requirement_id__resubmit_post'>`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[]`. 
- `POST /api/v1/student/group/requirements/{requirement_id}/upload`: body `<class 'fastapi._compat.v2.Body_upload_api_v1_student_group_requirements__requirement_id__upload_post'>`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[]`. 
- `GET /api/v1/student/group/requirements/{requirement_id}/submission`: body `None`; response `<class 'app.schemas.document_requirements.SubmissionOut'>`; query parameters `[]`. 

## backend/app/evaluations.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/evaluations/assignments` | `evaluation_assignments` line 141 | get_current_user; get_db |
| GET | `/api/v1/evaluations/my` | `my_evaluations` line 148 | get_current_user; get_db |
| POST | `/api/v1/evaluations` | `create_evaluation` line 200 | get_current_user; get_db |
| PATCH | `/api/v1/evaluations/{evaluation_id}` | `update_evaluation` line 216 | get_current_user; get_db |
| POST | `/api/v1/evaluations/{evaluation_id}/submit` | `submit_evaluation` line 232 | get_current_user; get_db |
| POST | `/api/v1/evaluations/{evaluation_id}/return` | `return_evaluation` line 253 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/evaluations/{evaluation_id}/approve` | `approve_evaluation` line 271 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/evaluations/{evaluation_id}/correct` | `correct_evaluation` line 287 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| POST | `/api/v1/evaluations/{evaluation_id}/publish` | `publish_evaluation` line 309 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/evaluations/{evaluation_id}/audit` | `evaluation_audit` line 325 | get_current_user; get_db |
| GET | `/api/v1/admin/evaluations` | `admin_evaluations` line 336 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/admin/evaluations/aggregation` | `list_aggregation` line 348 | role_guard: ADMIN; get_current_user; get_db |
| PUT | `/api/v1/admin/evaluations/aggregation` | `update_aggregation` line 359 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/student/results` | `student_results` line 430 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/admin/results/group/{group_id}` | `admin_group_results` line 435 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/admin/results/{student_id}` | `admin_results` line 445 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/evaluations/{evaluation_id}/report` | `evaluation_report` line 476 | get_current_user; get_db |
| GET | `/api/v1/evaluations/{evaluation_id}/report.pdf` | `evaluation_report_pdf` line 487 | get_current_user; get_db |
- `GET /api/v1/evaluations/assignments`: body `None`; response `list[app.schemas.evaluations.EvaluationAssignmentOut]`; query parameters `[]`. 
- `GET /api/v1/evaluations/my`: body `None`; response `list[app.schemas.evaluations.EvaluationOut]`; query parameters `[{'name': 'evaluation_status', 'required': False}, {'name': 'category', 'required': False}]`. 
- `POST /api/v1/evaluations`: body `<class 'app.schemas.evaluations.EvaluationWrite'>`; response `<class 'app.schemas.evaluations.EvaluationOut'>`; query parameters `[]`. 
- `PATCH /api/v1/evaluations/{evaluation_id}`: body `<class 'app.schemas.evaluations.EvaluationWrite'>`; response `<class 'app.schemas.evaluations.EvaluationOut'>`; query parameters `[]`. 
- `POST /api/v1/evaluations/{evaluation_id}/submit`: body `None`; response `<class 'app.schemas.evaluations.EvaluationOut'>`; query parameters `[]`. 
- `POST /api/v1/evaluations/{evaluation_id}/return`: body `<class 'app.schemas.evaluations.EvaluationReturn'>`; response `<class 'app.schemas.evaluations.EvaluationOut'>`; query parameters `[]`. 
- `POST /api/v1/evaluations/{evaluation_id}/approve`: body `None`; response `<class 'app.schemas.evaluations.EvaluationOut'>`; query parameters `[]`. 
- `POST /api/v1/evaluations/{evaluation_id}/correct`: body `<class 'app.schemas.evaluations.EvaluationCorrectionWrite'>`; response `<class 'app.schemas.evaluations.EvaluationOut'>`; query parameters `[]`. 
- `POST /api/v1/evaluations/{evaluation_id}/publish`: body `None`; response `<class 'app.schemas.evaluations.EvaluationOut'>`; query parameters `[]`. 
- `GET /api/v1/evaluations/{evaluation_id}/audit`: body `None`; response `list[dict]`; query parameters `[]`. 
- `GET /api/v1/admin/evaluations`: body `None`; response `list[app.schemas.evaluations.EvaluationOut]`; query parameters `[{'name': 'evaluation_status', 'required': False}, {'name': 'category', 'required': False}, {'name': 'evaluator_id', 'required': False}]`. 
- `GET /api/v1/admin/evaluations/aggregation`: body `None`; response `list[app.schemas.evaluations.EvaluationAggregationOut]`; query parameters `[]`. 
- `PUT /api/v1/admin/evaluations/aggregation`: body `<class 'app.schemas.evaluations.EvaluationAggregationWrite'>`; response `<class 'app.schemas.evaluations.EvaluationAggregationOut'>`; query parameters `[]`. 
- `GET /api/v1/student/results`: body `None`; response `<class 'app.schemas.evaluations.ConsolidatedResultOut'>`; query parameters `[]`. 
- `GET /api/v1/admin/results/group/{group_id}`: body `None`; response `list[app.schemas.evaluations.ConsolidatedResultOut]`; query parameters `[]`. 
- `GET /api/v1/admin/results/{student_id}`: body `None`; response `<class 'app.schemas.evaluations.ConsolidatedResultOut'>`; query parameters `[]`. 
- `GET /api/v1/evaluations/{evaluation_id}/report`: body `None`; response `<class 'dict'>`; query parameters `[]`. 
- `GET /api/v1/evaluations/{evaluation_id}/report.pdf`: body `None`; response `None`; query parameters `[]`. 

## backend/app/group_ai.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/group-ai/{team_id}` | `history` line 84 | get_current_user; get_db |
| POST | `/api/v1/group-ai/{team_id}` | `chat` line 91 | get_current_user; get_db |
- `GET /api/v1/group-ai/{team_id}`: body `None`; response `None`; query parameters `[{'name': 'before_id', 'required': False}]`. 
- `POST /api/v1/group-ai/{team_id}`: body `<class 'app.group_channels.MessageWrite'>`; response `None`; query parameters `[]`. 

## backend/app/group_channels.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/group-channels/teams` | `teams` line 57 | get_current_user; get_db |
| GET | `/api/v1/group-channels/{team_id}/{channel}` | `history` line 66 | get_current_user; get_db |
| POST | `/api/v1/group-channels/{team_id}/{channel}` | `send` line 73 | get_current_user; get_db |
| POST | `/api/v1/group-channels/{team_id}/files` | `upload_file` line 92 | get_current_user; get_db |
| GET | `/api/v1/group-channels/{team_id}/files/{stored_name}` | `download_file` line 112 | get_current_user; get_db |
- `GET /api/v1/group-channels/teams`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/group-channels/{team_id}/{channel}`: body `None`; response `None`; query parameters `[{'name': 'before_id', 'required': False}]`. 
- `POST /api/v1/group-channels/{team_id}/{channel}`: body `<class 'app.group_channels.MessageWrite'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/group-channels/{team_id}/files`: body `<class 'fastapi._compat.v2.Body_upload_file_api_v1_group_channels__team_id__files_post'>`; response `None`; query parameters `[]`. Store a team-scoped resource and publish it into Files & Resources.
- `GET /api/v1/group-channels/{team_id}/files/{stored_name}`: body `None`; response `None`; query parameters `[]`. 

## backend/app/main.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/academic-cycles` | `list_cycles` line 168 | get_db |
| GET | `/api/v1/academic-cycles/{cycle_id}/group-policy` | `get_group_policy` line 172 | get_db |
| GET | `/api/v1/admin/time-zones` | `list_time_zones` line 320 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/academic-deadlines/preview` | `preview_academic_deadline` line 326 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/academic-deadlines` | `list_academic_deadlines` line 337 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/academic-deadlines/{deadline_id}` | `academic_deadline_detail` line 372 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/academic-deadlines` | `create_academic_deadline` line 384 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/academic-deadlines/{deadline_id}/versions` | `create_academic_deadline_version` line 414 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/academic-deadlines/{deadline_id}` | `delete_academic_deadline` line 446 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/template-references` | `list_template_references` line 477 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/template-references/{reference_id}` | `template_reference_detail` line 487 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/template-references` | `create_template_reference` line 516 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/template-references/{reference_id}/versions` | `create_template_version` line 540 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/template-reference-versions/{version_id}/rules` | `create_rule_version` line 547 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/template-reference-versions/{version_id}` | `delete_template_reference_version` line 556 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/evaluation-rubrics` | `list_evaluation_rubrics` line 650 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/evaluation-rubrics/{rubric_id}` | `evaluation_rubric_detail` line 685 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/evaluation-rubrics` | `create_evaluation_rubric` line 697 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/evaluation-rubrics/{rubric_id}/versions` | `create_evaluation_rubric_version` line 721 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/academic-cycles` | `create_cycle` line 758 | role_guard: ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/admin/academic-cycles/{cycle_id}` | `update_cycle` line 775 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/academic-cycles/{cycle_id}` | `delete_cycle` line 795 | role_guard: ADMIN; get_current_user; get_db |
| PUT | `/api/v1/admin/academic-cycles/{cycle_id}/group-policy` | `set_group_policy` line 814 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/academic-cycles/{cycle_id}/group-policy` | `delete_group_policy` line 833 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/health` | `health` line 849 | See handler |
| GET | `/health/ready` | `readiness` line 855 | See handler |
| POST | `/api/v1/auth/login` | `login` line 879 | get_db |
| GET | `/api/v1/auth/me` | `current_user` line 1003 | get_current_user; get_db |
| GET | `/api/v1/admin/me` | `admin_current_user` line 1018 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/registration-mode` | `admin_registration_mode` line 1037 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/users` | `list_admin_users` line 1186 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/users` | `create_admin_user` line 1216 | role_guard: ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/admin/users/{user_id}/status` | `change_admin_user_status` line 1249 | role_guard: ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/admin/users/{user_id}/role` | `change_admin_user_role` line 1285 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/users/{user_id}` | `delete_admin_user` line 1327 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/supervisor-capacities` | `list_supervisor_capacities` line 1357 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/supervisor/capacity` | `supervisor_capacity_workspace` line 1367 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/admin/supervisor-capacities/{policy_id}` | `read_supervisor_capacity` line 1409 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/supervisor-capacities` | `create_supervisor_capacity` line 1419 | role_guard: ADMIN; get_current_user; get_db |
| PUT | `/api/v1/admin/supervisor-capacities/{policy_id}` | `update_supervisor_capacity` line 1453 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/supervisor-capacities/{policy_id}` | `delete_supervisor_capacity` line 1491 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/auth/logout` | `logout` line 1522 | get_db |
| POST | `/api/v1/auth/register` | `register_student` line 1543 | get_db |
| POST | `/api/v1/team-registration` | `register_team` line 1563 | get_db |
| POST | `/api/v1/auth/group-signup` | `register_student_group` line 1813 | get_db |
| POST | `/api/v1/student/group-registration` | `register_student_group` line 1813 | get_db |
| GET | `/api/v1/student/group/me` | `student_group_me` line 1911 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/student/group/members` | `student_group_members` line 1919 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/admin/student-groups` | `list_student_groups` line 1928 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/student-groups/{group_id}` | `get_student_group` line 1945 | role_guard: ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/admin/student-groups/{group_id}/activate` | `activate_student_group` line 1978 | role_guard: ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/admin/student-groups/{group_id}/deactivate` | `deactivate_student_group` line 1983 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/student-groups/{group_id}` | `delete_student_group` line 1988 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/reminder-rules/preview` | `preview_reminder_rule` line 2057 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/reminder-rules` | `list_reminder_rules` line 2063 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/reminder-rules/{rule_id}` | `read_reminder_rule` line 2073 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/reminder-rules` | `create_reminder_rule` line 2081 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/reminder-rules/{rule_id}/versions` | `create_reminder_rule_version` line 2103 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/admin/reminder-rules/{rule_id}` | `delete_reminder_rule` line 2126 | role_guard: ADMIN; get_current_user; get_db |
- `GET /api/v1/academic-cycles`: body `None`; response `list[app.schemas.academic.CycleOut]`; query parameters `[]`. 
- `GET /api/v1/academic-cycles/{cycle_id}/group-policy`: body `None`; response `<class 'app.schemas.academic.PolicyOut'>`; query parameters `[]`. 
- `GET /api/v1/admin/time-zones`: body `None`; response `list[str]`; query parameters `[]`. 
- `POST /api/v1/admin/academic-deadlines/preview`: body `<class 'app.schemas.academic_deadlines.DeadlinePreviewRequest'>`; response `<class 'app.schemas.academic_deadlines.DeadlinePreviewOut'>`; query parameters `[]`. 
- `GET /api/v1/admin/academic-deadlines`: body `None`; response `list[app.schemas.academic_deadlines.DeadlineListOut]`; query parameters `[{'name': 'academic_cycle_id', 'required': False}]`. 
- `GET /api/v1/admin/academic-deadlines/{deadline_id}`: body `None`; response `<class 'app.schemas.academic_deadlines.DeadlineDetailOut'>`; query parameters `[]`. 
- `POST /api/v1/admin/academic-deadlines`: body `<class 'app.schemas.academic_deadlines.DeadlineCreate'>`; response `<class 'app.schemas.academic_deadlines.DeadlineDetailOut'>`; query parameters `[]`. 
- `POST /api/v1/admin/academic-deadlines/{deadline_id}/versions`: body `<class 'app.schemas.academic_deadlines.DeadlineWrite'>`; response `<class 'app.schemas.academic_deadlines.DeadlineVersionOut'>`; query parameters `[]`. 
- `DELETE /api/v1/admin/academic-deadlines/{deadline_id}`: body `None`; response `None`; query parameters `[]`. Remove a deadline and its recorded versions when no rule references it.
- `GET /api/v1/admin/template-references`: body `None`; response `list[app.schemas.templates.TemplateListOut]`; query parameters `[]`. 
- `GET /api/v1/admin/template-references/{reference_id}`: body `None`; response `<class 'app.schemas.templates.TemplateDetail'>`; query parameters `[]`. 
- `POST /api/v1/admin/template-references`: body `<class 'app.schemas.templates.TemplateCreate'>`; response `<class 'app.schemas.templates.TemplateDetail'>`; query parameters `[]`. 
- `POST /api/v1/admin/template-references/{reference_id}/versions`: body `<class 'app.schemas.templates.TemplateVersionCreate'>`; response `<class 'app.schemas.templates.TemplateOut'>`; query parameters `[]`. 
- `POST /api/v1/admin/template-reference-versions/{version_id}/rules`: body `<class 'app.schemas.templates.RuleCreate'>`; response `<class 'app.schemas.templates.RuleOut'>`; query parameters `[]`. 
- `DELETE /api/v1/admin/template-reference-versions/{version_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/admin/evaluation-rubrics`: body `None`; response `list[app.schemas.evaluation_rubrics.RubricListOut]`; query parameters `[]`. 
- `GET /api/v1/admin/evaluation-rubrics/{rubric_id}`: body `None`; response `<class 'app.schemas.evaluation_rubrics.RubricDetailOut'>`; query parameters `[]`. 
- `POST /api/v1/admin/evaluation-rubrics`: body `<class 'app.schemas.evaluation_rubrics.RubricVersionWrite'>`; response `<class 'app.schemas.evaluation_rubrics.RubricDetailOut'>`; query parameters `[]`. 
- `POST /api/v1/admin/evaluation-rubrics/{rubric_id}/versions`: body `<class 'app.schemas.evaluation_rubrics.RubricVersionWrite'>`; response `<class 'app.schemas.evaluation_rubrics.RubricVersionOut'>`; query parameters `[]`. 
- `POST /api/v1/admin/academic-cycles`: body `<class 'app.schemas.academic.CycleCreate'>`; response `<class 'app.schemas.academic.CycleOut'>`; query parameters `[]`. 
- `PATCH /api/v1/admin/academic-cycles/{cycle_id}`: body `<class 'app.schemas.academic.CycleUpdate'>`; response `<class 'app.schemas.academic.CycleOut'>`; query parameters `[]`. 
- `DELETE /api/v1/admin/academic-cycles/{cycle_id}`: body `None`; response `None`; query parameters `[]`. 
- `PUT /api/v1/admin/academic-cycles/{cycle_id}/group-policy`: body `<class 'app.schemas.academic.PolicyUpdate'>`; response `<class 'app.schemas.academic.PolicyOut'>`; query parameters `[]`. 
- `DELETE /api/v1/admin/academic-cycles/{cycle_id}/group-policy`: body `None`; response `None`; query parameters `[]`. 
- `GET /health`: body `None`; response `dict[str, str]`; query parameters `[]`. Report application liveness only; this does not check database connectivity.
- `GET /health/ready`: body `None`; response `dict[str, str]`; query parameters `[]`. Report readiness only when the database and vector extension are available.
- `POST /api/v1/auth/login`: body `<class 'app.schemas.auth.LoginRequest'>`; response `<class 'app.schemas.auth.CurrentUserResponse'>`; query parameters `[]`. Authenticate an active account and issue a new opaque cookie session.
- `GET /api/v1/auth/me`: body `None`; response `<class 'app.schemas.auth.CurrentUserResponse'>`; query parameters `[]`. Return the authenticated active account's safe fields.
- `GET /api/v1/admin/me`: body `None`; response `<class 'app.schemas.auth.CurrentUserResponse'>`; query parameters `[]`. Return the current account only when its persisted role is ADMIN.
- `GET /api/v1/admin/registration-mode`: body `None`; response `dict[str, str / None]`; query parameters `[]`. Expose demo-mode status only to authenticated administrators.
- `GET /api/v1/admin/users`: body `None`; response `<class 'app.schemas.admin_users.AdminUserPage'>`; query parameters `[{'name': 'search', 'required': False}, {'name': 'role', 'required': False}, {'name': 'is_active', 'required': False}, {'name': 'page', 'required': False}, {'name': 'page_size', 'required': False}]`. 
- `POST /api/v1/admin/users`: body `<class 'app.schemas.admin_users.AdminUserCreate'>`; response `<class 'app.schemas.admin_users.AdminUserResponse'>`; query parameters `[]`. 
- `PATCH /api/v1/admin/users/{user_id}/status`: body `<class 'app.schemas.admin_users.AdminUserStatusChange'>`; response `<class 'app.schemas.admin_users.AdminUserResponse'>`; query parameters `[]`. 
- `PATCH /api/v1/admin/users/{user_id}/role`: body `<class 'app.schemas.admin_users.AdminUserRoleChange'>`; response `<class 'app.schemas.admin_users.AdminUserResponse'>`; query parameters `[]`. 
- `DELETE /api/v1/admin/users/{user_id}`: body `None`; response `None`; query parameters `[]`. Permanently remove an unused account; linked records stay protected by FK guards.
- `GET /api/v1/admin/supervisor-capacities`: body `None`; response `list[app.schemas.supervisor_capacity.SupervisorCapacityOut]`; query parameters `[]`. 
- `GET /api/v1/supervisor/capacity`: body `None`; response `list[dict[str, object]]`; query parameters `[]`. Return the signed-in supervisor's read-only annual capacity and assignment detail.
- `GET /api/v1/admin/supervisor-capacities/{policy_id}`: body `None`; response `<class 'app.schemas.supervisor_capacity.SupervisorCapacityOut'>`; query parameters `[]`. 
- `POST /api/v1/admin/supervisor-capacities`: body `<class 'app.schemas.supervisor_capacity.SupervisorCapacityWrite'>`; response `<class 'app.schemas.supervisor_capacity.SupervisorCapacityOut'>`; query parameters `[]`. 
- `PUT /api/v1/admin/supervisor-capacities/{policy_id}`: body `<class 'app.schemas.supervisor_capacity.SupervisorCapacityWrite'>`; response `<class 'app.schemas.supervisor_capacity.SupervisorCapacityOut'>`; query parameters `[]`. 
- `DELETE /api/v1/admin/supervisor-capacities/{policy_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/auth/logout`: body `None`; response `None`; query parameters `[]`. Revoke the presented session when present and always clear its browser cookie.
- `POST /api/v1/auth/register`: body `<class 'app.schemas.auth.RegistrationRequest'>`; response `<class 'app.schemas.auth.RegistrationResponse'>`; query parameters `[]`. Reject the retired individual public signup flow.
- `POST /api/v1/team-registration`: body `<class 'app.schemas.team_registration.TeamRegistrationRequest'>`; response `<class 'app.schemas.team_registration.TeamRegistrationResponse'>`; query parameters `[]`. Atomically create one shared student account, team, and member contacts.
- `POST /api/v1/auth/group-signup`: body `<class 'app.schemas.team_registration.StudentGroupRegistrationRequest'>`; response `<class 'app.schemas.team_registration.TeamRegistrationResponse'>`; query parameters `[]`. Create one shared STUDENT group account from member contacts only.
- `POST /api/v1/student/group-registration`: body `<class 'app.schemas.team_registration.StudentGroupRegistrationRequest'>`; response `<class 'app.schemas.team_registration.TeamRegistrationResponse'>`; query parameters `[]`. Create one shared STUDENT group account from member contacts only.
- `GET /api/v1/student/group/me`: body `None`; response `dict[str, object]`; query parameters `[]`. 
- `GET /api/v1/student/group/members`: body `None`; response `dict[str, object]`; query parameters `[]`. 
- `GET /api/v1/admin/student-groups`: body `None`; response `dict[str, object]`; query parameters `[{'name': 'search', 'required': False}, {'name': 'is_active', 'required': False}]`. 
- `GET /api/v1/admin/student-groups/{group_id}`: body `None`; response `dict[str, object]`; query parameters `[]`. 
- `PATCH /api/v1/admin/student-groups/{group_id}/activate`: body `None`; response `dict[str, object]`; query parameters `[]`. 
- `PATCH /api/v1/admin/student-groups/{group_id}/deactivate`: body `None`; response `dict[str, object]`; query parameters `[]`. 
- `DELETE /api/v1/admin/student-groups/{group_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/admin/reminder-rules/preview`: body `<class 'app.schemas.reminder_rules.RulePreview'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/admin/reminder-rules`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': False}]`. 
- `GET /api/v1/admin/reminder-rules/{rule_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/admin/reminder-rules`: body `<class 'app.schemas.reminder_rules.RuleCreate'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/admin/reminder-rules/{rule_id}/versions`: body `<class 'app.schemas.reminder_rules.RuleWrite'>`; response `None`; query parameters `[]`. 
- `DELETE /api/v1/admin/reminder-rules/{rule_id}`: body `None`; response `None`; query parameters `[]`. 

## backend/app/module2_collaboration.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/module-2/workspace` | `workspace` line 51 | get_current_user; get_db |
| POST | `/api/v1/module-2/teams/{team_id}/transfer-leadership` | `transfer_leadership` line 66 | get_current_user; get_db |
| POST | `/api/v1/module-2/teams/{team_id}/dissolve` | `dissolve` line 82 | get_current_user; get_db |
| POST | `/api/v1/module-2/teams/{team_id}/leave` | `leave_team` line 96 | get_current_user; get_db |
| GET | `/api/v1/module-2/notifications` | `notifications` line 122 | get_current_user; get_db |
| POST | `/api/v1/module-2/notifications/{notification_id}/read` | `mark_notification_read` line 131 | get_current_user; get_db |
| POST | `/api/v1/module-2/teams/{team_id}/{channel}/read` | `mark_channel_read` line 141 | get_current_user; get_db |
| GET | `/api/v1/module-2/teams/{team_id}/unread` | `unread_counts` line 154 | get_current_user; get_db |
| GET | `/api/v1/module-2/teams/{team_id}/proposal-versions` | `proposal_versions` line 167 | get_current_user; get_db |
| GET | `/api/v1/module-2/teams/{team_id}/tasks` | `tasks` line 174 | get_current_user; get_db |
| GET | `/api/v1/module-2/teams/{team_id}/deadlines` | `deadlines` line 181 | get_current_user; get_db |
- `GET /api/v1/module-2/workspace`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/module-2/teams/{team_id}/transfer-leadership`: body `<class 'app.module2_collaboration.TransferLeadership'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/module-2/teams/{team_id}/dissolve`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/module-2/teams/{team_id}/leave`: body `<class 'app.module2_collaboration.LeaveTeam'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/module-2/notifications`: body `None`; response `None`; query parameters `[{'name': 'unread_only', 'required': False}]`. 
- `POST /api/v1/module-2/notifications/{notification_id}/read`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/module-2/teams/{team_id}/{channel}/read`: body `None`; response `None`; query parameters `[{'name': 'message_id', 'required': False}]`. 
- `GET /api/v1/module-2/teams/{team_id}/unread`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/module-2/teams/{team_id}/proposal-versions`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/module-2/teams/{team_id}/tasks`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/module-2/teams/{team_id}/deadlines`: body `None`; response `None`; query parameters `[]`. 

## backend/app/modules/module_03_proposal/router.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| POST | `/api/v1/proposal-compliance/templates/upload` | `upload_template` line 184 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/templates` | `list_templates` line 225 | role_guard: ADMIN, COORDINATOR, SUPERVISOR, PANEL_MEMBER; get_current_user; get_db |
| POST | `/api/v1/proposal-compliance/templates/{version_id}/activate` | `activate_template` line 231 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/proposal-compliance/templates/{version_id}/deactivate` | `deactivate_template` line 249 | role_guard: ADMIN; get_current_user; get_db |
| DELETE | `/api/v1/proposal-compliance/templates/{version_id}` | `delete_template` line 264 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/proposal-compliance/templates/{version_id}/rules` | `save_template_rules` line 283 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/proposal-compliance/submissions` | `submit_proposal` line 319 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposal-compliance/submissions/{submission_id}/submit` | `submit_draft` line 401 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposal-compliance/submissions/{submission_id}/withdraw` | `withdraw_submission` line 415 | role_guard: STUDENT; get_current_user; get_db |
| PATCH | `/api/v1/proposal-compliance/submissions/{submission_id}/status` | `update_submission_status` line 431 | role_guard: ADMIN, COORDINATOR, SUPERVISOR, PANEL_MEMBER; get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/submissions/mine` | `my_submissions` line 450 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/submissions/{submission_id}` | `get_submission` line 458 | get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/reports` | `report_queue` line 467 | role_guard: ADMIN, COORDINATOR, SUPERVISOR, PANEL_MEMBER; get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/reports/{submission_id}` | `get_report` line 473 | get_current_user; get_db |
| POST | `/api/v1/proposal-compliance/reports/{submission_id}/run` | `rerun_report` line 484 | get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/reports/{submission_id}/original` | `get_original` line 497 | get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/reports/{submission_id}/annotated` | `get_annotated_document` line 508 | get_current_user; get_db |
| GET | `/api/v1/proposal-compliance/reports/{submission_id}/pdf` | `download_report_pdf` line 527 | get_current_user; get_db |
- `POST /api/v1/proposal-compliance/templates/upload`: body `<class 'fastapi._compat.v2.Body_upload_template_api_v1_proposal_compliance_templates_upload_post'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposal-compliance/templates`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposal-compliance/templates/{version_id}/activate`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposal-compliance/templates/{version_id}/deactivate`: body `None`; response `None`; query parameters `[]`. Stop using a baseline without deleting its immutable version history.
- `DELETE /api/v1/proposal-compliance/templates/{version_id}`: body `None`; response `None`; query parameters `[]`. Delete an unused uploaded template version and its extracted rule snapshot.
- `POST /api/v1/proposal-compliance/templates/{version_id}/rules`: body `dict[str, typing.Any]`; response `None`; query parameters `[]`. Save an admin-confirmed rule review as a new immutable rule snapshot.
- `POST /api/v1/proposal-compliance/submissions`: body `<class 'fastapi._compat.v2.Body_submit_proposal_api_v1_proposal_compliance_submissions_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposal-compliance/submissions/{submission_id}/submit`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposal-compliance/submissions/{submission_id}/withdraw`: body `None`; response `None`; query parameters `[]`. Withdraw a student-owned draft/submission without deleting its history.
- `PATCH /api/v1/proposal-compliance/submissions/{submission_id}/status`: body `<class 'app.modules.module_03_proposal.router.ProposalStatusUpdate'>`; response `None`; query parameters `[]`. Allow an authorized reviewer to record a lifecycle decision.
- `GET /api/v1/proposal-compliance/submissions/mine`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposal-compliance/submissions/{submission_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposal-compliance/reports`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposal-compliance/reports/{submission_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposal-compliance/reports/{submission_id}/run`: body `None`; response `None`; query parameters `[]`. Explicitly re-run a report against the current active baseline.
- `GET /api/v1/proposal-compliance/reports/{submission_id}/original`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposal-compliance/reports/{submission_id}/annotated`: body `None`; response `None`; query parameters `[]`. Return a safe annotated copy; the student's original file is never modified.
- `GET /api/v1/proposal-compliance/reports/{submission_id}/pdf`: body `None`; response `None`; query parameters `[]`. 

## backend/app/notifications.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/notifications` | `notifications` line 14 | get_current_user; get_db |
| POST | `/api/v1/notifications/{notification_id}/read` | `mark_notification_read` line 23 | get_current_user; get_db |
- `GET /api/v1/notifications`: body `None`; response `None`; query parameters `[{'name': 'unread_only', 'required': False}]`. 
- `POST /api/v1/notifications/{notification_id}/read`: body `None`; response `None`; query parameters `[]`. 

## backend/app/password_reset.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| POST | `/api/v1/auth/forgot-password` | `forgot_password` line 116 | get_db |
| GET | `/api/v1/auth/password-reset-status` | `password_reset_status` line 166 | See handler |
| GET | `/api/v1/auth/dev/password-reset-link` | `development_password_reset_link` line 175 | See handler |
| POST | `/api/v1/auth/reset-password` | `reset_password` line 191 | get_db |
- `POST /api/v1/auth/forgot-password`: body `<class 'app.schemas.password_reset.ForgotPasswordRequest'>`; response `<class 'app.schemas.password_reset.PasswordResetMessage'>`; query parameters `[]`. Create a reset token without revealing whether an account exists.
- `GET /api/v1/auth/password-reset-status`: body `None`; response `dict[str, bool]`; query parameters `[]`. Expose only the non-sensitive delivery mode needed by the local recovery UI.
- `GET /api/v1/auth/dev/password-reset-link`: body `None`; response `dict[str, str]`; query parameters `[{'name': 'identifier', 'required': True}]`. Return a local reset link only when the backend is explicitly in development mode.
- `POST /api/v1/auth/reset-password`: body `<class 'app.schemas.password_reset.ResetPasswordRequest'>`; response `<class 'app.schemas.password_reset.PasswordResetMessage'>`; query parameters `[]`. Consume a valid reset token and revoke every existing browser session.

## backend/app/project_workflow.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/project-progress/{team_id}` | `project_progress` line 109 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN, PANEL_MEMBER; get_current_user; get_db |
| POST | `/api/v1/project-progress/{team_id}/milestones` | `create_milestone` line 118 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/project-progress/milestones/{milestone_id}` | `update_milestone` line 127 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| POST | `/api/v1/project-progress/{team_id}/tasks` | `create_task` line 138 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| PATCH | `/api/v1/project-progress/tasks/{task_id}` | `update_task` line 151 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| GET | `/api/v1/project-progress/{team_id}/meetings` | `list_meetings` line 164 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN, PANEL_MEMBER; get_current_user; get_db |
| POST | `/api/v1/project-progress/{team_id}/meetings` | `create_meeting` line 171 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| GET | `/api/v1/panel-schedules` | `list_schedules` line 227 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN, PANEL_MEMBER; get_current_user; get_db |
| GET | `/api/v1/panel-schedules/options` | `schedule_options` line 235 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/panel-schedules/{schedule_id}` | `schedule_detail` line 243 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN, PANEL_MEMBER; get_current_user; get_db |
| POST | `/api/v1/panel-schedules` | `create_schedule` line 251 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| PATCH | `/api/v1/panel-schedules/{schedule_id}` | `reschedule` line 265 | role_guard: ADMIN, COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/panel-evaluations/schedule/{schedule_id}` | `list_evaluations` line 290 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN, PANEL_MEMBER; get_current_user; get_db |
| POST | `/api/v1/panel-evaluations` | `save_evaluation` line 298 | role_guard: PANEL_MEMBER; get_current_user; get_db |
| POST | `/api/v1/panel-evaluations/{evaluation_id}/resolution` | `resolve_evaluation` line 320 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
- `GET /api/v1/project-progress/{team_id}`: body `None`; response `<class 'dict'>`; query parameters `[]`. 
- `POST /api/v1/project-progress/{team_id}/milestones`: body `<class 'app.schemas.project_workflow.MilestoneWrite'>`; response `<class 'dict'>`; query parameters `[]`. 
- `PATCH /api/v1/project-progress/milestones/{milestone_id}`: body `<class 'app.schemas.project_workflow.MilestoneWrite'>`; response `<class 'dict'>`; query parameters `[]`. 
- `POST /api/v1/project-progress/{team_id}/tasks`: body `<class 'app.schemas.project_workflow.TaskWrite'>`; response `<class 'dict'>`; query parameters `[]`. 
- `PATCH /api/v1/project-progress/tasks/{task_id}`: body `<class 'app.schemas.project_workflow.TaskWrite'>`; response `<class 'dict'>`; query parameters `[]`. 
- `GET /api/v1/project-progress/{team_id}/meetings`: body `None`; response `list[dict]`; query parameters `[]`. 
- `POST /api/v1/project-progress/{team_id}/meetings`: body `<class 'app.schemas.project_workflow.MeetingWrite'>`; response `<class 'dict'>`; query parameters `[]`. 
- `GET /api/v1/panel-schedules`: body `None`; response `list[dict]`; query parameters `[{'name': 'academic_cycle_id', 'required': False}]`. 
- `GET /api/v1/panel-schedules/options`: body `None`; response `<class 'dict'>`; query parameters `[]`. 
- `GET /api/v1/panel-schedules/{schedule_id}`: body `None`; response `<class 'dict'>`; query parameters `[]`. 
- `POST /api/v1/panel-schedules`: body `<class 'app.schemas.project_workflow.ScheduleWrite'>`; response `<class 'dict'>`; query parameters `[]`. 
- `PATCH /api/v1/panel-schedules/{schedule_id}`: body `<class 'app.schemas.project_workflow.ScheduleReschedule'>`; response `<class 'dict'>`; query parameters `[]`. 
- `GET /api/v1/panel-evaluations/schedule/{schedule_id}`: body `None`; response `list[dict]`; query parameters `[]`. 
- `POST /api/v1/panel-evaluations`: body `<class 'app.schemas.project_workflow.EvaluationWrite'>`; response `<class 'dict'>`; query parameters `[]`. 
- `POST /api/v1/panel-evaluations/{evaluation_id}/resolution`: body `<class 'app.schemas.project_workflow.ResolutionWrite'>`; response `<class 'dict'>`; query parameters `[]`. 

## backend/app/proposal_reference.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/proposal-references/search` | `search_references` line 49 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
| GET | `/api/v1/proposal-references/{reference_id}/document` | `reference_document` line 77 | role_guard: STUDENT, SUPERVISOR, COORDINATOR, ADMIN; get_current_user; get_db |
- `GET /api/v1/proposal-references/search`: body `None`; response `None`; query parameters `[{'name': 'q', 'required': True}]`. 
- `GET /api/v1/proposal-references/{reference_id}/document`: body `None`; response `None`; query parameters `[]`. 

## backend/app/supervisor_assignments.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/admin/supervisor-assignments/teams` | `teams` line 24 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/admin/supervisor-assignments` | `listing` line 28 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/supervisor-assignments` | `assign` line 31 | role_guard: ADMIN; get_current_user; get_db |
| POST | `/api/v1/admin/supervisor-assignments/{assignment_id}/end` | `end` line 72 | role_guard: ADMIN; get_current_user; get_db |
- `GET /api/v1/admin/supervisor-assignments/teams`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': True}]`. 
- `GET /api/v1/admin/supervisor-assignments`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': True}]`. 
- `POST /api/v1/admin/supervisor-assignments`: body `<class 'app.supervisor_assignments.AssignmentWrite'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/admin/supervisor-assignments/{assignment_id}/end`: body `None`; response `None`; query parameters `[]`. 

## backend/app/supervisor_request_conversations.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/supervisor-requests/{request_id}/conversation` | `conversation_history` line 51 | get_current_user; get_db |
| POST | `/api/v1/supervisor-requests/{request_id}/conversation` | `send_conversation_message` line 58 | get_current_user; get_db |
- `GET /api/v1/supervisor-requests/{request_id}/conversation`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor-requests/{request_id}/conversation`: body `<class 'app.supervisor_request_conversations.RequestMessageWrite'>`; response `None`; query parameters `[]`. 

## backend/app/supervisor_requests.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/supervisor-requests/cycles` | `active_cycles` line 476 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/supervisor-requests/supervisors` | `eligible_supervisors` line 485 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/supervisor-requests/mine` | `my_requests` line 521 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/supervisor-requests` | `create_request` line 540 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/supervisor-requests/draft/{request_id}/document` | `update_draft_document` line 631 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/supervisor-requests/{request_id}/confirm` | `confirm_extraction` line 696 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/supervisor-requests/{request_id}/submit` | `submit_request` line 734 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/supervisor-requests/{request_id}/withdraw` | `withdraw_request` line 799 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/supervisor-requests/supervisor/queue` | `supervisor_queue` line 831 | role_guard: SUPERVISOR; get_current_user; get_db |
| POST | `/api/v1/supervisor-requests/{request_id}/decision` | `decide_request` line 848 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor-requests/document/{request_id}` | `proposal_document` line 920 | get_current_user; get_db |
| GET | `/api/v1/supervisor-requests/admin/monitor` | `admin_monitor` line 971 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/supervisor-requests/coordinator/monitor` | `coordinator_monitor` line 986 | role_guard: COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/supervisor-requests/detail/{request_id}` | `read_request` line 1001 | get_current_user; get_db |
| GET | `/api/v1/proposals/cycles` | `active_cycles` line 476 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/proposals/supervisors` | `eligible_supervisors` line 485 | role_guard: STUDENT; get_current_user; get_db |
| GET | `/api/v1/proposals/mine` | `my_requests` line 521 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposals` | `create_request` line 540 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposals/draft/{request_id}/document` | `update_draft_document` line 631 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposals/{request_id}/confirm` | `confirm_extraction` line 696 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposals/{request_id}/submit` | `submit_request` line 734 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposals/{request_id}/withdraw` | `withdraw_request` line 799 | role_guard: STUDENT; get_current_user; get_db |
| POST | `/api/v1/proposals/{request_id}/decision` | `decide_request` line 848 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/proposals/document/{request_id}` | `proposal_document` line 920 | get_current_user; get_db |
| GET | `/api/v1/proposals/admin/monitor` | `admin_monitor` line 971 | role_guard: ADMIN; get_current_user; get_db |
| GET | `/api/v1/proposals/coordinator/monitor` | `coordinator_monitor` line 986 | role_guard: COORDINATOR; get_current_user; get_db |
| GET | `/api/v1/proposals/{request_id}` | `read_request` line 1001 | get_current_user; get_db |
| POST | `/api/v1/proposals/{request_id}/ai-review` | `run_proposal_ai_review` line 1020 | get_current_user; get_db |
| GET | `/api/v1/proposals/{request_id}/ai-review` | `latest_proposal_ai_review` line 1072 | get_current_user; get_db |
- `GET /api/v1/supervisor-requests/cycles`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor-requests/supervisors`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': True}]`. 
- `GET /api/v1/supervisor-requests/mine`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor-requests`: body `<class 'fastapi._compat.v2.Body_create_request_api_v1_supervisor_requests_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor-requests/draft/{request_id}/document`: body `<class 'fastapi._compat.v2.Body_update_draft_document_api_v1_supervisor_requests_draft__request_id__document_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor-requests/{request_id}/confirm`: body `<class 'app.supervisor_requests.RevisionAction'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor-requests/{request_id}/submit`: body `<class 'app.supervisor_requests.RevisionAction'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor-requests/{request_id}/withdraw`: body `<class 'app.supervisor_requests.RevisionAction'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor-requests/supervisor/queue`: body `None`; response `None`; query parameters `[{'name': 'status_filter', 'required': False}]`. 
- `POST /api/v1/supervisor-requests/{request_id}/decision`: body `<class 'app.supervisor_requests.DecisionAction'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor-requests/document/{request_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor-requests/admin/monitor`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': False}, {'name': 'supervisor_id', 'required': False}, {'name': 'status_filter', 'required': False}, {'name': 'from_date', 'required': False}, {'name': 'to_date', 'required': False}]`. 
- `GET /api/v1/supervisor-requests/coordinator/monitor`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': False}, {'name': 'supervisor_id', 'required': False}, {'name': 'status_filter', 'required': False}, {'name': 'from_date', 'required': False}, {'name': 'to_date', 'required': False}]`. 
- `GET /api/v1/supervisor-requests/detail/{request_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposals/cycles`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposals/supervisors`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': True}]`. 
- `GET /api/v1/proposals/mine`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposals`: body `<class 'fastapi._compat.v2.Body_create_request_api_v1_proposals_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposals/draft/{request_id}/document`: body `<class 'fastapi._compat.v2.Body_update_draft_document_api_v1_proposals_draft__request_id__document_post'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposals/{request_id}/confirm`: body `<class 'app.supervisor_requests.RevisionAction'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposals/{request_id}/submit`: body `<class 'app.supervisor_requests.RevisionAction'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposals/{request_id}/withdraw`: body `<class 'app.supervisor_requests.RevisionAction'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposals/{request_id}/decision`: body `<class 'app.supervisor_requests.DecisionAction'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposals/document/{request_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/proposals/admin/monitor`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': False}, {'name': 'supervisor_id', 'required': False}, {'name': 'status_filter', 'required': False}, {'name': 'from_date', 'required': False}, {'name': 'to_date', 'required': False}]`. 
- `GET /api/v1/proposals/coordinator/monitor`: body `None`; response `None`; query parameters `[{'name': 'academic_cycle_id', 'required': False}, {'name': 'supervisor_id', 'required': False}, {'name': 'status_filter', 'required': False}, {'name': 'from_date', 'required': False}, {'name': 'to_date', 'required': False}]`. 
- `GET /api/v1/proposals/{request_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/proposals/{request_id}/ai-review`: body `None`; response `<class 'app.supervisor_requests.ProposalAIReviewResponse'>`; query parameters `[]`. 
- `GET /api/v1/proposals/{request_id}/ai-review`: body `None`; response `None`; query parameters `[]`. 

## backend/app/supervisor_workspace.py

| Method | API path | Handler / line | Dependency guards |
|---|---|---|---|
| GET | `/api/v1/supervisor/assigned-groups` | `assigned_groups` line 88 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/groups/{group_id}` | `group_detail` line 94 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/groups/{group_id}/progress` | `group_section` line 100 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/groups/{group_id}/documents` | `group_section` line 100 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/groups/{group_id}/project` | `group_section` line 100 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/groups/{group_id}/proposal` | `group_section` line 100 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/groups/{group_id}/members` | `group_section` line 100 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/requests` | `requests` line 109 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/requests/{request_id}` | `request_detail` line 115 | role_guard: SUPERVISOR; get_current_user; get_db |
| POST | `/api/v1/supervisor/requests/{request_id}/request-changes` | `decision` line 130 | role_guard: SUPERVISOR; get_current_user; get_db |
| POST | `/api/v1/supervisor/requests/{request_id}/reject` | `decision` line 130 | role_guard: SUPERVISOR; get_current_user; get_db |
| POST | `/api/v1/supervisor/requests/{request_id}/accept` | `decision` line 130 | role_guard: SUPERVISOR; get_current_user; get_db |
| GET | `/api/v1/supervisor/groups/{group_id}/conversation` | `conversation` line 146 | role_guard: SUPERVISOR; get_current_user; get_db |
| POST | `/api/v1/supervisor/groups/{group_id}/conversation` | `send_message` line 152 | role_guard: SUPERVISOR; get_current_user; get_db |
- `GET /api/v1/supervisor/assigned-groups`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/groups/{group_id}`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/groups/{group_id}/progress`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/groups/{group_id}/documents`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/groups/{group_id}/project`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/groups/{group_id}/proposal`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/groups/{group_id}/members`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/requests`: body `None`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/requests/{request_id}`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor/requests/{request_id}/request-changes`: body `<class 'app.supervisor_workspace.DecisionInput'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor/requests/{request_id}/reject`: body `<class 'app.supervisor_workspace.DecisionInput'>`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor/requests/{request_id}/accept`: body `<class 'app.supervisor_workspace.DecisionInput'>`; response `None`; query parameters `[]`. 
- `GET /api/v1/supervisor/groups/{group_id}/conversation`: body `None`; response `None`; query parameters `[]`. 
- `POST /api/v1/supervisor/groups/{group_id}/conversation`: body `<class 'app.collaboration_channels.MessageWrite'>`; response `None`; query parameters `[]`. 

# Appendix D — Complete source-file navigation atlas
Every discovered application, migration, test and script source file is listed below. Line numbers refer to this snapshot. Frontend reachability means an import path exists from main.tsx; a reachable module may still have conditional or inaccessible branches. A file not reachable through static relative imports is an alternative/helper candidate, not automatically safe to delete.

## backend/app/__init__.py
Lines: 1. FYPHub backend application package.

## backend/app/academic_cycle_overview.py
Lines: 115. Authorized, read-only academic-cycle dashboard aggregation.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_user` | 31 | Implementation entry; inspect this symbol for details |
| `cycle_overview` | 38 | Implementation entry; inspect this symbol for details |

## backend/app/agent_supervision.py
Lines: 101. Controlled supervision-agent planning and approval workflow.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `Approval` | 17 | Implementation entry; inspect this symbol for details |
| `_team` | 21 | Implementation entry; inspect this symbol for details |
| `_access` | 26 | Implementation entry; inspect this symbol for details |
| `_out` | 34 | Implementation entry; inspect this symbol for details |
| `_accepted_proposal` | 37 | Implementation entry; inspect this symbol for details |
| `start_run` | 41 | Implementation entry; inspect this symbol for details |
| `list_runs` | 60 | Implementation entry; inspect this symbol for details |
| `approve_run` | 64 | Implementation entry; inspect this symbol for details |
| `execute_run` | 72 | Implementation entry; inspect this symbol for details |
| `approve_reminder` | 93 | Implementation entry; inspect this symbol for details |

## backend/app/ai_provider.py
Lines: 129. Backend-only, schema-validated advisory AI clients with deterministic fallback.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalReviewFinding` | 12 | Implementation entry; inspect this symbol for details |
| `ProposalProviderPayload` | 23 | Implementation entry; inspect this symbol for details |
| `PlanItem` | 36 | Implementation entry; inspect this symbol for details |
| `PlanMilestone` | 39 | Implementation entry; inspect this symbol for details |
| `SupervisionPlanPayload` | 42 | Implementation entry; inspect this symbol for details |
| `provider_config` | 45 | Implementation entry; inspect this symbol for details |
| `validate_provider_configuration` | 48 | Implementation entry; inspect this symbol for details |
| `_allowed` | 60 | Implementation entry; inspect this symbol for details |
| `_run_ai_json_once` | 64 | Implementation entry; inspect this symbol for details |
| `run_ai_json` | 120 | Implementation entry; inspect this symbol for details |
| `run_groq_json` | 128 | Implementation entry; inspect this symbol for details |

## backend/app/archived_projects.py
Lines: 1108. Authorized logical FYP archive management and deterministic knowledge search.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_cell_text` | 31 | Implementation entry; inspect this symbol for details |
| `_clean_cell` | 38 | Return only literal cell content; discard formulas and Excel errors. |
| `_is_email_value` | 50 | Implementation entry; inspect this symbol for details |
| `_last_content_row` | 54 | Find the true end of a worksheet, preferring the last literal email row. |
| `_xls_value` | 80 | Implementation entry; inspect this symbol for details |
| `parse_archive_workbook` | 90 | Extract every populated column without imposing an archive schema. |
| `_column_token` | 175 | Implementation entry; inspect this symbol for details |
| `_mapped_value` | 179 | Implementation entry; inspect this symbol for details |
| `_project_title` | 196 | Read a project title only from an explicit project-title column. |
| `_column_values` | 218 | Implementation entry; inspect this symbol for details |
| `_member_rows` | 228 | Extract member data from one source row without treating it as a project. |
| `_same_member` | 258 | Implementation entry; inspect this symbol for details |
| `_merge_member_values` | 266 | Implementation entry; inspect this symbol for details |
| `_first_non_empty` | 282 | Implementation entry; inspect this symbol for details |
| `_unique_text` | 290 | Implementation entry; inspect this symbol for details |
| `_import_display` | 302 | Implementation entry; inspect this symbol for details |
| `_apply_imported_cells` | 308 | Apply an edited imported row while preserving its original Excel columns. |
| `_archive_import_project` | 352 | Build one archive parent from one Excel row. |
| `_resolved_import_rows` | 395 | Forward-fill merged Excel cells and return rows plus safe orphan rows. |
| `_merge_source_cells` | 443 | Preserve all original columns while exposing a single editable value per key. |
| `_group_mapped_value` | 462 | Implementation entry; inspect this symbol for details |
| `_import_row_errors` | 466 | Implementation entry; inspect this symbol for details |
| `_archive_import_group` | 476 | Create one parent archive entity for all rows sharing one safe key. |
| `_import_group_key` | 526 | Implementation entry; inspect this symbol for details |
| `_merge_imported_project` | 533 | Merge one grouped import into an existing project without overwriting data. |
| `normalize_title` | 557 | Implementation entry; inspect this symbol for details |
| `clean_filename` | 561 | Implementation entry; inspect this symbol for details |
| `ArchiveCreate` | 567 | Implementation entry; inspect this symbol for details |
| `ArchiveUpdate` | 593 | Implementation entry; inspect this symbol for details |
| `_error` | 617 | Implementation entry; inspect this symbol for details |
| `_audit` | 621 | Implementation entry; inspect this symbol for details |
| `_document_out` | 627 | Implementation entry; inspect this symbol for details |
| `_project_out` | 631 | Implementation entry; inspect this symbol for details |
| `_active_project` | 642 | Implementation entry; inspect this symbol for details |
| `_metadata_snapshot` | 649 | Implementation entry; inspect this symbol for details |
| `_validate_document` | 653 | Implementation entry; inspect this symbol for details |
| `_next_version` | 663 | Implementation entry; inspect this symbol for details |
| `search_archives` | 669 | Implementation entry; inspect this symbol for details |
| `admin_archive_list` | 724 | Implementation entry; inspect this symbol for details |
| `admin_archive_detail` | 729 | Implementation entry; inspect this symbol for details |
| `read_archive` | 737 | Implementation entry; inspect this symbol for details |
| `read_archive_document` | 742 | Implementation entry; inspect this symbol for details |
| `create_archive` | 755 | Implementation entry; inspect this symbol for details |
| `update_archive` | 771 | Implementation entry; inspect this symbol for details |
| `delete_archive` | 805 | Permanently remove an archive record and all of its stored document versions. |
| `rollback_archive_metadata` | 824 | Implementation entry; inspect this symbol for details |
| `set_archive_active` | 846 | Implementation entry; inspect this symbol for details |
| `upload_archive_document` | 858 | Implementation entry; inspect this symbol for details |
| `archive_document_history` | 879 | Implementation entry; inspect this symbol for details |
| `delete_archive_document` | 887 | Implementation entry; inspect this symbol for details |
| `_read_archive_upload` | 903 | Implementation entry; inspect this symbol for details |
| `archive_import_preview` | 910 | Implementation entry; inspect this symbol for details |
| `archive_import_confirm` | 919 | Implementation entry; inspect this symbol for details |
| `admin_archive_projects` | 1007 | Implementation entry; inspect this symbol for details |
| `repair_imported_archive` | 1030 | Safely consolidate obvious duplicate imported parents. |
| `admin_archive_project` | 1068 | Implementation entry; inspect this symbol for details |
| `admin_update_archive` | 1075 | Implementation entry; inspect this symbol for details |
| `admin_delete_archive` | 1080 | Implementation entry; inspect this symbol for details |
| `archive_import_batches` | 1085 | Implementation entry; inspect this symbol for details |
| `archive_import_batch_detail` | 1092 | Implementation entry; inspect this symbol for details |
| `set_archive_visibility` | 1100 | Implementation entry; inspect this symbol for details |

## backend/app/audit_history.py
Lines: 119. Read-only, allowlisted administrator audit history.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `scalar` | 54 | Implementation entry; inspect this symbol for details |
| `safe_changes` | 57 | Implementation entry; inspect this symbol for details |
| `output` | 74 | Implementation entry; inspect this symbol for details |
| `parse_time` | 77 | Implementation entry; inspect this symbol for details |
| `list_events` | 89 | Implementation entry; inspect this symbol for details |
| `event_detail` | 113 | Implementation entry; inspect this symbol for details |

## backend/app/auth.py
Lines: 203. Reusable cookie-session authentication dependencies and helpers.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `log_temporary_auth_diagnostic` | 31 | TEMPORARY: emit safe metadata while diagnosing post-login access failures. |
| `utc_now` | 46 | Implementation entry; inspect this symbol for details |
| `authentication_error` | 50 | Implementation entry; inspect this symbol for details |
| `validate_mutating_origin` | 54 | Allow same-origin/non-browser calls, but reject a supplied foreign browser Origin. |
| `session_cookie_secure` | 67 | Mark session cookies Secure exactly when the request is served over HTTPS. |
| `set_session_cookie` | 72 | Implementation entry; inspect this symbol for details |
| `clear_session_cookie` | 84 | Implementation entry; inspect this symbol for details |
| `get_current_user` | 94 | Resolve an active user through a current, non-revoked hashed cookie session. |
| `require_roles` | 176 | Create a dependency that permits only the listed roles after authentication. |

## backend/app/collaboration_channels.py
Lines: 137. Private assignment-scoped Module 2 collaboration channels.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `MessageWrite` | 15 | Implementation entry; inspect this symbol for details |
| `_active_channel` | 28 | Implementation entry; inspect this symbol for details |
| `_student_member` | 35 | Implementation entry; inspect this symbol for details |
| `_authorize` | 41 | Implementation entry; inspect this symbol for details |
| `_accepted_request` | 56 | Implementation entry; inspect this symbol for details |
| `ensure_collaboration_channel` | 60 | Implementation entry; inspect this symbol for details |
| `_channel_out` | 81 | Implementation entry; inspect this symbol for details |
| `_message_out` | 91 | Implementation entry; inspect this symbol for details |
| `_list_channels` | 96 | Implementation entry; inspect this symbol for details |
| `student_channels` | 106 | Implementation entry; inspect this symbol for details |
| `supervisor_channels` | 111 | Implementation entry; inspect this symbol for details |
| `collaboration_channel` | 117 | Implementation entry; inspect this symbol for details |
| `collaboration_messages` | 124 | Implementation entry; inspect this symbol for details |
| `send_collaboration_message` | 132 | Implementation entry; inspect this symbol for details |

## backend/app/config.py
Lines: 103. Configuration for the FYPHub backend.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `Settings` | 15 | Implementation entry; inspect this symbol for details |
| `get_settings` | 59 | Implementation entry; inspect this symbol for details |

## backend/app/coordinator_operations.py
Lines: 81. Read-only operational data exposed specifically to coordinators.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `supervisor_capacity` | 16 | Implementation entry; inspect this symbol for details |
| `audit_history` | 53 | Implementation entry; inspect this symbol for details |
| `proposal_templates` | 66 | Implementation entry; inspect this symbol for details |
| `evaluation_criteria` | 78 | Implementation entry; inspect this symbol for details |

## backend/app/dashboard_requirements.py
Lines: 71. Role-scoped deadlines and requirements for all dashboards.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_status` | 13 | Implementation entry; inspect this symbol for details |
| `_due_source` | 19 | Implementation entry; inspect this symbol for details |
| `_out` | 25 | Implementation entry; inspect this symbol for details |
| `_visible` | 29 | Implementation entry; inspect this symbol for details |
| `dashboard_requirements` | 36 | Implementation entry; inspect this symbol for details |
| `dashboard_summary` | 43 | Implementation entry; inspect this symbol for details |
| `create_requirement` | 48 | Implementation entry; inspect this symbol for details |
| `update_requirement` | 57 | Implementation entry; inspect this symbol for details |
| `delete_requirement` | 66 | Implementation entry; inspect this symbol for details |

## backend/app/database.py
Lines: 36. Synchronous SQLAlchemy database resources.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `Base` | 11 | Shared declarative base for future application models. |
| `get_db` | 30 | Provide a request-scoped session that is always closed. |

## backend/app/document_requirements.py
Lines: 303. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_audit` | 25 | Implementation entry; inspect this symbol for details |
| `_student_cycle_ids` | 29 | Resolve the student's current cycle without trusting a client-supplied cycle. |
| `_student_team_ids` | 43 | Implementation entry; inspect this symbol for details |
| `_student_group` | 52 | Implementation entry; inspect this symbol for details |
| `_current_active_cycle_id` | 56 | Implementation entry; inspect this symbol for details |
| `_visible` | 60 | Implementation entry; inspect this symbol for details |
| `_out` | 74 | Implementation entry; inspect this symbol for details |
| `_now` | 79 | Implementation entry; inspect this symbol for details |
| `_stored_path` | 80 | Implementation entry; inspect this symbol for details |
| `create_requirement` | 88 | Implementation entry; inspect this symbol for details |
| `delete_requirement` | 113 | Remove an unused draft requirement while preserving published/history records. |
| `list_requirements` | 133 | Implementation entry; inspect this symbol for details |
| `get_requirement` | 139 | Implementation entry; inspect this symbol for details |
| `update_requirement` | 146 | Implementation entry; inspect this symbol for details |
| `_state` | 153 | Implementation entry; inspect this symbol for details |
| `publish` | 163 | Implementation entry; inspect this symbol for details |
| `unpublish` | 165 | Implementation entry; inspect this symbol for details |
| `close` | 167 | Implementation entry; inspect this symbol for details |
| `archive` | 169 | Implementation entry; inspect this symbol for details |
| `reopen` | 171 | Implementation entry; inspect this symbol for details |
| `_submission` | 173 | Implementation entry; inspect this symbol for details |
| `_validate` | 184 | Implementation entry; inspect this symbol for details |
| `_submission_out` | 206 | Implementation entry; inspect this symbol for details |
| `student_requirements` | 213 | Implementation entry; inspect this symbol for details |
| `upload` | 219 | Implementation entry; inspect this symbol for details |
| `submission` | 248 | Implementation entry; inspect this symbol for details |
| `all_submissions` | 255 | Return every student's submission and every uploaded version for an admin requirement view. |
| `versions` | 274 | Implementation entry; inspect this symbol for details |
| `download` | 280 | Implementation entry; inspect this symbol for details |
| `_review` | 292 | Implementation entry; inspect this symbol for details |
| `approve` | 299 | Implementation entry; inspect this symbol for details |
| `reject` | 301 | Implementation entry; inspect this symbol for details |
| `replacement` | 303 | Implementation entry; inspect this symbol for details |

## backend/app/evaluations.py
Lines: 495. Role-scoped FYP evaluation, marks, audit, reporting, and result APIs.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_error` | 56 | Implementation entry; inspect this symbol for details |
| `_role_categories` | 60 | Implementation entry; inspect this symbol for details |
| `_target_group_ids` | 70 | Implementation entry; inspect this symbol for details |
| `_panel_can_access` | 82 | Implementation entry; inspect this symbol for details |
| `_actor_can_access_group` | 90 | Implementation entry; inspect this symbol for details |
| `_record_target` | 100 | Implementation entry; inspect this symbol for details |
| `_record_out` | 104 | Implementation entry; inspect this symbol for details |
| `_audit` | 108 | Implementation entry; inspect this symbol for details |
| `_validate_category_owner` | 112 | Implementation entry; inspect this symbol for details |
| `_resolve_target` | 117 | Implementation entry; inspect this symbol for details |
| `_target_filter` | 132 | Implementation entry; inspect this symbol for details |
| `_assignment_out` | 136 | Implementation entry; inspect this symbol for details |
| `evaluation_assignments` | 142 | Implementation entry; inspect this symbol for details |
| `my_evaluations` | 149 | Implementation entry; inspect this symbol for details |
| `_save_record` | 163 | Implementation entry; inspect this symbol for details |
| `create_evaluation` | 201 | Implementation entry; inspect this symbol for details |
| `update_evaluation` | 217 | Implementation entry; inspect this symbol for details |
| `submit_evaluation` | 233 | Implementation entry; inspect this symbol for details |
| `return_evaluation` | 254 | Implementation entry; inspect this symbol for details |
| `approve_evaluation` | 272 | Implementation entry; inspect this symbol for details |
| `correct_evaluation` | 288 | Implementation entry; inspect this symbol for details |
| `publish_evaluation` | 310 | Implementation entry; inspect this symbol for details |
| `evaluation_audit` | 326 | Implementation entry; inspect this symbol for details |
| `admin_evaluations` | 337 | Implementation entry; inspect this symbol for details |
| `list_aggregation` | 349 | Implementation entry; inspect this symbol for details |
| `update_aggregation` | 360 | Implementation entry; inspect this symbol for details |
| `_student_group` | 377 | Implementation entry; inspect this symbol for details |
| `_aggregation_method` | 381 | Implementation entry; inspect this symbol for details |
| `_category_result` | 386 | Implementation entry; inspect this symbol for details |
| `_grade` | 408 | Implementation entry; inspect this symbol for details |
| `_result` | 421 | Implementation entry; inspect this symbol for details |
| `student_results` | 431 | Implementation entry; inspect this symbol for details |
| `admin_group_results` | 436 | Implementation entry; inspect this symbol for details |
| `admin_results` | 446 | Implementation entry; inspect this symbol for details |
| `_report_lines` | 453 | Implementation entry; inspect this symbol for details |
| `_simple_pdf` | 465 | Implementation entry; inspect this symbol for details |
| `evaluation_report` | 477 | Implementation entry; inspect this symbol for details |
| `evaluation_report_pdf` | 488 | Implementation entry; inspect this symbol for details |

## backend/app/group_ai.py
Lines: 105. Team-scoped, advisory local Ollama chat.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `NoRedirect` | 17 | Implementation entry; inspect this symbol for details |
| `require_team` | 21 | Implementation entry; inspect this symbol for details |
| `scoped_context` | 28 | Implementation entry; inspect this symbol for details |
| `unavailable` | 42 | Implementation entry; inspect this symbol for details |
| `generate` | 45 | Implementation entry; inspect this symbol for details |
| `history` | 85 | Implementation entry; inspect this symbol for details |
| `chat` | 92 | Implementation entry; inspect this symbol for details |

## backend/app/group_channels.py
Lines: 118. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `Channel` | 16 | Implementation entry; inspect this symbol for details |
| `MessageWrite` | 24 | Implementation entry; inspect this symbol for details |
| `permission` | 36 | Implementation entry; inspect this symbol for details |
| `output` | 50 | Implementation entry; inspect this symbol for details |
| `_file_path` | 54 | Implementation entry; inspect this symbol for details |
| `teams` | 58 | Implementation entry; inspect this symbol for details |
| `history` | 67 | Implementation entry; inspect this symbol for details |
| `send` | 74 | Implementation entry; inspect this symbol for details |
| `upload_file` | 93 | Store a team-scoped resource and publish it into Files & Resources. |
| `download_file` | 113 | Implementation entry; inspect this symbol for details |

## backend/app/main.py
Lines: 2188. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_workflow_name` | 61 | Implementation entry; inspect this symbol for details |
| `StructuredRequestLoggingMiddleware` | 69 | Implementation entry; inspect this symbol for details |
| `request_validation_error` | 106 | Expose consistent, field-addressable request validation failures. |
| `registration_error` | 125 | Return a public, structured error without database implementation details. |
| `normalize_team_member` | 135 | Apply the established identifier conventions and field-length rules. |
| `list_cycles` | 169 | Implementation entry; inspect this symbol for details |
| `get_group_policy` | 173 | Implementation entry; inspect this symbol for details |
| `cycle_error` | 180 | Implementation entry; inspect this symbol for details |
| `locked_cycle_and_policy` | 184 | Use the same cycle-then-policy lock order as team registration. |
| `largest_active_team_size` | 193 | Implementation entry; inspect this symbol for details |
| `deadline_error` | 198 | Implementation entry; inspect this symbol for details |
| `formatted_utc_offset` | 202 | Implementation entry; inspect this symbol for details |
| `require_timezone_data` | 209 | Implementation entry; inspect this symbol for details |
| `resolve_deadline_time` | 216 | Resolve a wall time without guessing a zone, gap, or overlapping offset. |
| `deadline_version_out` | 243 | Implementation entry; inspect this symbol for details |
| `deadline_detail_out` | 263 | Implementation entry; inspect this symbol for details |
| `validate_deadline_write` | 279 | Implementation entry; inspect this symbol for details |
| `save_deadline_version` | 287 | Implementation entry; inspect this symbol for details |
| `list_time_zones` | 321 | Implementation entry; inspect this symbol for details |
| `preview_academic_deadline` | 327 | Implementation entry; inspect this symbol for details |
| `list_academic_deadlines` | 338 | Implementation entry; inspect this symbol for details |
| `academic_deadline_detail` | 373 | Implementation entry; inspect this symbol for details |
| `create_academic_deadline` | 385 | Implementation entry; inspect this symbol for details |
| `create_academic_deadline_version` | 415 | Implementation entry; inspect this symbol for details |
| `delete_academic_deadline` | 447 | Remove a deadline and its recorded versions when no rule references it. |
| `list_template_references` | 478 | Implementation entry; inspect this symbol for details |
| `template_reference_detail` | 488 | Implementation entry; inspect this symbol for details |
| `create_template_reference` | 517 | Implementation entry; inspect this symbol for details |
| `create_template_version` | 541 | Implementation entry; inspect this symbol for details |
| `create_rule_version` | 548 | Implementation entry; inspect this symbol for details |
| `delete_template_reference_version` | 557 | Implementation entry; inspect this symbol for details |
| `rubric_version_out` | 575 | Implementation entry; inspect this symbol for details |
| `rubric_detail_out` | 594 | Implementation entry; inspect this symbol for details |
| `save_rubric_version` | 607 | Implementation entry; inspect this symbol for details |
| `list_evaluation_rubrics` | 651 | Implementation entry; inspect this symbol for details |
| `evaluation_rubric_detail` | 686 | Implementation entry; inspect this symbol for details |
| `create_evaluation_rubric` | 698 | Implementation entry; inspect this symbol for details |
| `create_evaluation_rubric_version` | 722 | Implementation entry; inspect this symbol for details |
| `create_cycle` | 759 | Implementation entry; inspect this symbol for details |
| `update_cycle` | 776 | Implementation entry; inspect this symbol for details |
| `delete_cycle` | 796 | Implementation entry; inspect this symbol for details |
| `set_group_policy` | 815 | Implementation entry; inspect this symbol for details |
| `delete_group_policy` | 834 | Implementation entry; inspect this symbol for details |
| `health` | 850 | Report application liveness only; this does not check database connectivity. |
| `readiness` | 856 | Report readiness only when the database and vector extension are available. |
| `login` | 880 | Authenticate an active account and issue a new opaque cookie session. |
| `account_response` | 950 | Return an account principal and, for students, its shared group context. |
| `current_user` | 1004 | Return the authenticated active account's safe fields. |
| `admin_current_user` | 1019 | Return the current account only when its persisted role is ADMIN. |
| `admin_registration_mode` | 1038 | Expose demo-mode status only to authenticated administrators. |
| `admin_user_error` | 1049 | Return a safe management failure without leaking persistence details. |
| `add_admin_audit_event` | 1054 | Append only non-sensitive account metadata; never credentials or sessions. |
| `shared_team_account` | 1068 | Implementation entry; inspect this symbol for details |
| `lock_and_protect_last_active_admin` | 1072 | Serialize changes that could remove the final active ADMIN account. |
| `revoke_user_sessions` | 1089 | Implementation entry; inspect this symbol for details |
| `supervisor_capacity_counts` | 1097 | Implementation entry; inspect this symbol for details |
| `supervisor_capacity_out` | 1119 | Implementation entry; inspect this symbol for details |
| `locked_eligible_supervisor_and_cycle` | 1159 | Lock eligibility records so role/status changes cannot race capacity writes. |
| `locked_eligible_supervisor_and_period` | 1172 | Lock an active supervisor before changing annual capacity. |
| `assigned_groups_for_period` | 1182 | Implementation entry; inspect this symbol for details |
| `list_admin_users` | 1187 | Implementation entry; inspect this symbol for details |
| `create_admin_user` | 1217 | Implementation entry; inspect this symbol for details |
| `change_admin_user_status` | 1250 | Implementation entry; inspect this symbol for details |
| `change_admin_user_role` | 1286 | Implementation entry; inspect this symbol for details |
| `delete_admin_user` | 1328 | Permanently remove an unused account; linked records stay protected by FK guards. |
| `list_supervisor_capacities` | 1358 | Implementation entry; inspect this symbol for details |
| `supervisor_capacity_workspace` | 1368 | Return the signed-in supervisor's read-only annual capacity and assignment detail. |
| `read_supervisor_capacity` | 1410 | Implementation entry; inspect this symbol for details |
| `create_supervisor_capacity` | 1420 | Implementation entry; inspect this symbol for details |
| `update_supervisor_capacity` | 1454 | Implementation entry; inspect this symbol for details |
| `delete_supervisor_capacity` | 1492 | Implementation entry; inspect this symbol for details |
| `logout` | 1523 | Revoke the presented session when present and always clear its browser cookie. |
| `register_student` | 1548 | Reject the retired individual public signup flow. |
| `register_team` | 1568 | Atomically create one shared student account, team, and member contacts. |
| `register_student_group` | 1823 | Create one shared STUDENT group account from member contacts only. |
| `student_group_detail` | 1852 | Serialize the shared student principal without exposing credentials. |
| `current_student_team` | 1893 | Implementation entry; inspect this symbol for details |
| `student_group_me` | 1912 | Implementation entry; inspect this symbol for details |
| `student_group_members` | 1920 | Implementation entry; inspect this symbol for details |
| `list_student_groups` | 1929 | Implementation entry; inspect this symbol for details |
| `get_student_group` | 1946 | Implementation entry; inspect this symbol for details |
| `set_student_group_status` | 1957 | Implementation entry; inspect this symbol for details |
| `activate_student_group` | 1979 | Implementation entry; inspect this symbol for details |
| `deactivate_student_group` | 1984 | Implementation entry; inspect this symbol for details |
| `delete_student_group` | 1989 | Implementation entry; inspect this symbol for details |
| `reminder_calculation` | 2015 | Implementation entry; inspect this symbol for details |
| `reminder_version_out` | 2037 | Implementation entry; inspect this symbol for details |
| `reminder_detail` | 2042 | Implementation entry; inspect this symbol for details |
| `save_reminder_version` | 2048 | Implementation entry; inspect this symbol for details |
| `preview_reminder_rule` | 2058 | Implementation entry; inspect this symbol for details |
| `list_reminder_rules` | 2064 | Implementation entry; inspect this symbol for details |
| `read_reminder_rule` | 2074 | Implementation entry; inspect this symbol for details |
| `create_reminder_rule` | 2082 | Implementation entry; inspect this symbol for details |
| `create_reminder_rule_version` | 2104 | Implementation entry; inspect this symbol for details |
| `delete_reminder_rule` | 2127 | Implementation entry; inspect this symbol for details |

## backend/app/models/__init__.py
Lines: 34. Application SQLAlchemy models.

## backend/app/models/academic.py
Lines: 54. 
Tables declared: academic_cycles, academic_group_policies, supervisor_capacity_policies.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AcademicCycle` | 6 | Implementation entry; inspect this symbol for details |
| `AcademicGroupPolicy` | 23 | Implementation entry; inspect this symbol for details |
| `SupervisorCapacityPolicy` | 39 | Implementation entry; inspect this symbol for details |

## backend/app/models/academic_deadline.py
Lines: 39. Non-operational academic deadline configuration models.
Tables declared: academic_deadlines, academic_deadline_versions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AcademicDeadline` | 11 | Stable deadline identity fixed to one academic cycle. |
| `AcademicDeadlineVersion` | 22 | An immutable recorded deadline configuration. |

## backend/app/models/agent_supervision.py
Lines: 25. Controlled, append-only supervision-agent run records.
Tables declared: supervision_agent_runs.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisionAgentRun` | 9 | Implementation entry; inspect this symbol for details |

## backend/app/models/archive_import_batch.py
Lines: 22. Import history for administrator archive workbook uploads.
Tables declared: archive_import_batches.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ArchiveImportBatch` | 11 | Implementation entry; inspect this symbol for details |

## backend/app/models/archived_project.py
Lines: 102. Logical FYP archive records and immutable document versions.
Tables declared: archived_projects, archived_project_documents.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ArchivedProjectDocumentType` | 13 | Implementation entry; inspect this symbol for details |
| `ArchivedProject` | 26 | Implementation entry; inspect this symbol for details |
| `ArchivedProjectDocument` | 83 | Implementation entry; inspect this symbol for details |

## backend/app/models/audit_event.py
Lines: 31. Append-only audit records for administrator account mutations.
Tables declared: admin_audit_events.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminAuditEvent` | 13 | A safe, immutable record of one successful administrator account mutation. |

## backend/app/models/auth_session.py
Lines: 27. Persistent, hash-only browser authentication sessions.
Tables declared: auth_sessions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AuthSession` | 11 | An opaque browser session. The raw bearer token is never stored. |

## backend/app/models/dashboard_requirement.py
Lines: 29. Role-scoped dashboard deadline and requirement records.
Tables declared: dashboard_requirements.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `DashboardRequirement` | 8 | Implementation entry; inspect this symbol for details |

## backend/app/models/document_requirement.py
Lines: 59. 
Tables declared: document_upload_requirements, document_submissions, document_submission_versions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `DocumentUploadRequirement` | 7 | Implementation entry; inspect this symbol for details |
| `DocumentSubmission` | 29 | Implementation entry; inspect this symbol for details |
| `DocumentSubmissionVersion` | 46 | Implementation entry; inspect this symbol for details |

## backend/app/models/evaluation.py
Lines: 100. Persisted role-owned FYP evaluation records and result audit history.
Tables declared: evaluation_records, evaluation_audit_events, evaluation_corrections, evaluation_aggregation_configs.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluationRecord` | 12 | Implementation entry; inspect this symbol for details |
| `EvaluationAuditEvent` | 58 | Implementation entry; inspect this symbol for details |
| `EvaluationCorrection` | 73 | Implementation entry; inspect this symbol for details |
| `EvaluationAggregationConfig` | 86 | Implementation entry; inspect this symbol for details |

## backend/app/models/evaluation_rubric.py
Lines: 53. Draft evaluation-rubric configuration models.
Tables declared: evaluation_rubrics, evaluation_rubric_versions, evaluation_rubric_criteria.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluationRubric` | 11 | Stable identity shared by every immutable draft version. |
| `EvaluationRubricVersion` | 21 | A complete immutable snapshot of one draft rubric. |
| `EvaluationRubricCriterion` | 40 | An ordered criterion belonging exclusively to one rubric version. |

## backend/app/models/group_message.py
Lines: 19. 
Tables declared: group_messages.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `GroupMessage` | 6 | Implementation entry; inspect this symbol for details |

## backend/app/models/module2_collaboration.py
Lines: 83. Module 2 collaboration records: notifications, channel reads and moderation.
Tables declared: module2_notifications, module2_channel_reads, module2_chatbot_sessions, collaboration_channels, collaboration_participants, collaboration_messages.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `Module2Notification` | 8 | Implementation entry; inspect this symbol for details |
| `Module2ChannelRead` | 19 | Implementation entry; inspect this symbol for details |
| `Module2ChatbotSession` | 30 | Implementation entry; inspect this symbol for details |
| `CollaborationChannel` | 41 | Implementation entry; inspect this symbol for details |
| `CollaborationParticipant` | 58 | Implementation entry; inspect this symbol for details |
| `CollaborationMessage` | 73 | Implementation entry; inspect this symbol for details |

## backend/app/models/password_reset_token.py
Lines: 26. Hash-only, short-lived password reset tokens.
Tables declared: password_reset_tokens.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `PasswordResetToken` | 11 | A single-use reset token; the raw bearer value is never persisted. |

## backend/app/models/project_workflow.py
Lines: 131. Persisted project-progress, defense scheduling, and panel-evaluation records.
Tables declared: project_milestones, project_tasks, supervision_meetings, defense_schedules, defense_panel_members, panel_evaluations, panel_evaluation_scores.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProjectMilestone` | 12 | Implementation entry; inspect this symbol for details |
| `ProjectTask` | 30 | Implementation entry; inspect this symbol for details |
| `SupervisionMeeting` | 50 | Implementation entry; inspect this symbol for details |
| `DefenseSchedule` | 65 | Implementation entry; inspect this symbol for details |
| `DefensePanelMember` | 87 | Implementation entry; inspect this symbol for details |
| `PanelEvaluation` | 98 | Implementation entry; inspect this symbol for details |
| `PanelEvaluationScore` | 119 | Implementation entry; inspect this symbol for details |

## backend/app/models/proposal.py
Lines: 28. Non-operational identity and version foundations for proposals.
Tables declared: proposals, proposal_versions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `Proposal` | 8 | Implementation entry; inspect this symbol for details |
| `ProposalVersion` | 18 | Implementation entry; inspect this symbol for details |

## backend/app/models/proposal_ai_review.py
Lines: 24. Persisted advisory proposal AI-review runs.
Tables declared: proposal_ai_review_runs.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalAIReviewRun` | 12 | Implementation entry; inspect this symbol for details |

## backend/app/models/proposal_compliance.py
Lines: 58. Stored Module 3 proposal submissions and compliance report snapshots.
Tables declared: proposal_compliance_submissions, proposal_compliance_reports.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalComplianceSubmission` | 12 | Implementation entry; inspect this symbol for details |
| `ProposalComplianceReport` | 45 | Implementation entry; inspect this symbol for details |

## backend/app/models/proposal_reference.py
Lines: 43. Authorized archived proposal references and separate PDF documents.
Tables declared: proposal_references, proposal_reference_documents.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalReference` | 12 | Implementation entry; inspect this symbol for details |
| `ProposalReferenceDocument` | 32 | Implementation entry; inspect this symbol for details |

## backend/app/models/reminder_rule.py
Lines: 26. Non-operational reminder and escalation rule snapshots.
Tables declared: reminder_rules, reminder_rule_versions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ReminderRule` | 7 | Implementation entry; inspect this symbol for details |
| `ReminderRuleVersion` | 13 | Implementation entry; inspect this symbol for details |

## backend/app/models/supervisor_assignment.py
Lines: 22. 
Tables declared: supervisor_assignments.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorAssignment` | 6 | Implementation entry; inspect this symbol for details |

## backend/app/models/supervisor_request.py
Lines: 149. Student supervisor-selection request records and append-only history.
Tables declared: supervisor_requests, supervisor_request_documents, supervisor_request_status_history, supervisor_request_submission_note_versions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorRequestStatus` | 13 | Implementation entry; inspect this symbol for details |
| `SupervisorRequestExtractionStatus` | 22 | Implementation entry; inspect this symbol for details |
| `SupervisorRequest` | 29 | Implementation entry; inspect this symbol for details |
| `SupervisorRequestDocument` | 85 | Implementation entry; inspect this symbol for details |
| `SupervisorRequestStatusHistory` | 114 | Implementation entry; inspect this symbol for details |
| `SupervisorRequestSubmissionNoteVersion` | 133 | Immutable snapshots of notes submitted with a supervisor request. |

## backend/app/models/supervisor_request_conversation.py
Lines: 19. Append-only messages scoped to one supervisor request.
Tables declared: supervisor_request_messages.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorRequestMessage` | 11 | Implementation entry; inspect this symbol for details |

## backend/app/models/team.py
Lines: 21. 
Tables declared: teams, team_members.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `Team` | 6 | Implementation entry; inspect this symbol for details |
| `TeamMember` | 18 | Implementation entry; inspect this symbol for details |

## backend/app/models/template_reference.py
Lines: 18. 
Tables declared: template_references, template_reference_versions, academic_rule_versions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `TemplateType` | 7 | Implementation entry; inspect this symbol for details |
| `TemplateReference` | 8 | Implementation entry; inspect this symbol for details |
| `TemplateReferenceVersion` | 11 | Implementation entry; inspect this symbol for details |
| `AcademicRuleVersion` | 16 | Implementation entry; inspect this symbol for details |

## backend/app/models/user.py
Lines: 74. User and role database foundation.
Tables declared: users.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `UserRole` | 12 | Implementation entry; inspect this symbol for details |
| `User` | 20 | A future-authentication user record; password hashes only. |

## backend/app/module2_collaboration.py
Lines: 185. Complete Module 2 workspace endpoints and cross-module lifecycle surface.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `team_for_actor` | 16 | Implementation entry; inspect this symbol for details |
| `team_payload` | 37 | Implementation entry; inspect this symbol for details |
| `workspace` | 52 | Implementation entry; inspect this symbol for details |
| `TransferLeadership` | 59 | Implementation entry; inspect this symbol for details |
| `LeaveTeam` | 62 | Implementation entry; inspect this symbol for details |
| `transfer_leadership` | 67 | Implementation entry; inspect this symbol for details |
| `dissolve` | 83 | Implementation entry; inspect this symbol for details |
| `leave_team` | 97 | Implementation entry; inspect this symbol for details |
| `notifications` | 123 | Implementation entry; inspect this symbol for details |
| `mark_notification_read` | 132 | Implementation entry; inspect this symbol for details |
| `mark_channel_read` | 142 | Implementation entry; inspect this symbol for details |
| `unread_counts` | 155 | Implementation entry; inspect this symbol for details |
| `proposal_versions` | 168 | Implementation entry; inspect this symbol for details |
| `tasks` | 175 | Implementation entry; inspect this symbol for details |
| `deadlines` | 182 | Implementation entry; inspect this symbol for details |

## backend/app/modules/__init__.py
Lines: 1. Application feature modules.

## backend/app/modules/module_03_proposal/__init__.py
Lines: 1. Module 3: student proposal and university-template compliance.

## backend/app/modules/module_03_proposal/compliance_engine.py
Lines: 269. Deterministic comparison between a submission and an active template.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_text` | 10 | Implementation entry; inspect this symbol for details |
| `_same` | 14 | Implementation entry; inspect this symbol for details |
| `_status` | 22 | Implementation entry; inspect this symbol for details |
| `_category_status` | 30 | Implementation entry; inspect this symbol for details |
| `_similar_section` | 39 | Implementation entry; inspect this symbol for details |
| `_field_value` | 47 | Implementation entry; inspect this symbol for details |
| `_tokens` | 54 | Implementation entry; inspect this symbol for details |
| `_consistency_item` | 59 | Implementation entry; inspect this symbol for details |
| `build_change_summary` | 88 | Produce a safe, auditable AI-style summary without sending proposal text externally. |
| `build_compliance_report` | 112 | Implementation entry; inspect this symbol for details |
| `_pill` | 240 | Implementation entry; inspect this symbol for details |
| `_category_detail` | 244 | Implementation entry; inspect this symbol for details |
| `_violation` | 252 | Implementation entry; inspect this symbol for details |
| `_section_number` | 267 | Implementation entry; inspect this symbol for details |

## backend/app/modules/module_03_proposal/router.py
Lines: 604. Module 3 APIs: template ingestion, proposal submissions, and reports.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalStatusUpdate` | 35 | Implementation entry; inspect this symbol for details |
| `_error` | 42 | Implementation entry; inspect this symbol for details |
| `_student_team` | 46 | Resolve the existing shared project group for its login or an active member. |
| `_same_group` | 62 | Implementation entry; inspect this symbol for details |
| `_owner_scope` | 66 | Implementation entry; inspect this symbol for details |
| `_safe_filename` | 70 | Implementation entry; inspect this symbol for details |
| `_storage_path` | 75 | Implementation entry; inspect this symbol for details |
| `_template_rules` | 81 | Implementation entry; inspect this symbol for details |
| `_template_out` | 86 | Implementation entry; inspect this symbol for details |
| `_active_template` | 90 | Implementation entry; inspect this symbol for details |
| `_allowed_upload` | 98 | Implementation entry; inspect this symbol for details |
| `_allowed_template_upload` | 103 | Implementation entry; inspect this symbol for details |
| `_detected_headings` | 111 | Implementation entry; inspect this symbol for details |
| `_submission_out` | 135 | Implementation entry; inspect this symbol for details |
| `_version_history` | 141 | Implementation entry; inspect this symbol for details |
| `_can_view` | 164 | Implementation entry; inspect this symbol for details |
| `upload_template` | 185 | Implementation entry; inspect this symbol for details |
| `list_templates` | 226 | Implementation entry; inspect this symbol for details |
| `activate_template` | 232 | Implementation entry; inspect this symbol for details |
| `deactivate_template` | 250 | Stop using a baseline without deleting its immutable version history. |
| `delete_template` | 265 | Delete an unused uploaded template version and its extracted rule snapshot. |
| `save_template_rules` | 284 | Save an admin-confirmed rule review as a new immutable rule snapshot. |
| `submit_proposal` | 320 | Implementation entry; inspect this symbol for details |
| `_run_submission` | 380 | Implementation entry; inspect this symbol for details |
| `submit_draft` | 402 | Implementation entry; inspect this symbol for details |
| `withdraw_submission` | 416 | Withdraw a student-owned draft/submission without deleting its history. |
| `update_submission_status` | 432 | Allow an authorized reviewer to record a lifecycle decision. |
| `my_submissions` | 451 | Implementation entry; inspect this symbol for details |
| `get_submission` | 459 | Implementation entry; inspect this symbol for details |
| `report_queue` | 468 | Implementation entry; inspect this symbol for details |
| `get_report` | 474 | Implementation entry; inspect this symbol for details |
| `rerun_report` | 485 | Explicitly re-run a report against the current active baseline. |
| `get_original` | 498 | Implementation entry; inspect this symbol for details |
| `get_annotated_document` | 509 | Return a safe annotated copy; the student's original file is never modified. |
| `download_report_pdf` | 528 | Implementation entry; inspect this symbol for details |
| `_render_pdf` | 539 | Implementation entry; inspect this symbol for details |
| `_render_annotated_document` | 556 | Annotate each affected page with red issue callouts and append full evidence. |
| `display_value` | 601 | Implementation entry; inspect this symbol for details |

## backend/app/modules/module_03_proposal/template_extractor.py
Lines: 73. Deterministic extraction of measurable template rules.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_sections` | 15 | Implementation entry; inspect this symbol for details |
| `extract_template_rules` | 41 | Return only rules exposed by the uploaded template representation. |

## backend/app/notifications.py
Lines: 31. Authenticated notifications kept outside the retired team-collaboration module.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `notifications` | 15 | Implementation entry; inspect this symbol for details |
| `mark_notification_read` | 24 | Implementation entry; inspect this symbol for details |

## backend/app/password_reset.py
Lines: 213. Secure, enumeration-resistant password recovery endpoints.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_smtp_from` | 36 | Implementation entry; inspect this symbol for details |
| `_smtp_configured` | 40 | Implementation entry; inspect this symbol for details |
| `_development_mode` | 46 | Implementation entry; inspect this symbol for details |
| `_development_or_demo_mode` | 50 | Implementation entry; inspect this symbol for details |
| `_is_valid_email` | 54 | Implementation entry; inspect this symbol for details |
| `_rate_limit_allows` | 62 | Implementation entry; inspect this symbol for details |
| `_send_reset_email` | 75 | Implementation entry; inspect this symbol for details |
| `_audit` | 99 | Implementation entry; inspect this symbol for details |
| `_generic_response` | 112 | Implementation entry; inspect this symbol for details |
| `forgot_password` | 117 | Create a reset token without revealing whether an account exists. |
| `password_reset_status` | 167 | Expose only the non-sensitive delivery mode needed by the local recovery UI. |
| `development_password_reset_link` | 176 | Return a local reset link only when the backend is explicitly in development mode. |
| `reset_password` | 192 | Consume a valid reset token and revoke every existing browser session. |

## backend/app/pdf_extraction.py
Lines: 347. Deterministic, local extraction for supervisor-request PDFs and DOCX files.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_docx_formatting` | 21 | Read measurable formatting from the first DOCX section and its runs. |
| `_pdf_formatting` | 83 | Read measurable page, margin, and typography metadata from a PDF. |
| `PdfExtractionError` | 168 | Implementation entry; inspect this symbol for details |
| `extract_proposal_document` | 175 | Extract proposal fields from PDF, DOCX, or UTF-8 TXT documents. |
| `ExtractionResult` | 229 | Implementation entry; inspect this symbol for details |
| `_field` | 255 | Implementation entry; inspect this symbol for details |
| `_normalize_text` | 261 | Normalize pypdf output while retaining line boundaries used by section parsing. |
| `_heading` | 272 | Implementation entry; inspect this symbol for details |
| `_extract_fields` | 284 | Implementation entry; inspect this symbol for details |
| `extract_one_page_pdf` | 316 | Implementation entry; inspect this symbol for details |

## backend/app/project_workflow.py
Lines: 328. Authorized, persisted project progress, defense scheduling, and evaluation workflows.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `failure` | 34 | Implementation entry; inspect this symbol for details |
| `_utc` | 38 | Implementation entry; inspect this symbol for details |
| `_team` | 42 | Implementation entry; inspect this symbol for details |
| `_is_team_member` | 49 | Implementation entry; inspect this symbol for details |
| `_assigned_supervisor` | 66 | Implementation entry; inspect this symbol for details |
| `_can_access_team` | 70 | Implementation entry; inspect this symbol for details |
| `_require_team_access` | 79 | Implementation entry; inspect this symbol for details |
| `_audit` | 86 | Implementation entry; inspect this symbol for details |
| `_milestone_out` | 92 | Implementation entry; inspect this symbol for details |
| `_task_out` | 96 | Implementation entry; inspect this symbol for details |
| `_health` | 100 | Implementation entry; inspect this symbol for details |
| `project_progress` | 110 | Implementation entry; inspect this symbol for details |
| `create_milestone` | 119 | Implementation entry; inspect this symbol for details |
| `update_milestone` | 128 | Implementation entry; inspect this symbol for details |
| `create_task` | 139 | Implementation entry; inspect this symbol for details |
| `update_task` | 152 | Implementation entry; inspect this symbol for details |
| `list_meetings` | 165 | Implementation entry; inspect this symbol for details |
| `create_meeting` | 172 | Implementation entry; inspect this symbol for details |
| `_schedule_out` | 183 | Implementation entry; inspect this symbol for details |
| `_schedule_access` | 190 | Implementation entry; inspect this symbol for details |
| `_check_schedule_conflicts` | 198 | Implementation entry; inspect this symbol for details |
| `_validate_panel_members` | 221 | Implementation entry; inspect this symbol for details |
| `list_schedules` | 228 | Implementation entry; inspect this symbol for details |
| `schedule_options` | 236 | Implementation entry; inspect this symbol for details |
| `schedule_detail` | 244 | Implementation entry; inspect this symbol for details |
| `create_schedule` | 252 | Implementation entry; inspect this symbol for details |
| `reschedule` | 266 | Implementation entry; inspect this symbol for details |
| `_evaluation_out` | 280 | Implementation entry; inspect this symbol for details |
| `_evaluation_access` | 285 | Implementation entry; inspect this symbol for details |
| `list_evaluations` | 291 | Implementation entry; inspect this symbol for details |
| `save_evaluation` | 299 | Implementation entry; inspect this symbol for details |
| `resolve_evaluation` | 321 | Implementation entry; inspect this symbol for details |

## backend/app/proposal_reference.py
Lines: 90. Authorized, advisory search over archived proposal references.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `normalize_title` | 20 | Normalize case, punctuation, and repeated whitespace for advisory matching. |
| `_similarity` | 25 | Implementation entry; inspect this symbol for details |
| `_result` | 33 | Implementation entry; inspect this symbol for details |
| `search_references` | 50 | Implementation entry; inspect this symbol for details |
| `reference_document` | 78 | Implementation entry; inspect this symbol for details |

## backend/app/registration_policy.py
Lines: 25. Centralized, reversible policy for public registration behavior.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RegistrationMode` | 7 | Implementation entry; inspect this symbol for details |
| `get_registration_mode` | 16 | Return the configured mode, failing closed for missing/invalid values. |
| `registration_mode` | 22 | Read the current process configuration without exposing it publicly. |

## backend/app/schemas/__init__.py
Lines: 1. API request and response schemas.

## backend/app/schemas/academic.py
Lines: 55. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AcademicSession` | 6 | Implementation entry; inspect this symbol for details |
| `CycleOut` | 10 | Implementation entry; inspect this symbol for details |
| `PolicyOut` | 13 | Implementation entry; inspect this symbol for details |
| `CycleCreate` | 16 | Implementation entry; inspect this symbol for details |
| `CycleUpdate` | 28 | Implementation entry; inspect this symbol for details |
| `PolicyUpdate` | 43 | Implementation entry; inspect this symbol for details |

### API contract: CycleOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `code` | `str` | `Required` |
| `display_name` | `str` | `Required` |
| `academic_year` | `int / None` | `None` |
| `session` | `AcademicSession / None` | `None` |
| `registration_open` | `bool` | `Required` |
| `created_at` | `datetime` | `Required` |
| `updated_at` | `datetime` | `Required` |

### API contract: PolicyOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `academic_cycle_id` | `int` | `Required` |
| `max_group_size` | `int` | `Required` |
| `min_group_size` | `int` | `1` |
| `formation_deadline` | `datetime / None` | `None` |
| `matching_weights` | `dict` | `{}` |
| `created_at` | `datetime` | `Required` |
| `updated_at` | `datetime` | `Required` |

### API contract: CycleCreate

| Field | Type | Default / validation declaration |
|---|---|---|
| `academic_year` | `int` | `Required` |
| `session` | `AcademicSession` | `Required` |

### API contract: CycleUpdate

| Field | Type | Default / validation declaration |
|---|---|---|
| `code` | `str / None` | `None` |
| `display_name` | `str / None` | `None` |
| `registration_open` | `bool / None` | `None` |

### API contract: PolicyUpdate

| Field | Type | Default / validation declaration |
|---|---|---|
| `max_group_size` | `int` | `Required` |
| `min_group_size` | `int` | `1` |
| `formation_deadline` | `datetime / None` | `None` |
| `matching_weights` | `dict` | `{}` |

## backend/app/schemas/academic_deadlines.py
Lines: 100. Strict deadline configuration and timezone-preview schemas.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `DeadlinePreviewRequest` | 8 | Implementation entry; inspect this symbol for details |
| `DeadlineWrite` | 34 | Implementation entry; inspect this symbol for details |
| `DeadlineCreate` | 55 | Implementation entry; inspect this symbol for details |
| `DeadlinePreviewOut` | 67 | Implementation entry; inspect this symbol for details |
| `DeadlineVersionOut` | 74 | Implementation entry; inspect this symbol for details |
| `DeadlineDetailOut` | 82 | Implementation entry; inspect this symbol for details |
| `DeadlineListOut` | 90 | Implementation entry; inspect this symbol for details |

### API contract: DeadlinePreviewRequest

| Field | Type | Default / validation declaration |
|---|---|---|
| `local_due_at` | `str` | `Field(min_length=16, max_length=19)` |
| `time_zone` | `str` | `Field(min_length=1, max_length=100)` |
| `utc_offset` | `str / None` | `Field(default=None, pattern='^[+-](?:0\\d/1\\d/2[0-3]):[0-5]\\d$')` |

### API contract: DeadlineWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `name` | `str` | `Field(min_length=1, max_length=160)` |
| `description` | `str / None` | `Field(default=None, max_length=4000)` |
| `due_at_utc` | `datetime` | `Required` |

### API contract: DeadlineCreate

| Field | Type | Default / validation declaration |
|---|---|---|
| `academic_cycle_id` | `int` | `Field(gt=0)` |

### API contract: DeadlinePreviewOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `local_due_at` | `str` | `Required` |
| `time_zone` | `str` | `Required` |
| `utc_offset` | `str` | `Required` |
| `due_at_utc` | `datetime` | `Required` |

### API contract: DeadlineVersionOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `version_number` | `int` | `Required` |
| `name` | `str` | `Required` |
| `description` | `str / None` | `Required` |
| `created_at` | `datetime` | `Required` |

### API contract: DeadlineDetailOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `academic_cycle_id` | `int` | `Required` |
| `academic_cycle_name` | `str` | `Required` |
| `created_at` | `datetime` | `Required` |
| `versions` | `list[DeadlineVersionOut]` | `Required` |

### API contract: DeadlineListOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `academic_cycle_id` | `int` | `Required` |
| `academic_cycle_name` | `str` | `Required` |
| `name` | `str` | `Required` |
| `description` | `str / None` | `Required` |
| `latest_version_number` | `int` | `Required` |
| `due_at_utc` | `datetime` | `Required` |
| `local_due_at` | `str` | `Required` |
| `time_zone` | `str` | `Required` |
| `utc_offset` | `str` | `Required` |

## backend/app/schemas/admin_users.py
Lines: 83. Strict, safe contracts for ADMIN-only account management.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminUserResponse` | 12 | Implementation entry; inspect this symbol for details |
| `AdminUserPage` | 24 | Implementation entry; inspect this symbol for details |
| `AdminUserCreate` | 31 | Implementation entry; inspect this symbol for details |
| `AdminUserRoleChange` | 76 | Implementation entry; inspect this symbol for details |
| `AdminUserStatusChange` | 81 | Implementation entry; inspect this symbol for details |

### API contract: AdminUserResponse

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `full_name` | `str` | `Required` |
| `email` | `str` | `Required` |
| `registration_number` | `str / None` | `Required` |
| `role` | `UserRole` | `Required` |
| `is_active` | `bool` | `Required` |
| `created_at` | `datetime` | `Required` |

### API contract: AdminUserPage

| Field | Type | Default / validation declaration |
|---|---|---|
| `items` | `list[AdminUserResponse]` | `Required` |
| `page` | `int` | `Required` |
| `page_size` | `int` | `Required` |
| `total` | `int` | `Required` |

### API contract: AdminUserCreate

| Field | Type | Default / validation declaration |
|---|---|---|
| `full_name` | `str` | `Required` |
| `email` | `EmailStr` | `Required` |
| `password` | `str` | `Required` |
| `role` | `UserRole` | `Required` |
| `registration_number` | `str / None` | `None` |

### API contract: AdminUserRoleChange

| Field | Type | Default / validation declaration |
|---|---|---|
| `role` | `UserRole` | `Required` |

### API contract: AdminUserStatusChange

| Field | Type | Default / validation declaration |
|---|---|---|
| `is_active` | `bool` | `Required` |

## backend/app/schemas/auth.py
Lines: 100. Schemas for public authentication-related endpoints.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RegistrationRequest` | 12 | Strict public registration input; privileged fields are forbidden. |
| `RegistrationResponse` | 42 | Safe fields returned after a student account is registered. |
| `LoginRequest` | 56 | Strict credentials accepted by the sign-in endpoint. |
| `CurrentUserResponse` | 83 | Safe account data returned after session authentication. |

### API contract: RegistrationRequest

| Field | Type | Default / validation declaration |
|---|---|---|
| `full_name` | `str` | `Required` |
| `email` | `EmailStr` | `Required` |
| `registration_number` | `str` | `Required` |
| `password` | `str` | `Required` |

### API contract: RegistrationResponse

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `full_name` | `str` | `Required` |
| `email` | `str` | `Required` |
| `registration_number` | `str` | `Required` |
| `role` | `UserRole` | `Required` |
| `is_active` | `bool` | `Required` |
| `created_at` | `datetime` | `Required` |

### API contract: LoginRequest

| Field | Type | Default / validation declaration |
|---|---|---|
| `email` | `EmailStr / None` | `None` |
| `registration_number` | `str / None` | `None` |
| `password` | `str` | `Required` |
| `requested_role` | `UserRole / None` | `None` |

### API contract: CurrentUserResponse

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `full_name` | `str` | `Required` |
| `email` | `str` | `Required` |
| `registration_number` | `str / None` | `Required` |
| `role` | `UserRole` | `Required` |
| `is_active` | `bool` | `Required` |
| `group_id` | `int / None` | `None` |
| `group_email` | `str / None` | `None` |
| `principal_type` | `str` | `'ACCOUNT'` |
| `group_name` | `str / None` | `None` |
| `academic_cycle` | `str / None` | `None` |
| `group_status` | `str / None` | `None` |
| `members` | `list[dict[str, object]]` | `Field(default_factory=list)` |

## backend/app/schemas/dashboard_requirements.py
Lines: 43. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `DashboardRequirementWrite` | 9 | Implementation entry; inspect this symbol for details |
| `DashboardRequirementOut` | 37 | Implementation entry; inspect this symbol for details |

### API contract: DashboardRequirementWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `academic_deadline_id` | `int / None` | `Field(default=None, gt=0)` |
| `academic_cycle_id` | `int` | `Field(gt=0)` |
| `title` | `str` | `Field(min_length=3, max_length=200)` |
| `description` | `str / None` | `Field(default=None, max_length=4000)` |
| `requirement_type` | `RequirementType` | `Required` |
| `module` | `str` | `Field(min_length=1, max_length=120)` |
| `priority` | `Priority` | `'MEDIUM'` |
| `role_visibility` | `list[Roles]` | `Field(min_length=1)` |
| `assigned_user_id` | `int / None` | `Field(default=None, gt=0)` |
| `assigned_group_id` | `int / None` | `Field(default=None, gt=0)` |
| `due_at` | `datetime` | `Required` |
| `completion_percent` | `int` | `Field(default=0, ge=0, le=100)` |
| `is_required` | `bool` | `True` |

### API contract: DashboardRequirementOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `title` | `str` | `Required` |
| `description` | `str / None` | `Required` |
| `due_date` | `datetime` | `Required` |
| `timezone` | `str` | `Required` |
| `academic_cycle` | `int` | `Required` |
| `module` | `str` | `Required` |
| `requirement_type` | `str` | `Required` |
| `priority` | `str` | `Required` |
| `status` | `str` | `Required` |
| `completion_percent` | `int` | `Required` |
| `is_required` | `bool` | `Required` |
| `source_deadline_id` | `int / None` | `Required` |
| `assigned_to_current_user` | `bool` | `Required` |
| `can_update` | `bool` | `Required` |

## backend/app/schemas/document_requirements.py
Lines: 57. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RequirementWrite` | 5 | Implementation entry; inspect this symbol for details |
| `RequirementPatch` | 39 | Implementation entry; inspect this symbol for details |
| `RequirementOut` | 48 | Implementation entry; inspect this symbol for details |
| `VersionOut` | 52 | Implementation entry; inspect this symbol for details |
| `SubmissionOut` | 56 | Implementation entry; inspect this symbol for details |

### API contract: RequirementWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `title` | `str` | `Field(min_length=1, max_length=200)` |
| `due_date` | `datetime / None` | `None` |
| `assigned_to` | `str / None` | `None` |
| `description` | `str / None` | `None` |
| `academic_cycle_id` | `int / None` | `Field(default=None, gt=0)` |
| `module` | `str` | `'General'` |
| `visible_to_roles` | `list[str]` | `['STUDENT']` |
| `assigned_user_id` | `int / None` | `Field(default=None, gt=0)` |
| `assigned_group_id` | `int / None` | `Field(default=None, gt=0)` |
| `allowed_file_types` | `list[str]` | `['pdf']` |
| `max_file_size_mb` | `int` | `Field(default=10, ge=1, le=100)` |
| `due_at` | `datetime / None` | `None` |
| `reminder_days_before` | `int` | `Field(default=3, ge=0, le=365)` |
| `is_required` | `bool` | `True` |
| `late_upload_allowed` | `bool` | `False` |

### API contract: RequirementPatch

| Field | Type | Default / validation declaration |
|---|---|---|
| `title` | `str / None` | `Field(default=None, min_length=1, max_length=200)` |
| `description` | `str / None` | `None` |
| `due_at` | `datetime / None` | `None` |
| `allowed_file_types` | `list[str] / None` | `None` |
| `max_file_size_mb` | `int / None` | `Field(default=None, ge=1, le=100)` |
| `reminder_days_before` | `int / None` | `Field(default=None, ge=0, le=365)` |
| `late_upload_allowed` | `bool / None` | `None` |

### API contract: RequirementOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `title` | `str` | `Required` |
| `description` | `str / None` | `Required` |
| `academic_cycle_id` | `int` | `Required` |
| `module` | `str` | `Required` |
| `visible_to_roles` | `list` | `Required` |
| `assigned_user_id` | `int / None` | `Required` |
| `assigned_group_id` | `int / None` | `Required` |
| `allowed_file_types` | `list` | `Required` |
| `max_file_size_mb` | `int` | `Required` |
| `due_at` | `datetime` | `Required` |
| `reminder_days_before` | `int` | `Required` |
| `is_required` | `bool` | `Required` |
| `status` | `str` | `Required` |
| `late_upload_allowed` | `bool` | `Required` |
| `created_at` | `datetime` | `Required` |
| `updated_at` | `datetime` | `Required` |
| `submission_count` | `int` | `0` |

### API contract: VersionOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `version_number` | `int` | `Required` |
| `original_filename` | `str` | `Required` |
| `mime_type` | `str` | `Required` |
| `file_size` | `int` | `Required` |
| `storage_reference` | `str` | `Required` |
| `uploaded_at` | `datetime` | `Required` |
| `download_url` | `str / None` | `None` |

### API contract: SubmissionOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `requirement_id` | `int` | `Required` |
| `status` | `str` | `Required` |
| `is_late` | `bool` | `Required` |
| `review_comment` | `str / None` | `Required` |
| `uploaded_at` | `datetime` | `Required` |
| `updated_at` | `datetime` | `Required` |
| `versions` | `list[VersionOut]` | `[]` |

## backend/app/schemas/email.py
Lines: 9. Shared normalization for Pydantic email fields.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `normalize_email` | 4 | Trim and case-normalize email input before EmailStr validation. |

## backend/app/schemas/evaluation_rubrics.py
Lines: 88. Strict request and response schemas for draft Evaluation Criteria.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RubricCriterionWrite` | 8 | Implementation entry; inspect this symbol for details |
| `RubricVersionWrite` | 31 | Implementation entry; inspect this symbol for details |
| `RubricCriterionOut` | 61 | Implementation entry; inspect this symbol for details |
| `RubricVersionOut` | 68 | Implementation entry; inspect this symbol for details |
| `RubricDetailOut` | 77 | Implementation entry; inspect this symbol for details |
| `RubricListOut` | 83 | Implementation entry; inspect this symbol for details |

### API contract: RubricCriterionWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `name` | `str` | `Field(min_length=1, max_length=160)` |
| `description` | `str / None` | `Field(default=None, max_length=2000)` |
| `order` | `int` | `Field(ge=1)` |

### API contract: RubricVersionWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `name` | `str` | `Field(min_length=1, max_length=160)` |
| `description` | `str / None` | `Field(default=None, max_length=4000)` |
| `criteria` | `list[RubricCriterionWrite]` | `Field(min_length=1, max_length=100)` |

### API contract: RubricCriterionOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `name` | `str` | `Required` |
| `description` | `str / None` | `Required` |
| `order` | `int` | `Required` |

### API contract: RubricVersionOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `version_number` | `int` | `Required` |
| `name` | `str` | `Required` |
| `description` | `str / None` | `Required` |
| `created_at` | `datetime` | `Required` |
| `criteria` | `list[RubricCriterionOut]` | `Required` |

### API contract: RubricDetailOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `created_at` | `datetime` | `Required` |
| `versions` | `list[RubricVersionOut]` | `Required` |

### API contract: RubricListOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `name` | `str` | `Required` |
| `description` | `str / None` | `Required` |
| `latest_version_number` | `int` | `Required` |
| `created_at` | `datetime` | `Required` |

## backend/app/schemas/evaluations.py
Lines: 160. Request and response contracts for role-based FYP evaluation.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluationCategory` | 9 | Implementation entry; inspect this symbol for details |
| `EvaluationStatus` | 17 | Implementation entry; inspect this symbol for details |
| `EvaluationWrite` | 34 | Implementation entry; inspect this symbol for details |
| `EvaluationOut` | 64 | Implementation entry; inspect this symbol for details |
| `AssignmentMemberOut` | 85 | Implementation entry; inspect this symbol for details |
| `EvaluationAssignmentOut` | 92 | Implementation entry; inspect this symbol for details |
| `EvaluationReturn` | 99 | Implementation entry; inspect this symbol for details |
| `EvaluationCorrectionWrite` | 112 | Implementation entry; inspect this symbol for details |
| `EvaluationAggregationWrite` | 127 | Implementation entry; inspect this symbol for details |
| `EvaluationAggregationOut` | 133 | Implementation entry; inspect this symbol for details |
| `ResultCategoryOut` | 140 | Implementation entry; inspect this symbol for details |
| `ConsolidatedResultOut` | 149 | Implementation entry; inspect this symbol for details |

### API contract: EvaluationWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `student_id` | `int / None` | `Field(default=None, gt=0)` |
| `group_id` | `int / None` | `Field(default=None, gt=0)` |
| `team_id` | `int / None` | `Field(default=None, gt=0)` |
| `evaluation_category` | `EvaluationCategory` | `Required` |
| `obtained_marks` | `int / None` | `Field(default=None, ge=0)` |
| `feedback` | `str / None` | `Field(default=None, max_length=10000)` |
| `submit` | `bool` | `False` |

### API contract: EvaluationOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `student_id` | `int / None` | `Required` |
| `group_id` | `int / None` | `Required` |
| `evaluator_id` | `int` | `Required` |
| `evaluator_role` | `str` | `Required` |
| `evaluation_category` | `str` | `Required` |
| `maximum_marks` | `int` | `Required` |
| `obtained_marks` | `int / None` | `Required` |
| `feedback` | `str / None` | `Required` |
| `status` | `str` | `Required` |
| `returned_reason` | `str / None` | `Required` |
| `submitted_at` | `datetime / None` | `Required` |
| `approved_at` | `datetime / None` | `Required` |
| `published_at` | `datetime / None` | `Required` |
| `created_at` | `datetime` | `Required` |
| `updated_at` | `datetime` | `Required` |

### API contract: AssignmentMemberOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `full_name` | `str` | `Required` |
| `registration_number` | `str` | `Required` |
| `university_email` | `str` | `Required` |

### API contract: EvaluationAssignmentOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `group_id` | `int` | `Required` |
| `academic_cycle_id` | `int` | `Required` |
| `students` | `list[AssignmentMemberOut]` | `Required` |
| `categories` | `list[str]` | `Required` |

### API contract: EvaluationReturn

| Field | Type | Default / validation declaration |
|---|---|---|
| `reason` | `str` | `Field(min_length=3, max_length=5000)` |

### API contract: EvaluationCorrectionWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `new_marks` | `int` | `Field(ge=0)` |
| `reason` | `str` | `Field(min_length=3, max_length=5000)` |

### API contract: EvaluationAggregationWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `evaluation_category` | `EvaluationCategory` | `Required` |
| `method` | `str` | `Field(pattern='^(AVERAGE/MAXIMUM/MEDIAN)$')` |

### API contract: EvaluationAggregationOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `evaluation_category` | `str` | `Required` |
| `method` | `str` | `Required` |
| `is_active` | `bool` | `Required` |

### API contract: ResultCategoryOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `category` | `str` | `Required` |
| `maximum_marks` | `int` | `Required` |
| `obtained_marks` | `float / None` | `Required` |
| `status` | `str` | `Required` |
| `evaluator_ids` | `list[int]` | `Required` |
| `feedback` | `list[str]` | `Required` |

### API contract: ConsolidatedResultOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `student_id` | `int` | `Required` |
| `group_id` | `int / None` | `Required` |
| `student_name` | `str` | `Required` |
| `registration_number` | `str / None` | `Required` |
| `categories` | `list[ResultCategoryOut]` | `Required` |
| `total_marks` | `float` | `Required` |
| `maximum_marks` | `int` | `Required` |
| `percentage` | `float` | `Required` |
| `grade` | `str / None` | `Required` |
| `gpa` | `float / None` | `Required` |
| `published` | `bool` | `Required` |

## backend/app/schemas/password_reset.py
Lines: 46. Public schemas for password recovery without exposing account existence.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ForgotPasswordRequest` | 8 | Implementation entry; inspect this symbol for details |
| `ResetPasswordRequest` | 29 | Implementation entry; inspect this symbol for details |
| `PasswordResetMessage` | 45 | Implementation entry; inspect this symbol for details |

### API contract: ForgotPasswordRequest

| Field | Type | Default / validation declaration |
|---|---|---|
| `identifier` | `str / None` | `Field(default=None, min_length=1, max_length=320)` |
| `email` | `str / None` | `Field(default=None, min_length=1, max_length=320)` |
| `registration_number` | `str / None` | `Field(default=None, min_length=1, max_length=100)` |

### API contract: ResetPasswordRequest

| Field | Type | Default / validation declaration |
|---|---|---|
| `token` | `str` | `Field(min_length=20, max_length=256)` |
| `password` | `str` | `Field(validation_alias=AliasChoices('password', 'new_password'))` |

### API contract: PasswordResetMessage

| Field | Type | Default / validation declaration |
|---|---|---|
| `message` | `str` | `Required` |

## backend/app/schemas/project_workflow.py
Lines: 91. Validated request payloads for project progress, defense, and evaluation APIs.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `MilestoneWrite` | 8 | Implementation entry; inspect this symbol for details |
| `TaskWrite` | 24 | Implementation entry; inspect this symbol for details |
| `MeetingWrite` | 29 | Implementation entry; inspect this symbol for details |
| `ScheduleWrite` | 45 | Implementation entry; inspect this symbol for details |
| `ScheduleReschedule` | 61 | Implementation entry; inspect this symbol for details |
| `EvaluationScoreWrite` | 70 | Implementation entry; inspect this symbol for details |
| `EvaluationWrite` | 78 | Implementation entry; inspect this symbol for details |
| `ResolutionWrite` | 88 | Implementation entry; inspect this symbol for details |

### API contract: MilestoneWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `title` | `str` | `Field(min_length=1, max_length=255)` |
| `description` | `str / None` | `Field(default=None, max_length=5000)` |
| `due_at` | `datetime / None` | `None` |
| `completion_percent` | `int` | `Field(default=0, ge=0, le=100)` |

### API contract: TaskWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `milestone_id` | `int / None` | `Field(default=None, gt=0)` |
| `owner_user_id` | `int / None` | `Field(default=None, gt=0)` |

### API contract: MeetingWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `held_at` | `datetime` | `Required` |
| `minutes` | `str` | `Field(min_length=1, max_length=20000)` |
| `decisions` | `str / None` | `Field(default=None, max_length=10000)` |
| `action_items` | `list[dict[str, str]]` | `Field(default_factory=list, max_length=100)` |

### API contract: ScheduleWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `team_id` | `int` | `Field(gt=0)` |
| `academic_cycle_id` | `int` | `Field(gt=0)` |
| `start_at` | `datetime` | `Required` |
| `end_at` | `datetime` | `Required` |
| `room` | `str / None` | `Field(default=None, max_length=255)` |
| `online_link` | `str / None` | `Field(default=None, max_length=1000)` |
| `panel_member_ids` | `list[int]` | `Field(default_factory=list, max_length=20)` |

### API contract: ScheduleReschedule

| Field | Type | Default / validation declaration |
|---|---|---|
| `start_at` | `datetime` | `Required` |
| `end_at` | `datetime` | `Required` |
| `room` | `str / None` | `Field(default=None, max_length=255)` |
| `online_link` | `str / None` | `Field(default=None, max_length=1000)` |
| `panel_member_ids` | `list[int] / None` | `Field(default=None, max_length=20)` |

### API contract: EvaluationScoreWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `criterion_key` | `str` | `Field(min_length=1, max_length=160)` |
| `score` | `int` | `Field(ge=0)` |
| `max_score` | `int` | `Field(gt=0)` |
| `feedback` | `str / None` | `Field(default=None, max_length=5000)` |

### API contract: EvaluationWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `schedule_id` | `int` | `Field(gt=0)` |
| `scores` | `list[EvaluationScoreWrite]` | `Field(min_length=1, max_length=100)` |
| `overall_score` | `int / None` | `Field(default=None, ge=0, le=100)` |
| `overall_feedback` | `str / None` | `Field(default=None, max_length=10000)` |
| `decision` | `str / None` | `Field(default=None, max_length=64)` |
| `submit` | `bool` | `False` |

### API contract: ResolutionWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `status` | `str` | `Field(pattern='^(RECHECK_REQUESTED/RESOLVED)$')` |
| `note` | `str` | `Field(min_length=1, max_length=10000)` |

## backend/app/schemas/reminder_rules.py
Lines: 24. Strict configuration-only rule requests.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RulePreview` | 5 | Implementation entry; inspect this symbol for details |
| `RuleWrite` | 11 | Implementation entry; inspect this symbol for details |
| `RuleCreate` | 23 | Implementation entry; inspect this symbol for details |

### API contract: RulePreview

| Field | Type | Default / validation declaration |
|---|---|---|
| `deadline_version_id` | `int` | `Field(gt=0, strict=True)` |
| `direction` | `Literal['BEFORE', 'AFTER']` | `Required` |
| `elapsed_minutes` | `int` | `Field(gt=0, le=2147483647, strict=True)` |

### API contract: RuleWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `name` | `str` | `Field(min_length=1, max_length=160)` |
| `description` | `str / None` | `Field(default=None, max_length=4000)` |
| `category` | `Literal['REMINDER', 'ESCALATION']` | `Required` |

### API contract: RuleCreate

| Field | Type | Default / validation declaration |
|---|---|---|
| `academic_cycle_id` | `int` | `Field(gt=0, strict=True)` |

## backend/app/schemas/supervisor_capacity.py
Lines: 42. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CapacitySession` | 6 | Implementation entry; inspect this symbol for details |
| `SupervisorCapacityWrite` | 11 | Implementation entry; inspect this symbol for details |
| `SupervisorCapacityOut` | 18 | Implementation entry; inspect this symbol for details |

### API contract: SupervisorCapacityWrite

| Field | Type | Default / validation declaration |
|---|---|---|
| `supervisor_id` | `StrictInt` | `Required` |
| `academic_year` | `StrictInt` | `Field(ge=1900, le=2200)` |
| `maximum_groups` | `StrictInt` | `Field(gt=0)` |

### API contract: SupervisorCapacityOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `supervisor_id` | `int` | `Required` |
| `supervisor_name` | `str` | `Required` |
| `supervisor_email` | `str` | `Required` |
| `supervisor_is_eligible` | `bool` | `Required` |
| `academic_year` | `int / None` | `Required` |
| `maximum_groups` | `int` | `Required` |
| `fall_assigned` | `int` | `Required` |
| `spring_assigned` | `int` | `Required` |
| `total_assigned` | `int` | `Required` |
| `remaining_capacity` | `int` | `Required` |
| `status` | `str` | `Required` |
| `academic_cycle_id` | `int / None` | `None` |
| `academic_cycle_name` | `str / None` | `None` |
| `max_group_capacity` | `int / None` | `None` |
| `assigned_groups` | `int / None` | `None` |
| `remaining_groups` | `int / None` | `None` |
| `session` | `CapacitySession / None` | `None` |
| `assigned` | `int / None` | `None` |
| `remaining` | `int / None` | `None` |
| `full` | `bool / None` | `None` |
| `created_at` | `datetime` | `Required` |
| `updated_at` | `datetime` | `Required` |

## backend/app/schemas/team_registration.py
Lines: 142. Strict request and safe response schemas for shared-team registration.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `TeamMemberInput` | 12 | One group leader or colleague record; contact email is legacy-only. |
| `TeamRegistrationRequest` | 29 | Public input for one shared student login and its team contacts. |
| `SafeAccountOut` | 47 | Implementation entry; inspect this symbol for details |
| `SafeTeamOut` | 59 | Implementation entry; inspect this symbol for details |
| `SafeCycleOut` | 67 | Implementation entry; inspect this symbol for details |
| `SafeTeamMemberOut` | 75 | Implementation entry; inspect this symbol for details |
| `TeamRegistrationResponse` | 87 | Implementation entry; inspect this symbol for details |
| `StudentGroupMemberInput` | 94 | Implementation entry; inspect this symbol for details |
| `StudentGroupRegistrationRequest` | 120 | Implementation entry; inspect this symbol for details |

### API contract: TeamMemberInput

| Field | Type | Default / validation declaration |
|---|---|---|
| `full_name` | `str` | `Required` |
| `registration_number` | `str` | `Required` |
| `university_email` | `EmailStr / None` | `None` |

### API contract: TeamRegistrationRequest

| Field | Type | Default / validation declaration |
|---|---|---|
| `academic_cycle_id` | `int` | `Required` |
| `creator` | `TeamMemberInput` | `Required` |
| `shared_login_email` | `EmailStr` | `Required` |
| `password` | `str` | `Required` |
| `confirm_password` | `str / None` | `None` |
| `members` | `list[TeamMemberInput]` | `Required` |

### API contract: SafeAccountOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `full_name` | `str` | `Required` |
| `email` | `str` | `Required` |
| `registration_number` | `str` | `Required` |
| `role` | `UserRole` | `Required` |
| `is_active` | `bool` | `Required` |
| `created_at` | `datetime` | `Required` |

### API contract: SafeTeamOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `academic_cycle_id` | `int` | `Required` |
| `created_at` | `datetime` | `Required` |

### API contract: SafeCycleOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `code` | `str` | `Required` |
| `display_name` | `str` | `Required` |

### API contract: SafeTeamMemberOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `full_name` | `str` | `Required` |
| `registration_number` | `str` | `Required` |
| `university_email` | `str / None` | `Required` |
| `is_creator` | `bool` | `Required` |
| `is_active` | `bool` | `Required` |
| `created_at` | `datetime` | `Required` |

### API contract: TeamRegistrationResponse

| Field | Type | Default / validation declaration |
|---|---|---|
| `account` | `SafeAccountOut` | `Required` |
| `team` | `SafeTeamOut` | `Required` |
| `cycle` | `SafeCycleOut` | `Required` |
| `members` | `list[SafeTeamMemberOut]` | `Required` |

### API contract: StudentGroupMemberInput

| Field | Type | Default / validation declaration |
|---|---|---|
| `email` | `EmailStr` | `Required` |
| `registration_number` | `str` | `Required` |
| `full_name` | `str` | `Required` |
| `designation` | `str / None` | `None` |

### API contract: StudentGroupRegistrationRequest

| Field | Type | Default / validation declaration |
|---|---|---|
| `academic_cycle_id` | `int` | `Required` |
| `group_name` | `str / None` | `None` |
| `group_email` | `EmailStr` | `Required` |
| `password` | `str` | `Required` |
| `confirm_password` | `str` | `Required` |
| `members` | `list[StudentGroupMemberInput]` | `Required` |

## backend/app/schemas/templates.py
Lines: 22. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RuleFields` | 4 | Implementation entry; inspect this symbol for details |
| `TemplateCreate` | 7 | Implementation entry; inspect this symbol for details |
| `TemplateVersionCreate` | 9 | Implementation entry; inspect this symbol for details |
| `RuleCreate` | 11 | Implementation entry; inspect this symbol for details |
| `TemplateOut` | 13 | Implementation entry; inspect this symbol for details |
| `TemplateListOut` | 15 | Implementation entry; inspect this symbol for details |
| `RuleOut` | 17 | Implementation entry; inspect this symbol for details |
| `TemplateHistoryVersion` | 19 | Implementation entry; inspect this symbol for details |
| `TemplateDetail` | 21 | Implementation entry; inspect this symbol for details |

### API contract: RuleFields

| Field | Type | Default / validation declaration |
|---|---|---|
| `page_size` | `str / None` | `None` |
| `font_family` | `str / None` | `None` |
| `font_size_pt` | `float / None` | `Field(default=None, gt=0)` |
| `margin_mm` | `float / None` | `Field(default=None, gt=0)` |
| `line_spacing` | `float / None` | `Field(default=None, gt=0)` |
| `heading_style` | `str / None` | `None` |
| `required_sections` | `list[str] / None` | `None` |

### API contract: TemplateCreate

| Field | Type | Default / validation declaration |
|---|---|---|
| `template_type` | `TemplateType` | `Required` |
| `title` | `str` | `Field(min_length=1, max_length=160)` |
| `provenance` | `str` | `Field(pattern='^(OBSERVED_REFERENCE/CONFIRMED_REQUIREMENT)$')` |
| `source_note` | `str` | `Field(min_length=1, max_length=500)` |
| `rules` | `RuleFields` | `Field(default_factory=RuleFields)` |

### API contract: TemplateVersionCreate

| Field | Type | Default / validation declaration |
|---|---|---|
| `title` | `str` | `Field(min_length=1, max_length=160)` |
| `provenance` | `str` | `Field(pattern='^(OBSERVED_REFERENCE/CONFIRMED_REQUIREMENT)$')` |
| `source_note` | `str` | `Field(min_length=1, max_length=500)` |

### API contract: RuleCreate

| Field | Type | Default / validation declaration |
|---|---|---|
| `provenance` | `str` | `Field(pattern='^(OBSERVED_REFERENCE/CONFIRMED_REQUIREMENT)$')` |
| `rules` | `RuleFields` | `Field(default_factory=RuleFields)` |

### API contract: TemplateOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `template_type` | `TemplateType` | `Required` |
| `version_number` | `int` | `Required` |
| `title` | `str` | `Required` |
| `provenance` | `str` | `Required` |
| `source_note` | `str` | `Required` |
| `created_at` | `datetime` | `Required` |
| `is_active` | `bool` | `False` |
| `activated_at` | `datetime / None` | `None` |
| `activated_by_id` | `int / None` | `None` |

### API contract: TemplateListOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `reference_id` | `int` | `Required` |

### API contract: RuleOut

| Field | Type | Default / validation declaration |
|---|---|---|
| `id` | `int` | `Required` |
| `template_reference_version_id` | `int` | `Required` |
| `version_number` | `int` | `Required` |
| `provenance` | `str` | `Required` |
| `rules` | `dict` | `Required` |
| `created_at` | `datetime` | `Required` |

### API contract: TemplateHistoryVersion

| Field | Type | Default / validation declaration |
|---|---|---|
| `template` | `TemplateOut` | `Required` |
| `rules` | `list[RuleOut]` | `Required` |

### API contract: TemplateDetail

| Field | Type | Default / validation declaration |
|---|---|---|
| `reference_id` | `int` | `Required` |
| `template_type` | `TemplateType` | `Required` |
| `versions` | `list[TemplateHistoryVersion]` | `Required` |

## backend/app/security.py
Lines: 74. Password and opaque-session security utilities.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `normalize_full_name` | 15 | Implementation entry; inspect this symbol for details |
| `validate_full_name` | 19 | Implementation entry; inspect this symbol for details |
| `password_policy_errors` | 29 | Return safe, user-facing password requirements that are not met. |
| `validate_password` | 47 | Validate a newly supplied account password before it is hashed. |
| `hash_password` | 54 | Return an Argon2id hash without modifying the supplied password. |
| `verify_password` | 59 | Verify an unmodified password against an Argon2id hash. |
| `generate_session_token` | 67 | Return an opaque, URL-safe session bearer value; never persist this value. |
| `hash_session_token` | 72 | Return the deterministic database representation of an opaque session token. |

## backend/app/supervisor_assignments.py
Lines: 89. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AssignmentWrite` | 13 | Implementation entry; inspect this symbol for details |
| `failure` | 20 | Implementation entry; inspect this symbol for details |
| `out` | 22 | Implementation entry; inspect this symbol for details |
| `teams` | 25 | Implementation entry; inspect this symbol for details |
| `listing` | 29 | Implementation entry; inspect this symbol for details |
| `assign` | 32 | Implementation entry; inspect this symbol for details |
| `end` | 73 | Implementation entry; inspect this symbol for details |

## backend/app/supervisor_request_conversations.py
Lines: 78. Request-scoped conversation endpoints with server-side authorization.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RequestMessageWrite` | 15 | Implementation entry; inspect this symbol for details |
| `_request_for_actor` | 28 | Implementation entry; inspect this symbol for details |
| `_message_out` | 46 | Implementation entry; inspect this symbol for details |
| `conversation_history` | 52 | Implementation entry; inspect this symbol for details |
| `send_conversation_message` | 59 | Implementation entry; inspect this symbol for details |

## backend/app/supervisor_requests.py
Lines: 1082. Cycle-scoped supervisor selection and proposal-request workflow.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RevisionAction` | 57 | Implementation entry; inspect this symbol for details |
| `DecisionAction` | 63 | Implementation entry; inspect this symbol for details |
| `ProposalAIReviewFinding` | 79 | Implementation entry; inspect this symbol for details |
| `ProposalAIReviewResponse` | 91 | Implementation entry; inspect this symbol for details |
| `_normalize_submission_note` | 123 | Implementation entry; inspect this symbol for details |
| `_reject_text_for_supervisor_selection` | 128 | Keep the legacy supervisor-selection upload contract PDF/DOCX-only. |
| `failure` | 140 | Implementation entry; inspect this symbol for details |
| `_ai_fallback` | 144 | Implementation entry; inspect this symbol for details |
| `_review_prompt` | 162 | Implementation entry; inspect this symbol for details |
| `_ai_out` | 180 | Implementation entry; inspect this symbol for details |
| `_team_for_student` | 188 | Resolve the existing shared group for either its login or an active member. |
| `_actor_has_team_access` | 202 | Implementation entry; inspect this symbol for details |
| `_cycle_for_request` | 215 | Implementation entry; inspect this symbol for details |
| `_lock_capacity` | 227 | Implementation entry; inspect this symbol for details |
| `_capacity_used` | 247 | Implementation entry; inspect this symbol for details |
| `_ensure_capacity` | 267 | Implementation entry; inspect this symbol for details |
| `_owner_request` | 272 | Implementation entry; inspect this symbol for details |
| `_append_history` | 287 | Implementation entry; inspect this symbol for details |
| `_audit` | 299 | Implementation entry; inspect this symbol for details |
| `_history_out` | 313 | Implementation entry; inspect this symbol for details |
| `_document_out` | 333 | Implementation entry; inspect this symbol for details |
| `_missing_required` | 357 | Implementation entry; inspect this symbol for details |
| `_apply_document_snapshot` | 372 | Implementation entry; inspect this symbol for details |
| `_next_document_version` | 382 | Implementation entry; inspect this symbol for details |
| `_next_note_version` | 387 | Implementation entry; inspect this symbol for details |
| `_note_versions_out` | 392 | Implementation entry; inspect this symbol for details |
| `_audit_document` | 401 | Implementation entry; inspect this symbol for details |
| `_out` | 413 | Implementation entry; inspect this symbol for details |
| `_load_for_view` | 469 | Implementation entry; inspect this symbol for details |
| `active_cycles` | 478 | Implementation entry; inspect this symbol for details |
| `eligible_supervisors` | 487 | Implementation entry; inspect this symbol for details |
| `my_requests` | 523 | Implementation entry; inspect this symbol for details |
| `create_request` | 542 | Implementation entry; inspect this symbol for details |
| `update_draft_document` | 633 | Implementation entry; inspect this symbol for details |
| `confirm_extraction` | 698 | Implementation entry; inspect this symbol for details |
| `submit_request` | 736 | Implementation entry; inspect this symbol for details |
| `withdraw_request` | 801 | Implementation entry; inspect this symbol for details |
| `supervisor_queue` | 832 | Implementation entry; inspect this symbol for details |
| `decide_request` | 850 | Implementation entry; inspect this symbol for details |
| `proposal_document` | 922 | Implementation entry; inspect this symbol for details |
| `_monitor_statement` | 944 | Implementation entry; inspect this symbol for details |
| `admin_monitor` | 973 | Implementation entry; inspect this symbol for details |
| `coordinator_monitor` | 988 | Implementation entry; inspect this symbol for details |
| `read_request` | 1003 | Implementation entry; inspect this symbol for details |
| `run_proposal_ai_review` | 1021 | Implementation entry; inspect this symbol for details |
| `latest_proposal_ai_review` | 1073 | Implementation entry; inspect this symbol for details |

## backend/app/supervisor_workspace.py
Lines: 155. Supervisor-owned group workspace assembled from persisted workflow records.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `owned_request` | 20 | Implementation entry; inspect this symbol for details |
| `owned_group` | 27 | Implementation entry; inspect this symbol for details |
| `workspace` | 35 | Implementation entry; inspect this symbol for details |
| `assigned_groups` | 89 | Implementation entry; inspect this symbol for details |
| `group_detail` | 95 | Implementation entry; inspect this symbol for details |
| `group_section` | 105 | Implementation entry; inspect this symbol for details |
| `requests` | 110 | Implementation entry; inspect this symbol for details |
| `request_detail` | 116 | Implementation entry; inspect this symbol for details |
| `DecisionInput` | 125 | Implementation entry; inspect this symbol for details |
| `decision` | 133 | Implementation entry; inspect this symbol for details |
| `group_channel` | 138 | Implementation entry; inspect this symbol for details |
| `conversation` | 147 | Implementation entry; inspect this symbol for details |
| `send_message` | 153 | Implementation entry; inspect this symbol for details |

## backend/app/team_compatibility.py
Lines: 77. Equal-weight aggregation for team compatibility assessments.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `aggregate_compatibility` | 18 | Aggregate comparable categories, leaving missing assessments unscored. |
| `_tokens` | 30 | Implementation entry; inspect this symbol for details |
| `_overlap` | 38 | Implementation entry; inspect this symbol for details |
| `_similar_scale` | 45 | Implementation entry; inspect this symbol for details |
| `_complementary` | 53 | Implementation entry; inspect this symbol for details |
| `hybrid_compatibility` | 62 | Reproducible, explainable score; Ollama is never involved in this function. |

## backend/app/team_lifecycle.py
Lines: 31. Deterministic Module 2 lifecycle helpers shared by modules 2, 3 and 5.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `refresh_team_status` | 8 | Implementation entry; inspect this symbol for details |
| `lock_team` | 17 | Implementation entry; inspect this symbol for details |
| `cancel_open_team_requests` | 28 | Implementation entry; inspect this symbol for details |

## frontend/src/AcademicCycleDashboard.css
Lines: 1. 
Frontend entry import graph: not reached by static imports.

## frontend/src/AcademicCycleDashboard.tsx
Lines: 85. 
Frontend entry import graph: not reached by static imports.
Imports: `react`, `./AdminCycleManager`, `./AcademicCycleDashboard.css`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/academic-cycles/${detailId}/overview`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AcademicCycleDashboard` | 15 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminCycleManager.css
Lines: 57. 
Frontend entry import graph: reachable.

## frontend/src/AdminCycleManager.tsx
Lines: 41. 
Frontend entry import graph: reachable.
Imports: `react`, `./AdminCycleManager.css`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/academic-cycles/${cycle.id}/group-policy`, `/api/v1/admin/academic-cycles`, `/api/v1/admin/academic-cycles/${row.id}`, `/api/v1/admin/academic-cycles/${row.id}/group-policy`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminCycleManager` | 7 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDeadlines.tsx
Lines: 135. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/admin/academic-deadlines`, `/api/v1/admin/academic-deadlines${query}`, `/api/v1/admin/academic-deadlines/${deadlineId}`, `/api/v1/admin/academic-deadlines/${selected.id}/versions`, `/api/v1/admin/academic-deadlines/preview`, `/api/v1/admin/time-zones`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDeadlines` | 16 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManager.tsx
Lines: 3. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`, `/api/v1/document-requirements/${id}/${name}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManager` | 3 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerAllFormats.tsx
Lines: 7. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerAllFormats` | 7 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerClean.tsx
Lines: 35. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/document-requirements`, `/api/v1/document-requirements/${`, `/api/v1/document-requirements/${item.id}${name`, `/api/v1/document-requirements/${item.id}/submissions`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerClean` | 25 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerComplete.tsx
Lines: 5. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`, `/api/v1/document-requirements/${id}/${name}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerComplete` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerCreate.tsx
Lines: 16. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`, `/api/v1/document-requirements/${id}/${name}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerCreate` | 9 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerFinal.tsx
Lines: 6. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerFinal` | 6 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerFormats.tsx
Lines: 6. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerFormats` | 6 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerSimple.tsx
Lines: 5. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`, `/api/v1/document-requirements/${id}/${name}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerSimple` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminDocumentRequirementManagerUI.tsx
Lines: 8. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements`, `/api/v1/document-requirements/${id}/${name}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminDocumentRequirementManagerUI` | 8 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminOverview.css
Lines: 142. 
Frontend entry import graph: reachable.

## frontend/src/AdminOverview.tsx
Lines: 21. 
Frontend entry import graph: reachable.
Imports: `react`, `./AdminOverview.css`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/academic-cycles/${cycle.id}/group-policy`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminOverview` | 8 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminPortal.tsx
Lines: 38. 
Frontend entry import graph: reachable.
Imports: `react`, `./AdminCycleManager`, `./AdminOverview`, `./AdminUsersRoles`, `./AdminStudentGroups`, `./AdminSupervisorCapacity`, `./AdminReminderRules`, `./AdminDeadlines`, `./AdminDocumentRequirementManagerClean`, `./modules/module-3/AdminProposalTemplates`, `./portals/admin/modules/archive/ArchiveManagement`, `./portals/shared/AdminSidebar`, `./AdminSidebar.css`.
API references found in source (dynamic expressions may be partial): `/api/v1/admin/registration-mode`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminPortal` | 27 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminReminderRules.tsx
Lines: 37. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/admin/academic-deadlines/${row.id}`, `/api/v1/admin/academic-deadlines?academic_cycle_id`, `/api/v1/admin/reminder-rules${cycle`, `/api/v1/admin/reminder-rules${selected`, `/api/v1/admin/reminder-rules/${id}`, `/api/v1/admin/reminder-rules/preview`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminReminderRules` | 16 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminSidebar.css
Lines: 119. 
Frontend entry import graph: reachable.

## frontend/src/AdminStudentGroups.tsx
Lines: 21. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/admin/student-groups`, `/api/v1/admin/student-groups/${group.id}${action`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminStudentGroups` | 6 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminSupervisorCapacity.tsx
Lines: 21. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/admin/supervisor-capacities`, `/api/v1/admin/supervisor-capacities${isEdit`, `/api/v1/admin/supervisor-capacities/${policy.id}`, `/api/v1/admin/users?role`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminSupervisorCapacity` | 11 | Implementation entry; inspect this symbol for details |

## frontend/src/AdminUsersRoles.tsx
Lines: 489. 
Frontend entry import graph: reachable.
Imports: `react`, `./PasswordField`, `./passwordPolicy`, `./emailValidation`.
API references found in source (dynamic expressions may be partial): `/api/v1/admin/users`, `/api/v1/admin/users/${confirm.user.id}`, `/api/v1/admin/users/${confirm.user.id}/${confirm.type}`, `/api/v1/admin/users?${query}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminUsersRoles` | 36 | Implementation entry; inspect this symbol for details |

## frontend/src/App.tsx
Lines: 1324. 
Frontend entry import graph: reachable.
Imports: `react`, `./AdminPortal`, `./PasswordField`, `./passwordPolicy`, `./emailValidation`, `./portals/student/StudentPortal`, `./portals/supervisor/SupervisorPortal`, `./portals/coordinator/CoordinatorPortal`, `./portals/student/modules/StudentEvaluatorPortal`, `./assets/sign-in-students.webp`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/academic-cycles/${cycleId}/group-policy`, `/api/v1/auth/dev/password-reset-link?identifier`, `/api/v1/auth/forgot-password`, `/api/v1/auth/group-signup`, `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/password-reset-status`, `/api/v1/auth/reset-password`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `API` | 73 | Implementation entry; inspect this symbol for details |
| `dashboardPageForRole` | 91 | Implementation entry; inspect this symbol for details |
| `App` | 263 | Implementation entry; inspect this symbol for details |

## frontend/src/auth.css
Lines: 57. 
Frontend entry import graph: not reached by static imports.

## frontend/src/components/DashboardDeadlinesRequirements.tsx
Lines: 7. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/dashboard/requirements`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `DashboardDeadlinesRequirements` | 3 | Implementation entry; inspect this symbol for details |

## frontend/src/dashboard-theme.css
Lines: 204. 
Frontend entry import graph: not reached by static imports.

## frontend/src/design-system.css
Lines: 205. 
Frontend entry import graph: reachable.

## frontend/src/emailValidation.ts
Lines: 40. 
Frontend entry import graph: reachable.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EMAIL_DOMAIN_MESSAGE` | 1 | Implementation entry; inspect this symbol for details |
| `EMAIL_FORMAT_MESSAGE` | 3 | Implementation entry; inspect this symbol for details |
| `normalizeEmail` | 8 | Implementation entry; inspect this symbol for details |
| `emailValidationMessage` | 13 | Implementation entry; inspect this symbol for details |
| `isValidEmail` | 38 | Implementation entry; inspect this symbol for details |

## frontend/src/EvaluationMarksWorkspace.tsx
Lines: 177. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/admin/evaluations`, `/api/v1/admin/evaluations/aggregation`, `/api/v1/admin/results/group/${groupId}`, `/api/v1/evaluations`, `/api/v1/evaluations/${evaluation.id}`, `/api/v1/evaluations/${evaluation.id}/report.pdf`, `/api/v1/evaluations/${row.id}/${action}`, `/api/v1/evaluations/${row.id}/report.pdf`, `/api/v1/evaluations/assignments`, `/api/v1/evaluations/my`, `/api/v1/student/results`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluationMarksWorkspace` | 32 | Implementation entry; inspect this symbol for details |

## frontend/src/index.css
Lines: 355. 
Frontend entry import graph: reachable.

## frontend/src/inputValidation.ts
Lines: 21. 
Frontend entry import graph: not reached by static imports.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `normalizeFullName` | 3 | Implementation entry; inspect this symbol for details |
| `fullNameValidationMessage` | 7 | Implementation entry; inspect this symbol for details |
| `academicTextValidationMessage` | 15 | Implementation entry; inspect this symbol for details |

## frontend/src/main.tsx
Lines: 6. 
Frontend entry import graph: reachable.
Imports: `react`, `react-dom/client`, `./App`, `./index.css`, `./design-system.css`.

## frontend/src/modules/module-3/AdminProposalTemplates.tsx
Lines: 101. 
Frontend entry import graph: reachable.
Imports: `react`, `./module-3.css`.
API references found in source (dynamic expressions may be partial): `/api/v1/proposal-compliance/templates`, `/api/v1/proposal-compliance/templates/${selected.id}/rules`, `/api/v1/proposal-compliance/templates/${template.id}/activate`, `/api/v1/proposal-compliance/templates/${template.id}/deactivate`, `/api/v1/proposal-compliance/templates/upload`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminProposalTemplates` | 9 | Implementation entry; inspect this symbol for details |

## frontend/src/modules/module-3/module-3.css
Lines: 10. 
Frontend entry import graph: reachable.

## frontend/src/modules/module-3/ProposalComplianceWorkspace.tsx
Lines: 140. 
Frontend entry import graph: reachable.
Imports: `react`, `./module-3.css`.
API references found in source (dynamic expressions may be partial): `/api/v1/proposal-compliance/${reviewerMode`, `/api/v1/proposal-compliance/reports/${id}`, `/api/v1/proposal-compliance/reports/${selectedId}/annotated`, `/api/v1/proposal-compliance/reports/${selectedId}/original`, `/api/v1/proposal-compliance/reports/${selectedId}/pdf`, `/api/v1/proposal-compliance/reports/${selectedId}/run`, `/api/v1/proposal-compliance/submissions`, `/api/v1/proposal-compliance/submissions/${id}/submit`, `/api/v1/proposal-compliance/submissions/${id}/withdraw`, `/api/v1/proposal-compliance/submissions/${selectedId}/status`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalComplianceWorkspace` | 18 | Implementation entry; inspect this symbol for details |

## frontend/src/observability.ts
Lines: 21. 
Frontend entry import graph: not reached by static imports.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `classifyHttpStatus` | 7 | Implementation entry; inspect this symbol for details |
| `observeFetch` | 9 | Implementation entry; inspect this symbol for details |

## frontend/src/PanelPortal.tsx
Lines: 2. 
Frontend entry import graph: not reached by static imports.
Imports: `./portals/evaluator/EvaluatorPortal`.

## frontend/src/PasswordField.tsx
Lines: 48. 
Frontend entry import graph: reachable.
Imports: `react`, `./passwordPolicy`, `./passwordPolicy`, `./passwordPolicy`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `PasswordField` | 27 | Implementation entry; inspect this symbol for details |

## frontend/src/passwordPolicy.ts
Lines: 32. 
Frontend entry import graph: reachable.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `PASSWORD_MIN_LENGTH` | 1 | Implementation entry; inspect this symbol for details |
| `PASSWORD_MAX_LENGTH` | 2 | Implementation entry; inspect this symbol for details |
| `getPasswordGuidance` | 12 | Implementation entry; inspect this symbol for details |
| `passwordPolicyError` | 29 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/admin/modules/archive/AdminArchiveProjects.tsx
Lines: 185. 
Frontend entry import graph: reachable.
Imports: `react`, `./OldProjectArchiveImport`.
API references found in source (dynamic expressions may be partial): `/api/v1/admin/archive/projects/${deleteTarget.id}`, `/api/v1/admin/archive/projects/${editing.id}`, `/api/v1/admin/archive/projects/repair-imported`, `/api/v1/admin/archive/projects?${query}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminArchiveProjects` | 46 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/admin/modules/archive/ArchiveManagement.tsx
Lines: 5. 
Frontend entry import graph: reachable.
Imports: `./AdminArchiveProjects`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ArchiveManagement` | 3 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/admin/modules/archive/OldProjectArchiveImport.tsx
Lines: 54. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/admin/archive/import/confirm`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `OldProjectArchiveImport` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/admin/modules/supervisor-requests/AdminSupervisorRequests.tsx
Lines: 18. 
Frontend entry import graph: not reached by static imports.
Imports: `./AdminSupervisorRequestsPdf`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminSupervisorRequests` | 16 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/admin/modules/supervisor-requests/AdminSupervisorRequestsPdf.tsx
Lines: 81. 
Frontend entry import graph: not reached by static imports.
Imports: `react`, `./RequestConversation`.
API references found in source (dynamic expressions may be partial): `/api/v1/admin/audit-events?target_type`, `/api/v1/supervisor-requests/admin/monitor${suffix}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminSupervisorRequestsPdf` | 26 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/admin/modules/supervisor-requests/ProposalReferenceSearch.tsx
Lines: 1. 
Frontend entry import graph: not reached by static imports.
Imports: `../../../student/modules/supervisor-selection/ProposalReferenceSearch`.

## frontend/src/portals/admin/modules/supervisor-requests/RequestConversation.tsx
Lines: 1. 
Frontend entry import graph: not reached by static imports.
Imports: `../../../student/modules/supervisor-selection/RequestConversation`.

## frontend/src/portals/coordinator/CoordinatorPortal.tsx
Lines: 23. 
Frontend entry import graph: reachable.
Imports: `react`, `./modules/supervisor-requests/CoordinatorRequestsPdf`, `./CoordinatorSidebar`, `../../modules/module-3/ProposalComplianceWorkspace`, `../student/student.css`, `../supervisor/modules/supervisor-requests/supervisor-requests.css`, `./modules/supervisor-requests/coordinator-requests.css`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CoordinatorPortal` | 11 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/CoordinatorSidebar.tsx
Lines: 9. 
Frontend entry import graph: reachable.
Imports: `../shared/RoleSidebar`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `coordinatorNav` | 3 | Implementation entry; inspect this symbol for details |
| `CoordinatorSidebar` | 7 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/CoordinatorArchive.tsx
Lines: 24. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/archived-projects/search${suffix}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CoordinatorArchive` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/CoordinatorGroupPolicies.tsx
Lines: 11. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/academic-cycles/${cycle.id}/group-policy`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CoordinatorGroupPolicies` | 6 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/CoordinatorLiveList.tsx
Lines: 35. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CoordinatorLiveList` | 18 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/CoordinatorOverview.tsx
Lines: 43. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/academic-cycles`, `/api/v1/dashboard/deadlines`, `/api/v1/document-requirements`, `/api/v1/supervisor-requests/coordinator/monitor`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CoordinatorOverview` | 18 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/supervisor-requests/coordinator-requests.css
Lines: 1. 
Frontend entry import graph: reachable.

## frontend/src/portals/coordinator/modules/supervisor-requests/CoordinatorRequests.tsx
Lines: 17. 
Frontend entry import graph: not reached by static imports.
Imports: `./CoordinatorRequestsPdf`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CoordinatorRequests` | 15 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/supervisor-requests/CoordinatorRequestsPdf.tsx
Lines: 90. 
Frontend entry import graph: reachable.
Imports: `react`, `./RequestConversation`, `./PanelScheduling`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor-requests/coordinator/monitor${suffix}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CoordinatorRequestsPdf` | 33 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/supervisor-requests/PanelScheduling.tsx
Lines: 17. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/panel-schedules`, `/api/v1/panel-schedules/${row.id}`, `/api/v1/panel-schedules/options`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `PanelScheduling` | 7 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/coordinator/modules/supervisor-requests/ProposalReferenceSearch.tsx
Lines: 1. 
Frontend entry import graph: not reached by static imports.
Imports: `../../../student/modules/supervisor-selection/ProposalReferenceSearch`.

## frontend/src/portals/coordinator/modules/supervisor-requests/RequestConversation.tsx
Lines: 1. 
Frontend entry import graph: reachable.
Imports: `../../../student/modules/supervisor-selection/RequestConversation`.

## frontend/src/portals/evaluator/evaluator.css
Lines: 1. 
Frontend entry import graph: reachable.

## frontend/src/portals/evaluator/EvaluatorOverview.tsx
Lines: 39. 
Frontend entry import graph: reachable.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluatorOverview` | 13 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/evaluator/EvaluatorPortal.tsx
Lines: 48. 
Frontend entry import graph: reachable.
Imports: `react`, `./EvaluatorOverview`, `./EvaluatorSidebar`, `../student/student.css`, `./evaluator.css`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluatorPortal` | 20 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/evaluator/EvaluatorSidebar.tsx
Lines: 28. 
Frontend entry import graph: reachable.
Imports: `./EvaluatorPortal`, `../shared/RoleSidebar`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluatorSidebar` | 16 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/shared/AdminSidebar.tsx
Lines: 22. 
Frontend entry import graph: reachable.
Imports: `./RoleSidebar`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AdminSidebar` | 18 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/shared/CollaborationChannels.tsx
Lines: 16. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/${role}/collaboration`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CollaborationChannels` | 6 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/shared/dashboard-nav.css
Lines: 375. 
Frontend entry import graph: not reached by static imports.

## frontend/src/portals/shared/portal-shell.css
Lines: 216. 
Frontend entry import graph: not reached by static imports.

## frontend/src/portals/shared/PortalShell.tsx
Lines: 41. 
Frontend entry import graph: not reached by static imports.
Imports: `react`, `./portal-shell.css`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `PortalShell` | 17 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/shared/role-sidebar.css
Lines: 217. 
Frontend entry import graph: reachable.

## frontend/src/portals/shared/RoleSidebar.tsx
Lines: 110. 
Frontend entry import graph: reachable.
Imports: `react`, `./role-sidebar.css`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SidebarIcon` | 66 | Implementation entry; inspect this symbol for details |
| `RoleSidebar` | 70 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/shared/sidebar-state.ts
Lines: 15. 
Frontend entry import graph: not reached by static imports.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `readSidebarCollapsed` | 1 | Implementation entry; inspect this symbol for details |
| `writeSidebarCollapsed` | 9 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/shared/SidebarProfile.tsx
Lines: 9. 
Frontend entry import graph: not reached by static imports.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SidebarProfile` | 3 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/components/GroupMembers.tsx
Lines: 40. 
Frontend entry import graph: reachable.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `GroupMembers` | 10 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/AgentSupervisionPanel.tsx
Lines: 17. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/agent-supervision/${teamId}/runs`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AgentSupervisionPanel` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/archive-knowledge.css
Lines: 1. 
Frontend entry import graph: reachable.

## frontend/src/portals/student/modules/ArchivedProjectDetail.tsx
Lines: 3. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/archived-projects/${projectId}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ArchivedProjectDetail` | 3 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/EvaluatorWorkflow.tsx
Lines: 16. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/panel-evaluations`, `/api/v1/panel-evaluations/schedule/${selected.id}`, `/api/v1/panel-schedules`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluatorWorkflow` | 8 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/knowledge-search/ArchivedProjectDetail.tsx
Lines: 1. 
Frontend entry import graph: not reached by static imports.
Imports: `../ArchivedProjectDetail`.

## frontend/src/portals/student/modules/knowledge-search/KnowledgeSearch.tsx
Lines: 1. 
Frontend entry import graph: reachable.
Imports: `../KnowledgeSearch`.

## frontend/src/portals/student/modules/KnowledgeSearch.tsx
Lines: 26. 
Frontend entry import graph: reachable.
Imports: `react`, `./ArchivedProjectDetail`.
API references found in source (dynamic expressions may be partial): `/api/v1/archived-projects/search${params.toString`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `KnowledgeSearch` | 7 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/StudentEvaluatorPortal.tsx
Lines: 18. 
Frontend entry import graph: reachable.
Imports: `react`, `../../evaluator/EvaluatorOverview`, `../../evaluator/EvaluatorSidebar`, `./EvaluatorWorkflow`, `../../../modules/module-3/ProposalComplianceWorkspace`, `../student.css`, `../../evaluator/evaluator.css`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentEvaluatorPortal` | 11 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/StudentPhasePlaceholder.tsx
Lines: 12. 
Frontend entry import graph: reachable.
Imports: `../StudentSidebar`, `./StudentProgressDashboard`, `../../../App`, `./StudentRequiredDocumentsComplete`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentPhasePlaceholder` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/StudentProgressDashboard.tsx
Lines: 115. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/group-channels/teams`, `/api/v1/project-progress/${kind}/${item.id}`, `/api/v1/project-progress/${teamId}`, `/api/v1/project-progress/${teamId}/${path}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentProgressDashboard` | 34 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/StudentRequiredDocuments.tsx
Lines: 3. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements/${item.id}/upload`, `/api/v1/document-requirements/student`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentRequiredDocuments` | 3 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/StudentRequiredDocumentsComplete.tsx
Lines: 6. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/document-requirements/${id}/upload`, `/api/v1/document-requirements/${x.id}/submission`, `/api/v1/document-requirements/submissions/${sub.id}/versions/${v.id}/download`, `/api/v1/student/document-requirements`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentRequiredDocumentsComplete` | 6 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/StudentRequiredDocumentsDashboard.tsx
Lines: 27. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/student/group/requirements`, `/api/v1/student/group/requirements/${item.id}/${endpoint}`, `/api/v1/student/group/requirements/${item.id}/submission`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentRequiredDocumentsDashboard` | 16 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/StudentSupervisorInfo.tsx
Lines: 36. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/student/group/me`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentSupervisorInfo` | 17 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/supervisor-selection/ProposalReferenceSearch.tsx
Lines: 23. 
Frontend entry import graph: not reached by static imports.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/proposal-references/search?q`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalReferenceSearch` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/supervisor-selection/RequestConversation.tsx
Lines: 52. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor-requests/${requestId}/conversation`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `RequestConversation` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/supervisor-selection/StudentSupervisorSelection.tsx
Lines: 32. 
Frontend entry import graph: reachable.
Imports: `./StudentSupervisorSelectionPdf`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentSupervisorSelection` | 30 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/supervisor-selection/StudentSupervisorSelectionPdf.tsx
Lines: 41. 
Frontend entry import graph: reachable.
Imports: `react`, `./supervisor-selection.css`, `./RequestConversation`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor-requests`, `/api/v1/supervisor-requests/${preview.id}/confirm`, `/api/v1/supervisor-requests/${preview.id}/submit`, `/api/v1/supervisor-requests/${record.id}/withdraw`, `/api/v1/supervisor-requests/cycles`, `/api/v1/supervisor-requests/draft/${editingId}/document`, `/api/v1/supervisor-requests/mine`, `/api/v1/supervisor-requests/supervisors?academic_cycle_id`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentSupervisorSelectionPdf` | 27 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/modules/supervisor-selection/supervisor-selection.css
Lines: 2. 
Frontend entry import graph: reachable.

## frontend/src/portals/student/student-admin-theme.css
Lines: 134. 
Frontend entry import graph: reachable.

## frontend/src/portals/student/student-content.css
Lines: 197. 
Frontend entry import graph: reachable.

## frontend/src/portals/student/student-visibility.css
Lines: 2. 
Frontend entry import graph: reachable.

## frontend/src/portals/student/student.css
Lines: 3. 
Frontend entry import graph: reachable.

## frontend/src/portals/student/StudentOverview.tsx
Lines: 56. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/notifications`, `/api/v1/student/group/me`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentOverview` | 20 | Implementation entry; inspect this symbol for details |
| `StudentOverviewWithDocuments` | 54 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/StudentPortal.tsx
Lines: 56. 
Frontend entry import graph: reachable.
Imports: `react`, `./StudentOverview`, `./StudentSidebar`, `./modules/StudentPhasePlaceholder`, `./modules/StudentRequiredDocumentsDashboard`, `./modules/supervisor-selection/StudentSupervisorSelection`, `./modules/knowledge-search/KnowledgeSearch`, `../../modules/module-3/ProposalComplianceWorkspace`, `./components/GroupMembers`, `./modules/StudentSupervisorInfo`, `./student.css`, `./student-content.css`, `./student-admin-theme.css`, `./modules/archive-knowledge.css`, `./student-visibility.css`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `STUDENT_PHASES` | 35 | Implementation entry; inspect this symbol for details |
| `StudentPortal` | 46 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/student/StudentSidebar.tsx
Lines: 43. 
Frontend entry import graph: reachable.
Imports: `../shared/RoleSidebar`, `react`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `StudentSidebar` | 19 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/modules/supervisor-requests/ProposalReferenceSearch.tsx
Lines: 1. 
Frontend entry import graph: not reached by static imports.
Imports: `../../../student/modules/supervisor-selection/ProposalReferenceSearch`.

## frontend/src/portals/supervisor/modules/supervisor-requests/RequestConversation.tsx
Lines: 1. 
Frontend entry import graph: reachable.
Imports: `../../../student/modules/supervisor-selection/RequestConversation`.

## frontend/src/portals/supervisor/modules/supervisor-requests/supervisor-requests.css
Lines: 2. 
Frontend entry import graph: reachable.

## frontend/src/portals/supervisor/modules/supervisor-requests/SupervisorRequests.tsx
Lines: 21. 
Frontend entry import graph: not reached by static imports.
Imports: `./SupervisorRequestsPdf`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorRequests` | 19 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/modules/supervisor-requests/SupervisorRequestsPdf.tsx
Lines: 29. 
Frontend entry import graph: reachable.
Imports: `react`, `./RequestConversation`, `../../SupervisorGroupDetails`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor/requests`, `/api/v1/supervisor/requests/${selected.id}/${action}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorRequestsPdf` | 6 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/supervisor-capacity.css
Lines: 1. 
Frontend entry import graph: reachable.

## frontend/src/portals/supervisor/SupervisorAssignedTeams.tsx
Lines: 32. 
Frontend entry import graph: reachable.
Imports: `react`, `./SupervisorGroupDetails`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor/assigned-groups`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorAssignedTeams` | 4 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/SupervisorCapacity.tsx
Lines: 18. 
Frontend entry import graph: reachable.
Imports: `react`, `./supervisor-capacity.css`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor/capacity`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorCapacity` | 10 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/SupervisorDecisionHistory.tsx
Lines: 9. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor-requests/supervisor/queue?status`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorDecisionHistory` | 5 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/SupervisorGroupDetails.tsx
Lines: 52. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor/groups/${data.group.id}/conversation`, `/api/v1/supervisor/groups/${groupId}`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `date` | 18 | Implementation entry; inspect this symbol for details |
| `GroupDetailsContent` | 34 | Implementation entry; inspect this symbol for details |
| `SupervisorGroupDetails` | 47 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/SupervisorOverview.tsx
Lines: 18. 
Frontend entry import graph: reachable.
Imports: `react`.
API references found in source (dynamic expressions may be partial): `/api/v1/supervisor-requests/supervisor/queue?status`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorOverview` | 7 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/SupervisorPortal.tsx
Lines: 20. 
Frontend entry import graph: reachable.
Imports: `react`, `./modules/supervisor-requests/SupervisorRequestsPdf`, `./SupervisorSidebar`, `./SupervisorOverview`, `./SupervisorAssignedTeams`, `./SupervisorDecisionHistory`, `./SupervisorUnavailable`, `./SupervisorCapacity`, `../student/student.css`, `./modules/supervisor-requests/supervisor-requests.css`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorPortal` | 14 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/SupervisorSidebar.tsx
Lines: 23. 
Frontend entry import graph: reachable.
Imports: `../shared/RoleSidebar`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `supervisorNav` | 3 | Implementation entry; inspect this symbol for details |
| `SupervisorSidebar` | 11 | Implementation entry; inspect this symbol for details |

## frontend/src/portals/supervisor/SupervisorUnavailable.tsx
Lines: 3. 
Frontend entry import graph: reachable.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorUnavailable` | 1 | Implementation entry; inspect this symbol for details |

## backend/alembic/env.py
Lines: 45. Alembic environment using the FYPHub application database configuration.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `run_migrations_offline` | 20 | Run migrations without a live database connection. |
| `run_migrations_online` | 33 | Run migrations with the shared synchronous application engine. |

## backend/alembic/versions/3a1f53f17b1c_add_academic_cycles_and_group_policies.py
Lines: 56. add academic cycles and group policies
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Apply this revision. |
| `downgrade` | 50 | Revert this revision. |

## backend/alembic/versions/9415b228314f_join_requests_and_creator_proof_binding.py
Lines: 75. join requests and creator proof binding
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Apply this revision. |
| `downgrade` | 64 | Revert this revision. |

## backend/alembic/versions/9c227dc337bf_create_users_foundation.py
Lines: 49. create users foundation
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Apply this revision. |
| `downgrade` | 44 | Revert this revision. |

## backend/alembic/versions/a2b3c4d5e6f7_add_academic_deadline_versions.py
Lines: 40. add academic deadline configuration versions
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 16 | Implementation entry; inspect this symbol for details |
| `downgrade` | 38 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/a3b4c5d6e7f8_bind_anonymous_join_proof_target.py
Lines: 48. bind anonymous join proof target
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Apply this revision. |
| `downgrade` | 33 | Revert this revision. |

## backend/alembic/versions/a7b8c9d0e1f2_add_group_messages.py
Lines: 14. Add retained team channel messages.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 13 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/a8467cad28da_invitation_transactional_outbox.py
Lines: 37. invitation transactional outbox
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Implementation entry; inspect this symbol for details |
| `downgrade` | 34 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/b2c3d4e5f6a7_student_matching_proof.py
Lines: 17. Allow a distinct anonymous student matching proof.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 14 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/b3c4d5e6f7a8_add_reminder_rules.py
Lines: 15. Add non-operational reminder rule versions.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 13 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/b8c9d0e1f2a3_add_team_match_preferences.py
Lines: 13. Add team compatibility preferences.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 12 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/b8d2e4f6a9c1_add_admin_audit_events.py
Lines: 55. add append-only administrator audit events
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Implementation entry; inspect this symbol for details |
| `downgrade` | 50 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/c3d4e5f6a7b8_proposal_foundation.py
Lines: 37. Add non-operational proposal identity and version foundations.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 15 | Implementation entry; inspect this symbol for details |
| `downgrade` | 35 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/c4d5e6f7a8b9_add_student_roster.py
Lines: 17. Add approved student roster and import provenance.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 15 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/c4e7f1a2b9d3_add_audit_targets.py
Lines: 25. add explicit audit targets
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 15 | Implementation entry; inspect this symbol for details |
| `downgrade` | 22 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/c5d6e7f8a9b0_add_supervisor_requests.py
Lines: 67. add student supervisor-selection requests and immutable history
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 16 | Implementation entry; inspect this symbol for details |
| `downgrade` | 59 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/c9d0e1f2a3b4_add_match_chat.py
Lines: 16. Add temporary match chats and retained messages.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 14 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/ce964120f177_add_teams_and_member_duplicate_.py
Lines: 68. add teams and member duplicate constraints
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Apply this revision. |
| `downgrade` | 60 | Revert this revision. |

## backend/alembic/versions/d0e1f2a3b4c5_match_chat_mutual_reconsent.py
Lines: 17. Allow new match conversations after mutual fresh consent.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 14 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/d5e6f7a8b9c0_add_template_reference_versions.py
Lines: 10. add internal template reference and rule versions
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 6 | Implementation entry; inspect this symbol for details |
| `downgrade` | 10 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/d6e7f8a9b0c1_add_supervisor_request_documents.py
Lines: 81. add immutable one-page proposal documents and extraction snapshots
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 18 | Implementation entry; inspect this symbol for details |
| `downgrade` | 63 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/e1f2a3b4c5d6_individual_verification.py
Lines: 19. Store roster-bound verification challenges and one-use proofs.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 15 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/e5f6a7b8c9d0_add_workflow_policy_drafts.py
Lines: 15. Add non-operational workflow policy drafts.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 13 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/e7f8a9b0c1d2_add_proposal_references_and_request_conversations.py
Lines: 65. add authorized proposal references and request conversations
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 14 | Implementation entry; inspect this symbol for details |
| `downgrade` | 56 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/e8f9a0b1c2d3_add_supervisor_capacity_policies.py
Lines: 27. add supervisor capacity policies
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 26 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/eb100aa929ab_team_invitations.py
Lines: 71. team invitations
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Apply this revision. |
| `downgrade` | 62 | Revert this revision. |

## backend/alembic/versions/f1a2b3c4d5e6_add_evaluation_rubric_drafts.py
Lines: 47. add evaluation rubric draft versions
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 16 | Implementation entry; inspect this symbol for details |
| `downgrade` | 44 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/f2a3b4c5d6e7_anonymous_verification.py
Lines: 82. anonymous verification
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 21 | Apply this revision. |
| `downgrade` | 74 | Revert this revision. |

## backend/alembic/versions/f6a7b8c9d0e1_add_supervisor_assignments.py
Lines: 14. Add supervisor allocation history.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Implementation entry; inspect this symbol for details |
| `downgrade` | 13 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/f7a1c3d9e2b4_add_auth_sessions.py
Lines: 40. add hash-only browser authentication sessions
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 20 | Implementation entry; inspect this symbol for details |
| `downgrade` | 37 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/f9a0b1c2d3e4_add_archived_projects.py
Lines: 69. add logical archived projects and immutable document versions
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 14 | Implementation entry; inspect this symbol for details |
| `downgrade` | 62 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fa0b1c2d3e4_allow_archived_title_reuse_after_deactivation.py
Lines: 20. allow archived title reuse after deactivation
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 18 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fb1c2d3e4f5_add_historical_archive_fields.py
Lines: 39. add structured historical project archive fields
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 36 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fb1c2d3e4f5a_add_module03_proposal_compliance.py
Lines: 53. add Module 03 dynamic proposal compliance tables
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_jsonb` | 14 | Implementation entry; inspect this symbol for details |
| `upgrade` | 18 | Implementation entry; inspect this symbol for details |
| `downgrade` | 47 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fc2d3e4f5a6b_add_supervisor_request_submission_notes.py
Lines: 38. add optional immutable supervisor-request submission note versions
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 32 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fc6b7c8d9e0f_add_private_collaboration_channels.py
Lines: 60. add assignment-scoped private Module 2 collaboration channels
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 53 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fd3e4f5a6b7c_add_fyp_registry_metadata.py
Lines: 32. add safe administrative metadata for the FYP registry
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 30 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fe4f5a6b7c8d_add_password_reset_tokens.py
Lines: 32. add hash-only password reset tokens
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 29 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/ff5a6b7c8d9e_add_progress_scheduling_evaluation.py
Lines: 126. add persisted progress, defense scheduling, and panel evaluation workflows
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 14 | Implementation entry; inspect this symbol for details |
| `downgrade` | 115 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fg6b7c8d9e0f_add_module03_template_versions.py
Lines: 37. add immutable Module 03 template metadata and rule version provenance
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 14 | Implementation entry; inspect this symbol for details |
| `downgrade` | 27 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fh7c8d9e0f1a_add_module03_activation_mode.py
Lines: 18. Persist complete or partial Module 03 baseline activation mode.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 17 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fi8d9e0f1a2b_continue_proposal_chain.py
Lines: 14. Continue the proposal foundation migration chain.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 9 | Converge the already-applied migration branches without changing data. |
| `downgrade` | 13 | Re-expose the proposal foundation parent for historical downgrades. |

## backend/alembic/versions/fj9e0f1a2b3_add_proposal_type.py
Lines: 19. Store the selected SHORT/LONG type on supervisor-request proposals.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 17 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fk0f1a2b3c4_add_proposal_metadata_fields.py
Lines: 19. Add editable proposal metadata snapshots to the existing lifecycle records.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 17 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/fl1a2b3c4d5_add_agent_supervision_runs.py
Lines: 33. Add controlled supervision agent run records.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 11 | Implementation entry; inspect this symbol for details |
| `downgrade` | 31 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/gm2b3c4d5e6f_add_dashboard_requirements.py
Lines: 42. Add role-scoped dashboard requirements.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 11 | Implementation entry; inspect this symbol for details |
| `downgrade` | 38 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/hn3c4d5e6f7a_add_document_upload_requirements.py
Lines: 35. add admin-managed document upload requirements
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 15 | Implementation entry; inspect this symbol for details |
| `downgrade` | 34 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/jk4d5e6f7a8b_document_storage_reference.py
Lines: 15. make document version content optional for persistent file storage
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 14 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/kl5e6f7a8b9c_add_role_based_fyp_evaluations.py
Lines: 78. add independent role-based FYP evaluations and result audit history
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 69 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/lm6f7a8b9c0d_remove_evaluation_marks_module.py
Lines: 37. Remove the retired Evaluation & Marks module.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 16 | Implementation entry; inspect this symbol for details |
| `downgrade` | 36 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/m123a001_modules_1_3_lifecycle.py
Lines: 43. Join existing histories; add proposal lifecycle and membership consent only.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 15 | Implementation entry; inspect this symbol for details |
| `downgrade` | 34 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/mn7c8d9e0f1a_restore_role_based_evaluations.py
Lines: 97. restore the role-based FYP evaluation and results module
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 14 | Implementation entry; inspect this symbol for details |
| `downgrade` | 87 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/mo8r9e0f1a2b_add_proposal_ai_review_runs.py
Lines: 32. Persist advisory AI review runs for supervisor proposal requests.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 14 | Implementation entry; inspect this symbol for details |
| `downgrade` | 30 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/n456a001_add_academic_cycle_year_session.py
Lines: 40. Persist the year and session selected when creating an academic cycle.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 35 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/oa1b2c3d4e5f_repair_module1_evaluation_schema.py
Lines: 89. Repair Module 1 evaluation tables after removing the retired compliance branch.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 18 | Implementation entry; inspect this symbol for details |
| `downgrade` | 86 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/ob1c2d3e4f5a_repair_module1_identity_columns.py
Lines: 38. Add identity generation to tables created by the Module 1 repair migration.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 37 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/oc1d2e3f4a5b_add_template_activation.py
Lines: 24. Compatibility migration for the existing template activation state.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 20 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/p567a001_supervisor_capacity_year_session.py
Lines: 75. Add year/session identity to supervisor capacity policies.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 17 | Implementation entry; inspect this symbol for details |
| `downgrade` | 70 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/pa1b2c3d4e5f_add_module03_compliance_workspace.py
Lines: 62. Add the Module 3 proposal compliance workspace.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 14 | Implementation entry; inspect this symbol for details |
| `downgrade` | 57 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/qa1b2c3d4e5f_complete_module02_collaboration.py
Lines: 122. Complete Module 2 team lifecycle, matching and collaboration foundations.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 88 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/r678a001_remove_registry_roster_identity_modules.py
Lines: 55. Remove registry, roster, workflow-draft, invitation and identity modules.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 17 | Implementation entry; inspect this symbol for details |
| `downgrade` | 54 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/r678a002_remove_invitation_outbox.py
Lines: 17. Remove the transactional outbox belonging to retired invitations.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 16 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/r678a003_annual_supervisor_capacity.py
Lines: 101. Make supervisor capacity annual and shared across Fall and Spring.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 93 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/rd7e8f9a0b1c_repair_archive_import_columns.py
Lines: 44. Repair archive storage columns on the active collaboration migration branch.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 13 | Implementation entry; inspect this symbol for details |
| `downgrade` | 42 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/re8f9a0b1c2d_archive_import_batches.py
Lines: 52. Persist archive import batches and append-safe duplicate keys.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 46 | Implementation entry; inspect this symbol for details |

## backend/alembic/versions/rf9a0b1c2d3e_document_requirement_lifecycle.py
Lines: 33. Normalize document requirement lifecycle and bind submissions to groups.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `upgrade` | 12 | Implementation entry; inspect this symbol for details |
| `downgrade` | 29 | Implementation entry; inspect this symbol for details |

## backend/tests/__init__.py
Lines: 1. Backend test package.

## backend/tests/test_academic_cycle_overview.py
Lines: 146. Authorized academic-cycle overview coverage for Admin and Coordinator portals.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `request` | 22 | Implementation entry; inspect this symbol for details |
| `AcademicCycleOverviewTests` | 66 | Implementation entry; inspect this symbol for details |
Test cases: `test_admin_and_coordinator_receive_empty_structured_overview`, `test_overview_rejects_missing_session_student_and_unknown_cycle`, `test_overview_route_is_registered_in_openapi`, `test_fall_2027_list_id_resolves_for_admin_and_coordinator`.

## backend/tests/test_academic_deadlines.py
Lines: 227. Rollback-isolated coverage for non-operational academic deadlines.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AcademicDeadlineTests` | 23 | Implementation entry; inspect this symbol for details |
Test cases: `test_authorization_and_origin_rejection`, `test_unknown_cycle_and_strict_validation`, `test_naive_writes_leave_versions_and_audit_unchanged`, `test_missing_timezone_data_returns_service_error`, `test_timezone_conversion_mismatch_gap_and_overlap`, `test_initial_subsequent_and_ordered_history`, `test_audit_failure_rolls_back_subsequent_version`, `test_controlled_concurrent_version_allocation`.

## backend/tests/test_admin_users.py
Lines: 238. Rollback-isolated coverage for M1-B administrator account management.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `request` | 21 | Implementation entry; inspect this symbol for details |
| `AdminUserTests` | 49 | Implementation entry; inspect this symbol for details |
Test cases: `test_listing_authorization_search_and_safe_values`, `test_pagination_uses_the_requested_page`, `test_last_admin_lock_is_exclusive_across_database_connections`, `test_creation_duplicate_and_atomic_audit`, `test_creation_rejects_malformed_email`, `test_admin_can_create_each_fixed_non_public_role`, `test_role_status_session_revocation_and_last_admin_protection`, `test_shared_team_protection_and_append_only_database_trigger`, `test_cycle_policy_management_and_audit_target`, `test_academic_cycle_creation_requires_year_and_session`, `test_academic_cycle_creation_persists_year_and_session`.

## backend/tests/test_ai_proposal_review.py
Lines: 45. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AiProposalReviewTests` | 6 | Implementation entry; inspect this symbol for details |
Test cases: `test_deterministic_fallback_returns_structured_findings`, `test_missing_document_fallback_is_unavailable_and_structured`, `test_fallback_preserves_deterministic_evidence`.

## backend/tests/test_archive_import.py
Lines: 91. Excel imports preserve source columns without an archive schema.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ArchiveImportValidationTests` | 9 | Implementation entry; inspect this symbol for details |
Test cases: `test_arbitrary_columns_and_values_are_preserved`, `test_legacy_xls_keeps_columns_values_and_dates`, `test_no_required_fields_or_cycle_matching`, `test_duplicate_and_blank_headers_and_blank_cells`, `test_all_worksheets_and_repeated_rows_are_kept`, `test_headerless_and_explicit_heading_row`, `test_formulas_and_excel_errors_are_not_imported_as_content`, `test_stops_after_last_email_and_ignores_trailing_formula_or_spacing_rows`, `test_whitespace_only_cells_are_blank`.

## backend/tests/test_archive_import_persistence.py
Lines: 73. Confirm and edit flexible imports inside a rolled-back database transaction.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ArchiveImportPersistenceTests` | 15 | Implementation entry; inspect this symbol for details |
Test cases: `test_confirm_and_edit_only_original_columns`, `test_http_preview_and_confirm_use_flexible_columns`.

## backend/tests/test_archived_projects.py
Lines: 142. Focused logical archive, versioning, ranking, and role-isolation tests.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ArchivedProjectTests` | 23 | Implementation entry; inspect this symbol for details |
Test cases: `test_admin_create_search_detail_and_panel_denial`, `test_pdf_versions_are_separate_and_student_read_only`, `test_metadata_refresh_duplicate_protection_and_inactive_filtering`, `test_metadata_audit_snapshot_can_be_rolled_back`.

## backend/tests/test_audit_history.py
Lines: 59. Rollback-isolated read-only audit viewer tests.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AuditHistoryTests` | 11 | Implementation entry; inspect this symbol for details |
Test cases: `test_authorization_and_missing`, `test_filter_pagination_order_and_read_only`, `test_legacy_and_sensitive_data_exclusion`, `test_strict_filters`.

## backend/tests/test_auth_sessions.py
Lines: 479. Rollback-isolated integration tests for cookie-backed authentication.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `request` | 26 | Invoke ASGI without adding a test client dependency. |
| `AuthSessionTests` | 65 | Implementation entry; inspect this symbol for details |
Test cases: `test_login_safe_cookie_and_me`, `test_login_session_is_usable_by_proposal_endpoints`, `test_bad_unknown_and_inactive_credentials_are_generic`, `test_malformed_email_login_is_rejected_before_authentication`, `test_creator_registration_login_and_selected_role_cannot_escalate`, `test_admin_endpoint_requires_persisted_admin_role`, `test_missing_tampered_expired_revoked_and_deactivated_sessions`, `test_session_rotation_logout_and_idempotent_logout`, `test_same_valid_session_supports_concurrent_requests`, `test_deactivation_revokes_every_active_session_for_the_user`, `test_origin_cors_and_role_helpers`, `test_authenticated_admin_can_create_document_requirement`, `test_admin_published_document_requirement_is_visible_to_student`, `test_forgot_password_is_generic_and_stores_only_a_hash`, `test_reset_password_rejects_weak_and_consumes_token_revoking_sessions`, `test_new_request_invalidates_old_token_and_expired_token_is_rejected`, `test_development_without_smtp_exposes_only_loopback_reset_link`, `test_development_with_smtp_never_exposes_local_link`, `test_production_without_smtp_keeps_safe_unavailable_status`, `test_demo_mode_unknown_email_uses_development_message_without_smtp`.

## backend/tests/test_collaboration_channels.py
Lines: 27. Focused contract tests for the private Module 2 collaboration channel API.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `CollaborationChannelContractTests` | 11 | Implementation entry; inspect this symbol for details |
Test cases: `test_blank_messages_are_rejected`, `test_message_text_is_trimmed`, `test_private_channel_routes_exist`.

## backend/tests/test_coordinator_operations.py
Lines: 18. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `test_coordinator_read_only_routes_are_registered` | 5 | Implementation entry; inspect this symbol for details |
| `test_coordinator_operations_are_read_only_get_routes` | 17 | Implementation entry; inspect this symbol for details |

## backend/tests/test_cycle_concurrency.py
Lines: 282. True multi-connection coverage for cycle configuration and team registration.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_RequestWithoutOrigin` | 42 | The direct endpoint call has the same permitted no-Origin boundary as tests. |
| `CycleConcurrencyTests` | 48 | Exercise the production cycle-then-policy lock order with real sessions. |
Test cases: `test_registration_finishes_before_a_waiting_registration_closure`, `test_policy_reduction_rejects_after_waiting_registration_commits`.

## backend/tests/test_document_requirements_contract.py
Lines: 46. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `test_document_requirement_models_and_routes_exist` | 7 | Implementation entry; inspect this symbol for details |
| `test_supported_file_mimes_and_states` | 14 | Implementation entry; inspect this symbol for details |
| `test_exact_document_requirement_paths_are_registered_in_openapi` | 20 | Implementation entry; inspect this symbol for details |
| `test_storage_reference_is_relative_and_path_traversal_is_rejected` | 34 | Implementation entry; inspect this symbol for details |
| `test_file_format_adapter_preserves_single_and_combined_formats` | 40 | Implementation entry; inspect this symbol for details |

## backend/tests/test_document_requirements_visibility.py
Lines: 62. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_Rows` | 8 | Implementation entry; inspect this symbol for details |
| `_Db` | 16 | Implementation entry; inspect this symbol for details |
| `_student` | 24 | Implementation entry; inspect this symbol for details |
| `_requirement` | 28 | Implementation entry; inspect this symbol for details |
| `test_published_all_students_requirement_appears` | 37 | Implementation entry; inspect this symbol for details |
| `test_student_specific_requirement_appears_only_for_that_student` | 44 | Implementation entry; inspect this symbol for details |
| `test_draft_and_archived_requirements_stay_hidden` | 51 | Implementation entry; inspect this symbol for details |
| `test_requirement_for_another_student_stays_hidden` | 58 | Implementation entry; inspect this symbol for details |

## backend/tests/test_evaluation_rubrics.py
Lines: 184. Rollback-isolated coverage for internal evaluation-rubric drafts.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluationRubricTests` | 21 | Implementation entry; inspect this symbol for details |
Test cases: `test_authorization_origin_and_missing_record`, `test_validation_rejects_blank_duplicate_order_and_extra_fields`, `test_ordered_history_preserves_prior_version`, `test_audit_failure_rolls_back_complete_version`, `test_concurrent_version_numbers_are_distinct`.

## backend/tests/test_evaluations.py
Lines: 135. Integration coverage for role-owned marks and published result aggregation.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `EvaluationWorkflowTests` | 18 | Implementation entry; inspect this symbol for details |
Test cases: `test_role_ownership_and_submission_lock`, `test_panel_records_are_independent_and_admin_can_monitor`, `test_approve_publish_and_student_results`, `test_report_access_and_unauthorized_student`, `test_admin_correction_and_panel_aggregation_are_audited`.

## backend/tests/test_groq_configuration.py
Lines: 13. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `GroqConfigurationTests` | 6 | Implementation entry; inspect this symbol for details |
Test cases: `test_key_is_optional_for_ollama`.

## backend/tests/test_groq_provider.py
Lines: 63. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_Response` | 9 | Implementation entry; inspect this symbol for details |
| `_StatusClient` | 16 | Implementation entry; inspect this symbol for details |
| `_Client` | 25 | Implementation entry; inspect this symbol for details |
| `GroqProviderTests` | 33 | Implementation entry; inspect this symbol for details |
Test cases: `test_success_uses_exact_endpoint_headers_and_model`, `test_missing_key_falls_back_without_request`, `test_unauthorized_and_invalid_model_are_classified`.

## backend/tests/test_group_access.py
Lines: 96. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `request_scope` | 16 | Implementation entry; inspect this symbol for details |
| `GroupAccessTests` | 32 | Implementation entry; inspect this symbol for details |
Test cases: `test_group_login_returns_saved_role_and_group_context`, `test_registration_number_login_is_rejected`, `test_dissolved_group_cannot_login`.

## backend/tests/test_group_ai.py
Lines: 53. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `GroupAITests` | 13 | Implementation entry; inspect this symbol for details |
Test cases: `test_authorization_and_team_isolation`, `test_configured_model_and_history`, `test_missing_configuration_timeout_and_runtime_error`, `test_agent_model_falls_back_to_configured_local_model`.

## backend/tests/test_group_channels.py
Lines: 51. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `GroupChannelTests` | 12 | Implementation entry; inspect this symbol for details |
Test cases: `test_permissions_all_channels`, `test_history_reassignment_and_safe_rollback`.

## backend/tests/test_module3_compliance_engine.py
Lines: 107. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `test_template_upload_contract_only_accepts_pdf_and_docx` | 7 | Implementation entry; inspect this symbol for details |
| `test_compliance_report_reconciles_findings_and_locations` | 16 | Implementation entry; inspect this symbol for details |
| `test_compliance_report_checks_structure_and_academic_consistency` | 52 | Implementation entry; inspect this symbol for details |
| `test_version_change_summary_is_structured_and_advisory` | 88 | Implementation entry; inspect this symbol for details |
| `test_module3_lifecycle_and_review_routes_are_exposed` | 101 | Implementation entry; inspect this symbol for details |

## backend/tests/test_observability.py
Lines: 15. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ObservabilityTests` | 6 | Implementation entry; inspect this symbol for details |
Test cases: `test_workflow_names_are_safe_and_specific`.

## backend/tests/test_ollama_provider.py
Lines: 66. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `_Response` | 9 | Implementation entry; inspect this symbol for details |
| `_Client` | 19 | Implementation entry; inspect this symbol for details |
| `OllamaProviderTests` | 29 | Implementation entry; inspect this symbol for details |
Test cases: `test_chat_request_is_local_non_streaming_and_schema_validated`, `test_invalid_response_returns_fallback`, `test_timeout_returns_fallback`.

## backend/tests/test_password_policy.py
Lines: 62. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `PasswordPolicyTests` | 10 | Implementation entry; inspect this symbol for details |
Test cases: `test_shared_policy_accepts_compliant_password`, `test_shared_policy_reports_each_missing_requirement`, `test_shared_policy_rejects_overlong_values`, `test_student_and_admin_creation_schemas_use_shared_policy`, `test_admin_registration_number_is_role_dependent`.

## backend/tests/test_pdf_extraction.py
Lines: 71. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `PdfExtractionFieldTests` | 9 | Implementation entry; inspect this symbol for details |
Test cases: `test_demo_headings_extract_all_sections_until_next_heading`, `test_labels_are_case_insensitive_and_aliases_are_supported`, `test_missing_field_remains_not_detected_without_fabrication`, `test_normalization_preserves_sections_and_colon_spacing`, `test_docx_upload_extracts_fields_with_immutable_file_metadata`, `test_unsupported_upload_is_rejected`.

## backend/tests/test_project_workflow.py
Lines: 93. Focused coverage for persisted progress, scheduling, and evaluation workflows.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProjectWorkflowTests` | 18 | Implementation entry; inspect this symbol for details |
Test cases: `test_progress_milestones_tasks_meetings_and_health`, `test_progress_cross_team_denial`, `test_schedule_assignment_conflict_and_reschedule`, `test_panel_evaluation_submission_disagreement_and_resolution`.

## backend/tests/test_proposal_foundation.py
Lines: 48. Isolated checks for the non-operational proposal schema.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalFoundationTests` | 7 | Implementation entry; inspect this symbol for details |
Test cases: `test_short_long_and_independent_version_sequences`, `test_invalid_type_and_missing_team_are_rejected`, `test_invalid_version_duplicate_and_missing_parent_are_rejected`, `test_proposal_lifecycle_routes_are_exposed`.

## backend/tests/test_proposal_reference_and_conversation.py
Lines: 123. Reference-search and request-conversation authorization coverage.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ProposalReferenceAndConversationTests` | 21 | Implementation entry; inspect this symbol for details |
Test cases: `test_title_search_exact_similar_and_no_close`, `test_reference_pdf_and_panel_denial`, `test_request_conversation_scope_and_panel_denial`.

## backend/tests/test_registration.py
Lines: 228. Integration tests for public student registration.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `request_json` | 19 | Make an in-process ASGI request without requiring a test HTTP client package. |
| `RegistrationIntegrationTests` | 59 | Registration tests whose database writes are rolled back as one outer transaction. |
Test cases: `test_password_hashing_and_verification`, `test_individual_public_registration_is_rejected`, `test_successful_student_registration_stores_only_hash`, `test_demo_mode_allows_unlisted_student_and_records_mode`, `test_duplicate_normalized_email_returns_conflict`, `test_common_consumer_and_institutional_domains_are_accepted`, `test_duplicate_normalized_registration_number_returns_conflict`, `test_invalid_email_missing_fields_and_password_lengths_are_rejected`, `test_privileged_request_fields_are_rejected`.

## backend/tests/test_reminder_rules.py
Lines: 97. Isolated non-operational reminder configuration coverage.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `ReminderTests` | 16 | Implementation entry; inspect this symbol for details |
Test cases: `test_auth_origin_and_validation`, `test_dst_exact_link_history_and_cross_cycle`, `test_overflow_and_atomic_audit`, `test_concurrent_allocation`.

## backend/tests/test_retired_modules.py
Lines: 23. Focused assertions for the retired registry/roster/identity surface.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `test_retired_api_routes_are_not_registered` | 6 | Implementation entry; inspect this symbol for details |

## backend/tests/test_supervisor_assignments.py
Lines: 84. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `AssignmentTests` | 13 | Implementation entry; inspect this symbol for details |
Test cases: `test_authorization_validation_history_and_capacity`, `test_wrong_cycle_ineligible_and_audit_rollback`, `test_fall_and_spring_share_annual_capacity_and_counts`, `test_00_concurrent_capacity`.

## backend/tests/test_supervisor_capacity.py
Lines: 145. Rollback-isolated coverage for M1-E.1 supervisor capacity configuration.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `request` | 21 | Implementation entry; inspect this symbol for details |
| `SupervisorCapacityTests` | 44 | Implementation entry; inspect this symbol for details |
Test cases: `test_00_capacity_advisory_lock_is_exclusive_across_connections`, `test_authorization_validation_eligibility_and_duplicate`, `test_update_historical_listing_and_capacity_lock`, `test_audit_failure_rolls_back_capacity`, `test_annual_policy_is_shared_by_fall_and_spring`, `test_capacity_status_and_update_cannot_drop_below_assignments`.

## backend/tests/test_supervisor_requests.py
Lines: 496. Focused authorization, lifecycle, capacity, and audit tests for supervisor requests.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorRequestTests` | 24 | Implementation entry; inspect this symbol for details |
Test cases: `test_eligible_supervisor_list_and_role_isolation`, `test_create_submit_and_student_list`, `test_duplicate_cross_cycle_and_stale_request_protection`, `test_supervisor_only_decision_comment_and_accept_assignment`, `test_accept_requires_registered_team_and_keeps_request_submitted`, `test_duplicate_assignment_is_rejected_without_accepting_request`, `test_accept_capacity_conflict_rolls_back_assignment_and_status`, `test_accept_audit_failure_rolls_back_assignment_and_status`, `test_reject_changes_resubmit_withdraw_and_history`, `test_capacity_full_inactive_supervisor_monitoring_and_audit_rollback`, `test_pdf_validation_and_missing_required_fields`, `test_pdf_preview_confirmation_and_authorized_original_document`, `test_owner_confirm_and_submit_only`, `test_submit_requires_confirmation_and_current_revision`, `test_cross_team_owner_and_missing_required_fields_are_denied`, `test_concurrent_submission_revision_safety`, `test_submission_note_is_optional_visible_and_immutable_by_version`, `test_fyp_registry_role_scopes_filters_and_supervisor_assignment`, `test_fyp_registry_detail_and_admin_metadata_are_audited_without_mutating_proposal`, `test_fyp_registry_student_ownership_and_cross_scope_are_enforced`.

## backend/tests/test_supervisor_workspace.py
Lines: 163. Transactional integration checks for the supervisor group workspace.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `SupervisorWorkspaceTests` | 19 | Implementation entry; inspect this symbol for details |
Test cases: `test_workspace_request_and_acceptance`, `test_workspace_ownership_and_download_denial`, `test_workspace_decision_comments`, `test_workspace_capacity_enforced`, `test_workspace_conversation_and_empty_states`, `test_workspace_empty_group`, `test_workspace_real_upload_download_and_refresh`, `test_student_submission_to_supervisor_assignment_flow`.

## backend/tests/test_team_compatibility.py
Lines: 12. 
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `TeamCompatibilityTests` | 4 | Implementation entry; inspect this symbol for details |
Test cases: `test_equal_weight_and_unanswered_excluded`, `test_no_answers_is_not_zero_score`, `test_unknown_or_non_boolean_assessment_is_rejected`.

## backend/tests/test_team_constraints.py
Lines: 340. Database integration tests for the applied team/member constraints.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `TeamConstraintTests` | 20 | Exercise constraints supplied by Alembic revision ``ce964120f177``. |
Test cases: `test_duplicate_registration_within_one_team_is_rejected`, `test_duplicate_active_registration_across_teams_in_one_cycle_is_rejected`, `test_duplicate_active_contact_email_in_one_cycle_is_rejected`, `test_noncanonical_registration_and_email_values_are_rejected`, `test_same_name_students_with_distinct_identifiers_are_allowed`, `test_member_team_cycle_mismatch_is_rejected`, `test_second_creator_is_rejected`, `test_shared_user_cannot_link_to_two_teams`, `test_member_identifiers_can_recur_in_different_academic_cycles`.

## backend/tests/test_team_registration.py
Lines: 598. Rollback-isolated API tests for shared-team registration.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `request_json` | 24 | Call the endpoint in process, without starting a server or adding a client library. |
| `cors_preflight` | 67 | Exercise CORS without a running HTTP server. |
| `TeamRegistrationApiTests` | 108 | API writes share an outer transaction and never retain fixture data. |
| `TeamEligibilityTests` | 485 | Roster enforcement uses the selected cycle and each member's contact email. |
Test cases: `test_successful_team_registration_creates_one_user_and_one_creator`, `test_student_group_registration_creates_one_shared_student_account`, `test_student_group_registration_rejects_privileged_role_fields`, `test_group_registration_accepts_only_names_and_registration_numbers`, `test_group_registration_enforces_configured_minimum`, `test_cors_allows_only_the_configured_frontend_origin`, `test_unknown_closed_and_missing_policy_cycles_return_safe_errors`, `test_configured_maximum_boundary_and_excess_members`, `test_request_and_existing_record_duplicate_conflicts`, `test_creator_registration_used_by_individual_account_is_rejected`, `test_invalid_and_privileged_fields_are_rejected`, `test_late_member_insert_failure_rolls_back_all_new_records`, `test_safe_error_for_existing_shared_login_email`, `test_password_confirmation_mismatch_is_rejected_before_creation`, `test_missing_creator_and_member_are_field_specific_and_atomic`, `test_wrong_cycle_and_mismatched_pair_are_rejected`, `test_normalization_and_shared_login_is_not_contact_email`, `test_invalid_semester_is_rejected_by_roster_constraint`, `test_demo_mode_allows_unlisted_one_two_and_three_member_teams`, `test_restricted_mode_and_invalid_mode_keep_roster_validation`, `test_demo_mode_records_audit_metadata_without_changing_security_validation`, `test_demo_mode_still_enforces_group_limit`.

## backend/tests/test_template_references.py
Lines: 156. Rollback-isolated regression coverage for internal template references.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `TemplateReferenceTests` | 17 | Implementation entry; inspect this symbol for details |
| `TemplateReferenceConcurrencyTests` | 128 | Implementation entry; inspect this symbol for details |
Test cases: `test_access_validation_and_history`, `test_origin_and_numeric_rule_validation`, `test_audit_failure_rolls_back_initial_reference`, `test_audit_failure_rolls_back_metadata_version`, `test_audit_failure_rolls_back_rule_version`, `test_concurrent_metadata_version_allocation`.

## frontend/tests/academic-cycle-dashboard.test.mjs
Lines: 69. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/account-creation.test.mjs
Lines: 50. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/admin-theme.test.mjs
Lines: 28. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`.

## frontend/tests/archive-import.test.mjs
Lines: 13. 
Imports: `node:assert/strict`, `node:fs`.

## frontend/tests/archive-search.test.mjs
Lines: 16. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`.

## frontend/tests/auth-persistence.test.mjs
Lines: 45. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `API` | 9 | Implementation entry; inspect this symbol for details |

## frontend/tests/collaboration-channel.test.mjs
Lines: 16. 
Imports: `node:assert/strict`, `node:fs`.

## frontend/tests/coordinator-admin-monitoring.test.mjs
Lines: 36. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/coordinator-workspace.test.mjs
Lines: 18. 
Imports: `node:assert/strict`, `node:fs`.

## frontend/tests/dashboard-navigation.test.mjs
Lines: 49. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/dashboard-presentation.test.mjs
Lines: 34. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/dashboard-theme.test.mjs
Lines: 29. 
Imports: `node:assert/strict`, `node:fs`, `node:test`, `\.\/dashboard-theme\.css`.

## frontend/tests/design-system.test.mjs
Lines: 30. 
Imports: `node:assert/strict`, `node:fs`, `node:test`, `\.\/index\.css`, `\.\/auth\.css`, `\.\/design-system\.css`, `./index.css`, `./design-system.css`.

## frontend/tests/document-requirements.test.mjs
Lines: 50. 
Imports: `node:assert/strict`, `node:fs`.

## frontend/tests/email-validation.test.mjs
Lines: 39. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/encoding.test.mjs
Lines: 32. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`.

## frontend/tests/evaluation-marks.test.mjs
Lines: 36. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/evaluator-portal.test.mjs
Lines: 29. 
Imports: `node:assert/strict`, `node:fs`.

## frontend/tests/group-account-access.test.mjs
Lines: 25. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.
API references found in source (dynamic expressions may be partial): `/api/v1/team-registration`.

## frontend/tests/manual-delete-controls.test.mjs
Lines: 19. 
Imports: `node:test`, `node:assert/strict`, `node:fs`.

## frontend/tests/module3-proposal.test.mjs
Lines: 27. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/password-policy.test.mjs
Lines: 47. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`, `\.\/passwordPolicy`.

## frontend/tests/password-reset.test.mjs
Lines: 52. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`.

## frontend/tests/portal-contrast.test.mjs
Lines: 28. 
Imports: `node:assert/strict`, `node:fs`.

## frontend/tests/project-workflow.test.mjs
Lines: 28. 
Imports: `node:assert/strict`, `node:fs`.

## frontend/tests/registration-mode.test.mjs
Lines: 22. 
Imports: `node:assert/strict`, `node:fs/promises`, `node:test`.

## frontend/tests/retired-modules.test.mjs
Lines: 33. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/role-sidebar.test.mjs
Lines: 44. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/student-entry-flow.test.mjs
Lines: 34. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`.

## frontend/tests/supervisor-capacity.test.mjs
Lines: 33. 
Imports: `node:assert/strict`, `node:fs`, `node:test`.

## frontend/tests/supervisor-portal.test.mjs
Lines: 40. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`.

## frontend/tests/supervisor-request-workflow.test.mjs
Lines: 73. 
Imports: `node:assert/strict`, `node:fs`, `node:path`, `node:url`.

## scripts/bootstrap_first_admin.py
Lines: 69. Interactively create the first FYPHub administrator, once only.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `main` | 27 | Prompt locally for a new first-admin account without exposing credentials. |

## scripts/build_defence_guide.py
Lines: 351. Build a source-backed defence guide. Database inspection is read-only.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `command` | 70 | Implementation entry; inspect this symbol for details |
| `source_index` | 77 | Implementation entry; inspect this symbol for details |
| `snapshot` | 157 | Implementation entry; inspect this symbol for details |
| `cell` | 172 | Implementation entry; inspect this symbol for details |
| `build` | 176 | Implementation entry; inspect this symbol for details |
| `render` | 247 | Implementation entry; inspect this symbol for details |
| `main` | 342 | Implementation entry; inspect this symbol for details |

## scripts/configure_p1_cycle.py
Lines: 107. Configure the approved local Fall 2026 academic-cycle bootstrap.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `main` | 31 | Create the approved local setting, or verify it already matches exactly. |

## scripts/seed_archived_projects.py
Lines: 69. Development-only idempotent archive fixtures; never run at application startup.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `sample_pdf` | 28 | Implementation entry; inspect this symbol for details |
| `main` | 46 | Implementation entry; inspect this symbol for details |

## scripts/seed_proposal_references.py
Lines: 79. Explicit development-only seed for proposal reference search.
| Symbol | Line | Purpose / source docstring |
|---|---|---|
| `sample_pdf` | 35 | Implementation entry; inspect this symbol for details |
| `main` | 58 | Implementation entry; inspect this symbol for details |

## database/init/001_extensions.sql
Lines: 1. 

## docker-compose.yml
Lines: 155. Service topology, initialization jobs, ports, volumes, networks and health checks.

## backend/Dockerfile
Lines: 28. Python runtime image, dependency installation and Uvicorn launch command.

## frontend/Dockerfile
Lines: 23. Frontend build stage and Nginx static runtime image.

## frontend/nginx.conf
Lines: 27. SPA fallback and reverse proxy routes for API and health endpoints.

## frontend/vite.config.ts
Lines: 15. Vite React/Tailwind plugins, development host/port and API proxy.

## frontend/package.json
Lines: 1. Frontend dependency declarations and dev/build/lint commands.

## frontend/package-lock.json
Lines: 3383. Exact resolved npm dependency graph for reproducible installs.

## frontend/tsconfig.json
Lines: 1. TypeScript project-reference configuration.

## frontend/tsconfig.app.json
Lines: 1. Browser TypeScript compiler rules.

## frontend/tsconfig.node.json
Lines: 1. Node/toolchain TypeScript compiler rules.

## frontend/eslint.config.js
Lines: 5. Lint rules and React hooks checks.

## backend/requirements.txt
Lines: 16. Pinned Python runtime dependency versions.

## backend/alembic.ini
Lines: 4. Migration tool configuration; environment builds the effective connection.

## frontend/index.html
Lines: 1. HTML shell containing the React root and module entry script.

## .gitignore
Lines: 36. Excludes environment files, dependencies, caches and runtime uploads from Git.

## .env.example
Lines: 35. Environment-variable template; real private values are intentionally not inspected or exported.

# Appendix E — Migration revision graph

| Revision | Parent(s) | File |
|---|---|---|
| `3a1f53f17b1c` | `9c227dc337bf` | `backend/alembic/versions/3a1f53f17b1c_add_academic_cycles_and_group_policies.py` |
| `9415b228314f` | `a3b4c5d6e7f8` | `backend/alembic/versions/9415b228314f_join_requests_and_creator_proof_binding.py` |
| `9c227dc337bf` | `None` | `backend/alembic/versions/9c227dc337bf_create_users_foundation.py` |
| `a2b3c4d5e6f7` | `f1a2b3c4d5e6` | `backend/alembic/versions/a2b3c4d5e6f7_add_academic_deadline_versions.py` |
| `a3b4c5d6e7f8` | `f2a3b4c5d6e7` | `backend/alembic/versions/a3b4c5d6e7f8_bind_anonymous_join_proof_target.py` |
| `a7b8c9d0e1f2` | `f6a7b8c9d0e1` | `backend/alembic/versions/a7b8c9d0e1f2_add_group_messages.py` |
| `a8467cad28da` | `eb100aa929ab` | `backend/alembic/versions/a8467cad28da_invitation_transactional_outbox.py` |
| `b2c3d4e5f6a7` | `a8467cad28da` | `backend/alembic/versions/b2c3d4e5f6a7_student_matching_proof.py` |
| `b3c4d5e6f7a8` | `a2b3c4d5e6f7` | `backend/alembic/versions/b3c4d5e6f7a8_add_reminder_rules.py` |
| `b8c9d0e1f2a3` | `a7b8c9d0e1f2` | `backend/alembic/versions/b8c9d0e1f2a3_add_team_match_preferences.py` |
| `b8d2e4f6a9c1` | `f7a1c3d9e2b4` | `backend/alembic/versions/b8d2e4f6a9c1_add_admin_audit_events.py` |
| `c3d4e5f6a7b8` | `b2c3d4e5f6a7` | `backend/alembic/versions/c3d4e5f6a7b8_proposal_foundation.py` |
| `c4d5e6f7a8b9` | `b3c4d5e6f7a8` | `backend/alembic/versions/c4d5e6f7a8b9_add_student_roster.py` |
| `c4e7f1a2b9d3` | `b8d2e4f6a9c1` | `backend/alembic/versions/c4e7f1a2b9d3_add_audit_targets.py` |
| `c5d6e7f8a9b0` | `b2c3d4e5f6a7` | `backend/alembic/versions/c5d6e7f8a9b0_add_supervisor_requests.py` |
| `c9d0e1f2a3b4` | `b8c9d0e1f2a3` | `backend/alembic/versions/c9d0e1f2a3b4_add_match_chat.py` |
| `ce964120f177` | `3a1f53f17b1c` | `backend/alembic/versions/ce964120f177_add_teams_and_member_duplicate_.py` |
| `d0e1f2a3b4c5` | `c9d0e1f2a3b4` | `backend/alembic/versions/d0e1f2a3b4c5_match_chat_mutual_reconsent.py` |
| `d5e6f7a8b9c0` | `c4e7f1a2b9d3` | `backend/alembic/versions/d5e6f7a8b9c0_add_template_reference_versions.py` |
| `d6e7f8a9b0c1` | `c5d6e7f8a9b0` | `backend/alembic/versions/d6e7f8a9b0c1_add_supervisor_request_documents.py` |
| `e1f2a3b4c5d6` | `d0e1f2a3b4c5` | `backend/alembic/versions/e1f2a3b4c5d6_individual_verification.py` |
| `e5f6a7b8c9d0` | `c4d5e6f7a8b9` | `backend/alembic/versions/e5f6a7b8c9d0_add_workflow_policy_drafts.py` |
| `e7f8a9b0c1d2` | `d6e7f8a9b0c1` | `backend/alembic/versions/e7f8a9b0c1d2_add_proposal_references_and_request_conversations.py` |
| `e8f9a0b1c2d3` | `d5e6f7a8b9c0` | `backend/alembic/versions/e8f9a0b1c2d3_add_supervisor_capacity_policies.py` |
| `eb100aa929ab` | `9415b228314f` | `backend/alembic/versions/eb100aa929ab_team_invitations.py` |
| `f1a2b3c4d5e6` | `e8f9a0b1c2d3` | `backend/alembic/versions/f1a2b3c4d5e6_add_evaluation_rubric_drafts.py` |
| `f2a3b4c5d6e7` | `e1f2a3b4c5d6` | `backend/alembic/versions/f2a3b4c5d6e7_anonymous_verification.py` |
| `f6a7b8c9d0e1` | `e5f6a7b8c9d0` | `backend/alembic/versions/f6a7b8c9d0e1_add_supervisor_assignments.py` |
| `f7a1c3d9e2b4` | `ce964120f177` | `backend/alembic/versions/f7a1c3d9e2b4_add_auth_sessions.py` |
| `f9a0b1c2d3e4` | `e7f8a9b0c1d2` | `backend/alembic/versions/f9a0b1c2d3e4_add_archived_projects.py` |
| `fa0b1c2d3e4` | `f9a0b1c2d3e4` | `backend/alembic/versions/fa0b1c2d3e4_allow_archived_title_reuse_after_deactivation.py` |
| `fb1c2d3e4f5` | `fb1c2d3e4f5a` | `backend/alembic/versions/fb1c2d3e4f5_add_historical_archive_fields.py` |
| `fb1c2d3e4f5a` | `fa0b1c2d3e4` | `backend/alembic/versions/fb1c2d3e4f5a_add_module03_proposal_compliance.py` |
| `fc2d3e4f5a6b` | `fa0b1c2d3e4` | `backend/alembic/versions/fc2d3e4f5a6b_add_supervisor_request_submission_notes.py` |
| `fc6b7c8d9e0f` | `r678a003` | `backend/alembic/versions/fc6b7c8d9e0f_add_private_collaboration_channels.py` |
| `fd3e4f5a6b7c` | `fc2d3e4f5a6b` | `backend/alembic/versions/fd3e4f5a6b7c_add_fyp_registry_metadata.py` |
| `fe4f5a6b7c8d` | `fd3e4f5a6b7c` | `backend/alembic/versions/fe4f5a6b7c8d_add_password_reset_tokens.py` |
| `ff5a6b7c8d9e` | `fe4f5a6b7c8d` | `backend/alembic/versions/ff5a6b7c8d9e_add_progress_scheduling_evaluation.py` |
| `fg6b7c8d9e0f` | `ff5a6b7c8d9e` | `backend/alembic/versions/fg6b7c8d9e0f_add_module03_template_versions.py` |
| `fh7c8d9e0f1a` | `fg6b7c8d9e0f` | `backend/alembic/versions/fh7c8d9e0f1a_add_module03_activation_mode.py` |
| `fi8d9e0f1a2b` | `c3d4e5f6a7b8` | `backend/alembic/versions/fi8d9e0f1a2b_continue_proposal_chain.py` |
| `fj9e0f1a2b3` | `fi8d9e0f1a2b` | `backend/alembic/versions/fj9e0f1a2b3_add_proposal_type.py` |
| `fk0f1a2b3c4` | `fj9e0f1a2b3` | `backend/alembic/versions/fk0f1a2b3c4_add_proposal_metadata_fields.py` |
| `fl1a2b3c4d5` | `fk0f1a2b3c4` | `backend/alembic/versions/fl1a2b3c4d5_add_agent_supervision_runs.py` |
| `gm2b3c4d5e6f` | `fl1a2b3c4d5` | `backend/alembic/versions/gm2b3c4d5e6f_add_dashboard_requirements.py` |
| `hn3c4d5e6f7a` | `gm2b3c4d5e6f` | `backend/alembic/versions/hn3c4d5e6f7a_add_document_upload_requirements.py` |
| `jk4d5e6f7a8b` | `hn3c4d5e6f7a` | `backend/alembic/versions/jk4d5e6f7a8b_document_storage_reference.py` |
| `kl5e6f7a8b9c` | `jk4d5e6f7a8b` | `backend/alembic/versions/kl5e6f7a8b9c_add_role_based_fyp_evaluations.py` |
| `lm6f7a8b9c0d` | `kl5e6f7a8b9c` | `backend/alembic/versions/lm6f7a8b9c0d_remove_evaluation_marks_module.py` |
| `m123a001` | `('c3d4e5f6a7b8', 'fh7c8d9e0f1a')` | `backend/alembic/versions/m123a001_modules_1_3_lifecycle.py` |
| `mn7c8d9e0f1a` | `lm6f7a8b9c0d` | `backend/alembic/versions/mn7c8d9e0f1a_restore_role_based_evaluations.py` |
| `mo8r9e0f1a2b` | `('mn7c8d9e0f1a', 'ff5a6b7c8d9e')` | `backend/alembic/versions/mo8r9e0f1a2b_add_proposal_ai_review_runs.py` |
| `n456a001` | `m123a001` | `backend/alembic/versions/n456a001_add_academic_cycle_year_session.py` |
| `oa1b2c3d4e5f` | `mo8r9e0f1a2b` | `backend/alembic/versions/oa1b2c3d4e5f_repair_module1_evaluation_schema.py` |
| `ob1c2d3e4f5a` | `oa1b2c3d4e5f` | `backend/alembic/versions/ob1c2d3e4f5a_repair_module1_identity_columns.py` |
| `oc1d2e3f4a5b` | `ob1c2d3e4f5a` | `backend/alembic/versions/oc1d2e3f4a5b_add_template_activation.py` |
| `p567a001` | `n456a001` | `backend/alembic/versions/p567a001_supervisor_capacity_year_session.py` |
| `pa1b2c3d4e5f` | `('ob1c2d3e4f5a', 'oc1d2e3f4a5b')` | `backend/alembic/versions/pa1b2c3d4e5f_add_module03_compliance_workspace.py` |
| `qa1b2c3d4e5f` | `pa1b2c3d4e5f` | `backend/alembic/versions/qa1b2c3d4e5f_complete_module02_collaboration.py` |
| `r678a001` | `p567a001` | `backend/alembic/versions/r678a001_remove_registry_roster_identity_modules.py` |
| `r678a002` | `r678a001` | `backend/alembic/versions/r678a002_remove_invitation_outbox.py` |
| `r678a003` | `r678a002` | `backend/alembic/versions/r678a003_annual_supervisor_capacity.py` |
| `rd7e8f9a0b1c` | `fc6b7c8d9e0f` | `backend/alembic/versions/rd7e8f9a0b1c_repair_archive_import_columns.py` |
| `re8f9a0b1c2d` | `rd7e8f9a0b1c` | `backend/alembic/versions/re8f9a0b1c2d_archive_import_batches.py` |
| `rf9a0b1c2d3e` | `re8f9a0b1c2d` | `backend/alembic/versions/rf9a0b1c2d3e_document_requirement_lifecycle.py` |

# Appendix F — Reproducibility and evidence files
The machine-readable companion `technical-inventory.json` contains the full inspected schema, ORM metadata, endpoint ownership, source symbols, frontend imports and test names. `scripts/build_defence_guide.py` rebuilds it using read-only database catalog queries. `FYPHub_Defence_Guide_Source.md` is the authored explanatory part. Generated documents are snapshots and should be regenerated after code/schema changes.
