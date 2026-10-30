# Module 03 — AI-Native Proposal Compliance

Module 03 adds a versioned, document-backed proposal compliance workflow. Admins upload the approved SHORT/LONG PDF or DOCX baseline; the parser extracts only observable rules and records unknowns as warnings. Students upload proposal versions and receive deterministic formatting/structure checks plus an optional local Ollama chain-of-logic advisory check.

All API routes are under `/api/v1/module-03`. All new tables use the `m03_` prefix and external user/team/proposal/document identifiers are plain strings without SQL foreign keys. The workflow never makes an academic approval decision and never sends documents to a cloud provider.

Configuration: `OLLAMA_BASE_URL` defaults to `http://localhost:11434`, `OLLAMA_MODEL` selects the local model, `OLLAMA_TIMEOUT_SECONDS` bounds requests, and `FYPHUB_M03_MAX_BYTES` bounds uploads. If Ollama is unavailable or returns malformed JSON, Check 3 is explicitly `UNAVAILABLE`; uploaded documents and deterministic results remain available.

## Reference-template baseline

The Admin-uploaded official template is a reference baseline, not a student proposal. PDF/DOCX ingestion records only observable structure (geometry, fonts, headings, spacing, and related layout facts). Proposal-only fields such as purpose, problem statement, objectives, methodology, and expected outcomes are recorded as `Not specified in reference template` when absent; they do not create false extraction failures. Student proposal extraction continues to use its own required-field rules.

Coordinator and Admin registry screens link Module 03 compliance metadata only when a persisted report exists. They never fabricate a completion percentage or compliance result.
