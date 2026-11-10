# Archive and Knowledge Search coverage

This source map records the archive and knowledge-search requirements from the current Long Proposal checkpoint: a separate logical archive, immutable document versions, Admin curation, authorized read-only search/detail access, deterministic ranking, and optional advisory semantic ranking. These are tracked separately from the Module 2 team-collaboration scope.

| Requirement | Status | Evidence / limitation |
| --- | --- | --- |
| Separate archived-project metadata model | Implemented | `backend/app/models/archived_project.py`, migrations `f9a0b1c2d3e4` and `fa0b1c2d3e4` |
| Immutable PDF document versions and supported document types | Implemented | `backend/app/archived_projects.py`; new uploads supersede only the active version and preserve history |
| Admin create/edit/upload/activate/deactivate and audit | Implemented | Admin API and `ArchiveManagementV2`; append-only audit events are visible through the existing audit endpoint |
| Student ranked search and read-only detail/document access | Implemented | `KnowledgeSearch.tsx`, `ArchivedProjectDetail.tsx`; active PDFs use an authorized endpoint |
| Deterministic ranking | Implemented | Exact title, normalized title, keyword, summary, and scope matches are ranked with an explicit reason |
| Semantic/embedding ranking | Not available | No approved embedding source is configured; responses label semantic search unavailable and never fabricate scores |
| Development sample data | Implemented, not run | `scripts/seed_archived_projects.py` is opt-in, idempotent, and inserts eight `SAMPLE_DATA` projects |

Browser verification remains pending in this environment. The proposal-specified Student/Admin archive paths are present as stable module boundaries and delegate to the shared implementations.
