# Known limitations

- PyMuPDF and python-docx provide best-effort layout metadata; unavailable parser capabilities are represented as warnings/unknown values.
- Coordinator cycle/department scope cannot be narrowed further until the existing coordinator-scope model is available to this module.
- A dedicated scoped original-document download route is still pending; report metadata does not expose document bytes.
- The Ollama Check 3 is advisory and may be `UNAVAILABLE`; deterministic checks do not depend on it.
- Registry completion stages remain `Not Available` until a persisted progress model exists; the registry does not invent percentages or academic completion states.
