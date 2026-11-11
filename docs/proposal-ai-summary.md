# Proposal AI summaries

The original proposal PDF, its extracted fields, and its human-written purpose remain unchanged. The separate **AI-generated summary** panel runs local inference through the configured Ollama proposal model. It is advisory and does not confirm, submit, accept, reject, or grade a request.

## Implementation

The compliance narrative prompt and response schema are in `backend/app/modules/module_03_proposal/ai_report.py`. The current detailed format includes proposal fields, a requested 250–400 word narrative, exact recorded score/status, all recorded findings, passed checks and priority actions. The LLM generates narrative fields; the backend assembles the findings and actions from saved source entries so no finding is omitted or rewritten by the model. Repeated recorded entries remain separate. Missing metadata uses “Not detected in the provided proposal.” The frontend renders this structure and can download the exact `{ "summary": ... }` JSON document. Earlier short summaries are invalidated by the report format version.

- `frontend/src/ProposalAiSummary.tsx`: shared student/supervisor panel, generation status and retry.
- Student proposal preview and supervisor request details automatically request a summary. Saved student request cards offer generation on demand.
- `POST /api/v1/supervisor-requests/{request_id}/ai-summary`: authorized generation and cached retrieval.
- `backend/app/supervisor_requests.py`: source-only prompt, validated summary schema, authorization, document-version check and audit events.
- `backend/app/ai_provider.py`: existing provider client, structured JSON, retries and rate limiting.
- PostgreSQL `supervisor_requests.ai_summary` (JSONB): summary, status, model, provider, generated timestamp, original document ID and advisory flag.
- Migration `rh1c2d3e4f5a`: adds the JSONB column.

Successful results are cached for the current document. Replacing a PDF clears its previous AI summary. If the PDF changes while inference is running, the result is rejected instead of attached to the wrong version. The database connection is released while waiting for inference.

Compliance summaries now send the complete extracted proposal text, all extracted fields, and the entire compliance report (excluding an existing AI summary). No character slices, evidence shortening, or finding-count caps are applied. Supervisor-request summaries likewise send the complete extracted text. Older excerpt-based cached summaries are regenerated. Summary requests expand the context reservation using a conservative UTF-8 byte upper bound plus template/output headroom; inputs that cannot be guaranteed to fit Llama 3.1's 128K context are rejected explicitly, never silently shortened. Larger contexts require more inference memory and time.

## Local requirements

The configured model must exist in the Ollama model volume and the VM must have sufficient memory. This environment uses `llama3.1:8b`; Docker memory was increased from 2 GB to 10 GB for local inference. `AI_TIMEOUT_SECONDS` was increased to 120 in the local environment. Nginx allows 300 seconds for API responses, accommodating the configured retry.

Unavailable, rate-limited, or invalid model responses produce an explicit unavailable state with retry. Extracted proposal text is never presented as an AI-generated substitute.

## Validation

The focused regression covers generation and caching, unchanged original content, unauthorized supervisor access, and provider failure without changing submitted status. PDF extraction and existing Ollama provider tests cover heading variants, structured responses and timeout behavior. Frontend production compilation is required as well.
