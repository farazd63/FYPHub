<<<<<<< HEAD
# Proposal coverage

| Requirement | Implementation | State |
|---|---|---|
| Dynamic SHORT/LONG baseline ingestion | `doc_parser.py`, `admin_template_extractor.py`, `m03_reference_templates`, `m03_template_rule_sets` | Implemented |
| Immutable versions and activation | Template version rows and activation/deactivation routes | Implemented |
| Student PDF/DOCX upload and versioned AST | `m03_proposal_documents`, upload route | Implemented |
| Tier 1 visual/formating audit | Deterministic observable typography/geometry comparisons | Implemented |
| Tier 2 structural/content audit | Deterministic section, word-count, citation/reference checks | Implemented |
| Tier 3 chain-of-logic audit | Local Ollama JSON advisory adapter | Implemented with unavailable fallback |
| Supervisor/coordinator access | Existing supervisor assignment authorization and coordinator role guard | Partial: cycle scope is not represented by existing coordinator records |
| Panel access | Backend role guard denies Panel | Implemented |
| Original document download | Stored as immutable content; a dedicated scoped download endpoint remains | Pending |
| Reference-template missing proposal fields | Explicit `Not specified in reference template` values; no false required-field failure | Implemented |
| Coordinator/Admin registry linkage | Authorized registry detail links persisted compliance metadata when available | Implemented; report availability remains data-dependent |
=======
# Long Proposal Module 3 coverage

Source: `D:/FYP Project/long proposal.pdf`, section 9.3, PDF page 10, read directly on 23 October 2026. The later recovery audit identifies an uncommitted, non-operational schema foundation; statuses below distinguish it from operational features. ?Missing? means no corresponding implementation was found; no Module 3 tests were run in this documentation pass.

| Proposal requirement | Status | Existing evidence and gap |
| --- | --- | --- |
| Official short/long proposal creation and upload | Partial | A non-operational [proposal model](../../backend/app/models/proposal.py), [migration](../../backend/alembic/versions/c3d4e5f6a7b8_proposal_foundation.py), and [schema tests](../../backend/tests/test_proposal_foundation.py) exist; no creation/upload route or proposal UI was found. [Template reference model](../../backend/app/models/template_reference.py), [admin API](../../backend/app/main.py), [admin UI](../../frontend/src/AdminTemplateReferences.tsx) and [template tests](../../backend/tests/test_template_references.py) manage internal reference metadata/rules, not submitted proposals. |
| Draft, submit, resubmit and lifecycle-status management | Missing | No proposal lifecycle implementation or tests found. The existing [workflow record](../../docs/p1-workflows.md) describes a proposed pipeline, not implemented behavior. |
| Proposal version history | Partial | A non-operational proposal version table and numbered-version constraints exist in the model and migration above; there is no operational version history. Template-reference and academic-rule versions in [template_reference.py](../../backend/app/models/template_reference.py) and [test_template_references.py](../../backend/tests/test_template_references.py) are not proposal versions. |
| AI-generated change summaries between proposal versions | Missing | No proposal-version summary service, UI or tests found. Requires proposal versions; the user's existing deferral of agentic AI remains in effect. |
| University-format checking: font, font size, margins, alignment, line spacing, heading styles, page numbering, tables and figures | Missing | [Template schemas](../../backend/app/schemas/templates.py) describe internal rule inputs; no proposal document checker or tests found. Approved university templates and applicable rules are not established by internal draft references. |
| Structural validation: required sections, section order, headings, references, appendices and captions | Missing | No proposal structural-validation implementation or tests found. Internal [template references](../../backend/app/models/template_reference.py) do not validate a submitted document. |
| Academic consistency analysis: problem statement, objectives, methodology, proposed solution, scope and expected outcomes | Missing | No proposal analysis implementation or tests found. [Group chatbot](../../backend/app/group_ai.py) is a separate collaboration feature, not a proposal consistency checker. |
| Authorized Supervisor, Coordinator and Panel views of the same analysis, according to role permissions | Missing | Existing [authentication](../../backend/app/auth.py) and [supervisor assignments](../../backend/app/supervisor_assignments.py) are shared foundations; no proposal-analysis view or proposal-specific access enforcement was found. [Decisions](../../docs/decisions.md) record review boundaries and unresolved scopes. |
| Official proposal version and Proposal Compliance & Readiness Report as primary output | Missing | No official proposal-version record or compliance/readiness report was found. |
>>>>>>> c3b9ee80fadf2c13df694c08620da65daf55cb12
