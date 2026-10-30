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
