# Remaining Long Proposal requirements

- **Verified membership and leader/member rules:** initial registration validates roster eligibility but does not establish each initial member's individual consent. The proposal does not define the remaining membership or leader lifecycle rules; obtain those decisions before implementing them.
- **AI teammate compatibility matching:** deterministic compatibility remains the source of truth and the new `/api/v1/team-matching/ai-suggestions` endpoint adds advisory AI ranking with an explicit deterministic fallback. Live Ollama availability still needs environment verification.
- **Group AI chatbot:** local integration and mocked tests exist; a configured runtime and model are needed to verify live operation.

Verification still needed: functional browser checks beyond the user-reported student discovery visual check, and actual SMTP delivery for roster OTP and invitations. These are verification gaps, not additional proposal features. SMTP server acceptance does not prove final delivery.

Current checkpoint: the user reports that student discovery looked good in desktop and mobile views; functional browser checks remain pending where not explicitly confirmed. SMTP host/sender and local AI URL/model are not configured in the current environment; live email and AI remain unverified. See `verification.md` for manual discovery steps.

Discovery follow-up: the user reports that the desktop and mobile views looked good. The report does not specify outcomes for all eight answers, live roster OTP delivery, filtering, result privacy, or expired/replayed or wrong-cycle rejection. Focused backend tests passed with mocked delivery; live SMTP remains unverified. See the manual steps in `verification.md`.

Chatbot and email availability check: local AI URL/model and SMTP host/sender are not configured. Unavailable responses and mocked failure behavior passed; live AI operation and delivery to a controlled mailbox remain unverified.
