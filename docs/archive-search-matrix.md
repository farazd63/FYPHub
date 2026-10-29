# FYP Archive and Knowledge Search Matrix

This checkpoint implements a separate logical archive. It does not duplicate the PostgreSQL database or repurpose supervisor-request documents.

| Requirement | Implementation | Status / limitation |
| --- | --- | --- |
| Archived project metadata | `ArchivedProject` with normalized title, summary, keywords, cycle/year, scope, stage, implemented scope, gaps, future work, source, active/archive timestamps | Implemented; duplicate active title/year rejected |
| Immutable document library | `ArchivedProjectDocument` with document type, storage key, hash, PDF bytes, version, uploader, active flag | Implemented; new uploads deactivate only the prior active version |
| Admin management | Create/edit metadata, PDF upload/versioning, active document history, audit events | Implemented; browser verification pending |
| Student search/detail | Authorized deterministic ranked search and read-only detail/document access | Implemented; no private student/audit data returned |
| Semantic ranking | pgvector availability is documented, but no safe project embedding source is configured | Explicitly reported as unavailable; deterministic ranking never fails |
| Sample data | `scripts/seed_archived_projects.py`, 8 labelled `SAMPLE_DATA` projects with separate short/long/final PDFs | Opt-in and idempotent; not run against the project database |

## Source map

- Model/migration: `backend/app/models/archived_project.py`, `backend/alembic/versions/f9a0b1c2d3e4_add_archived_projects.py`, and title-reuse correction `fa0b1c2d3e4`.
- API and authorization: `backend/app/archived_projects.py`; Student, Supervisor, Coordinator, and Admin can read active records; only Admin mutates; Panel is denied by default.
- Student UI: `frontend/src/portals/student/modules/knowledge-search/KnowledgeSearch.tsx`, `ArchivedProjectDetail.tsx`, with implementation shared from the existing Student module files and `archive-knowledge.css`.
- Admin UI: `frontend/src/portals/admin/modules/archive/ArchiveManagement.tsx`, delegating to the shared implementation in `ArchiveManagementV2.tsx`.
- Tests: `backend/tests/test_archived_projects.py` and the frontend production build/lint.
