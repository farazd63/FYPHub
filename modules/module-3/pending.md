<<<<<<< HEAD
# Known limitations

- PyMuPDF and python-docx provide best-effort layout metadata; unavailable parser capabilities are represented as warnings/unknown values.
- Coordinator cycle/department scope cannot be narrowed further until the existing coordinator-scope model is available to this module.
- A dedicated scoped original-document download route is still pending; report metadata does not expose document bytes.
- The Ollama Check 3 is advisory and may be `UNAVAILABLE`; deterministic checks do not depend on it.
- Registry completion stages remain `Not Available` until a persisted progress model exists; the registry does not invent percentages or academic completion states.
=======
# Remaining Long Proposal Module 3 requirements

- Official short/long proposal creation and upload; draft, submit, resubmit and lifecycle statuses.
- Proposal version history and AI-generated change summaries between versions.
- University-format checks for font, font size, margins, alignment, line spacing, heading styles, page numbering, tables and figures.
- Structural checks for required sections, order, headings, references, appendices and captions.
- Academic consistency analysis across problem, objectives, methodology, proposed solution, scope and expected outcomes.
- Authorized Supervisor, Coordinator and Panel views of the same analysis and an official proposal version with a Proposal Compliance & Readiness Report.

Existing template/rule references are internal foundations, not approved university templates or an implemented checker. The proposal does not specify detailed lifecycle, upload or permission rules; existing [decisions](../../docs/decisions.md) leave correction/resubmission rules and Coordinator scope unresolved. Agentic AI remains deferred by the user; no substitute or model policy is presumed.

A non-operational proposal/version schema exists in the working tree; operational creation, version history and the requirements above remain pending. Do not infer that its migration has been applied.
>>>>>>> c3b9ee80fadf2c13df694c08620da65daf55cb12
