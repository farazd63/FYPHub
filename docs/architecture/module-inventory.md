# FYPHub module inventory

This inventory describes the current repository after the retired collaboration flows were removed. It records the active implementation boundaries and keeps build-tool locations centralized.

## Module 01 — governance and academic configuration

- Frontend entry points: `frontend/src/AdminPortal.tsx`, `AdminUsersRoles.tsx`, `AdminCycleManager.tsx`, `AdminSupervisorCapacity.tsx`, `AdminDeadlines.tsx`, `AdminReminderRules.tsx`, and `AdminDocumentArchive.tsx`.
- Backend routes/services: `backend/app/main.py`, `academic_cycle_overview.py`, `coordinator_operations.py`, `dashboard_requirements.py`, `document_requirements.py`, `registration_policy.py`.
- Models: `backend/app/models/academic.py`, `academic_deadline.py`, `dashboard_requirement.py`, `document_requirement.py`, `reminder_rule.py`, `audit_event.py`.
- Schemas: `backend/app/schemas/academic.py`, `academic_deadlines.py`, `dashboard_requirements.py`, `document_requirements.py`, `reminder_rules.py`, `admin_users.py`, `supervisor_capacity.py`.
- Tests: `backend/tests/test_admin_users.py`, `test_cycle_concurrency.py`, `test_academic_cycle_overview.py`, `test_academic_deadlines.py`, `test_reminder_rules.py`, `test_document_requirements_*.py`, `test_supervisor_capacity.py`.
- Roles: ADMIN and COORDINATOR for configuration; role-specific read scopes are enforced by existing dependencies.

## Module 02 — student teams and collaboration

- Frontend entry points: `frontend/src/portals/student/modules/StudentCollaborationChannel.tsx`, `GroupAIChat.tsx`, `StudentProgressDashboard.tsx`, and the student portal/sidebar files.
- Backend routes/services: `backend/app/collaboration_channels.py`, `group_ai.py`, `project_workflow.py`, `team_lifecycle.py`, and `supervisor_assignments.py`.
- Models: `backend/app/models/team.py`, `module2_collaboration.py` (the active private-channel and notification records), `student_ai.py`, `project_workflow.py`, and `supervisor_assignment.py`.
- Tests: `backend/tests/test_collaboration_channels.py`, `test_collaboration_channel_access.py`, `test_project_workflow.py`, `test_team_registration.py`, and `test_team_constraints.py`.
- API prefixes: `/api/v1/student/collaboration/channels`, `/api/v1/supervisor/collaboration/channels`, `/api/v1/group-ai`, and `/api/v1/project-progress`.

## Module 03 — proposal, review, workflow, and archive

- Frontend entry points: `frontend/src/modules/module-3/`, `frontend/src/portals/student/modules/supervisor-selection/`, `frontend/src/portals/supervisor/modules/supervisor-requests/`, `frontend/src/portals/admin/modules/supervisor-requests/`, `frontend/src/portals/admin/modules/archive/`.
- Backend routes/services: `backend/app/modules/module_03_proposal/`, `project_workflow.py`, `proposal_reference.py`, `supervisor_requests.py`, `supervisor_request_conversations.py`, `archived_projects.py`, `evaluations.py`.
- Models: `proposal.py`, `proposal_compliance.py`, `proposal_reference.py`, `proposal_ai_review.py`, `project_workflow.py`, `supervisor_request.py`, `supervisor_request_conversation.py`, `archived_project.py`, `evaluation.py`, `evaluation_rubric.py`, `template_reference.py`.
- Tests: `test_module3_compliance_engine.py`, `test_project_workflow.py`, `test_proposal_reference_and_conversation.py`, `test_supervisor_requests.py`, `test_archived_projects.py`, `test_evaluations.py`, `test_evaluation_rubrics.py`, and `test_template_references.py`.

## Shared/core code

- Frontend authentication and application shell: `frontend/src/App.tsx`, `auth.css`, `PasswordField.tsx`, `emailValidation.ts`, `passwordPolicy.ts`, `inputValidation.ts`, `portals/shared/`.
- Backend core: `backend/app/auth.py`, `config.py`, `database.py`, `security.py`, `main.py` application registration, `models/__init__.py`, `schemas/__init__.py`.
- Infrastructure: `docker-compose.yml`, `frontend/package.json`, Vite/TypeScript configuration, `backend/alembic/`, and database initialization remain centralized by tool requirements.

## Database and migration inventory

- Initialization SQL: `database/init/001_extensions.sql`.
- Runtime schema: SQLAlchemy models under `backend/app/models/`.
- Migrations: all revisions remain in `backend/alembic/versions/`; no migration files were moved.
- The live repository is at one Alembic head after the retired collaboration and AI-matching cleanup migrations.

## Tests and documentation

- Backend tests remain under `backend/tests/` because the backend image and unittest discovery depend on that location.
- Frontend tests remain under `frontend/tests/` because they read source paths directly.
- Module documentation is under `docs/modules/`; Module 2's pre-existing documentation was moved from `modules/module-2/` to `docs/modules/module-02-collaboration/` with its internal link updated.
