# Workflow

1. Admin uploads a SHORT or LONG PDF/DOCX. The file is checksummed, parsed, extracted dynamically, and saved as an inactive immutable version with warnings/confidence.
2. Admin reviews the extraction preview and activates one version per proposal type. Previous versions remain available.
3. A Student uploads a matching proposal type only when an active baseline exists. The proposal is stored with an immutable versioned AST and parser warnings.
4. The Student starts an audit. Tier 1 and Tier 2 run deterministically. Tier 3 sends normalized text only to the configured local Ollama runtime using JSON mode.
5. The report stores all three tier results, severity counts, remediation, runtime metadata, and an advisory disclaimer. Reports are versioned and never auto-approve/reject a proposal.
6. Students see their own proposals, assigned Supervisors see accepted assigned proposals, Coordinators see authorized role-scoped reports, Admins see all, and Panel users are denied by default.
