# Workflow

1. Admin uploads a SHORT or LONG PDF/DOCX. The file is checksummed, parsed, extracted dynamically, and saved as an inactive immutable version with warnings/confidence.
2. Admin reviews the extraction preview and activates one version per proposal type. Previous versions remain available.
3. A Student uploads a matching proposal type only when an active baseline exists. The proposal is stored with an immutable versioned AST and parser warnings.
4. The Student starts an audit. Tier 1 and Tier 2 run deterministically. Tier 3 sends normalized text only to the configured local Ollama runtime using JSON mode.
5. The report stores all three tier results, severity counts, remediation, runtime metadata, and an advisory disclaimer. Reports are versioned and never auto-approve/reject a proposal.
6. Students see their own proposals, assigned Supervisors see accepted assigned proposals, Coordinators see authorized role-scoped reports, Admins see all, and Panel users are denied by default.

7. Coordinator and Admin registry pages read the same persisted request/document/history data through role-specific endpoints. Supervisor registry reads are limited to active assignments and student reads to own/team ownership. Admin metadata corrections require a reason and are stored with a before/after audit event; original proposal bytes and immutable extraction/decision history are never edited.
8. Reference-template extraction records observable structure. Missing purpose/problem/objectives/methodology/outcomes in the official template are represented as `Not specified in reference template`, while student proposal required-field validation remains independent.
