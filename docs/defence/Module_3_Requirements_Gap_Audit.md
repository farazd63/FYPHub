# Module 3 proposal requirements: implementation and gap audit

Inspected 11 November 2026. This is a code audit with focused verification, not a claim that every portal workflow has passed end-to-end testing. No application changes were made as part of this audit.

## Overall conclusion

The proposal workflow and rule-based compliance foundations exist. The complete requested AI-assisted analysis is not implemented. In particular, change summaries do not call an AI model, academic consistency uses word overlap, and formatting extraction is approximate rather than a complete document-layout validator.

## Requirement coverage

| Requirement | Finding | Implementation | Remaining work |
|---|---|---|---|
| Short/long upload | Present | `frontend/src/modules/module-3/ProposalComplianceWorkspace.tsx`; `backend/app/modules/module_03_proposal/router.py: submit_proposal`; SHORT/LONG database constraint | Separate from the supervisor-selection upload flow. An active template for the selected type is required, even when saving a draft. |
| Draft/submit/resubmit | Present with limitations | Multipart `action=draft/submit`, proposal_key, numbered versions; frontend Save Draft, submit and resubmit controls | Editing a draft creates another version. Version numbers use previous+1 without a demonstrated concurrent-upload retry. |
| Lifecycle status | Partial | Submission and review endpoints; DRAFT, SUBMITTED, RESUBMITTED, CHANGES_REQUESTED, APPROVED, REJECTED, WITHDRAWN workflows | Multiple proposal stores are not a single unified lifecycle. Review transition validation and report rerun permissions need a separate workflow/security review. |
| Version history | Present | proposal_key/version unique constraint; `_version_history`; frontend history | Each historical version is compared with the selected current version, rather than necessarily adjacent versions. Existing report snapshots may not reflect later review changes. |
| AI-generated change summaries | Missing as genuine AI | `compliance_engine.py: build_change_summary` | Compares selected fields and emits canned text such as Updated Objectives. No LLM call. Labels AI_ASSISTED_DETERMINISTIC and local-change-analyzer must not be presented as proof of model-generated output. Title/topic/formatting changes are not part of its comparison list. |
| Fonts/font size/margins/spacing | Partial | `pdf_extraction.py: _pdf_formatting`, `_docx_formatting`; template extractor; compliance engine | Predominant fonts and median sizes aggregate away local violations. PDF margins are inferred from content bounding boxes; spacing is inferred from line geometry. DOCX uses first-section margins and explicitly set run values, without full inherited-style resolution. |
| Alignment/heading styles | Partial | DOCX explicit paragraph alignment and heading style aggregation | PDF does not extract equivalent alignment/heading-style values. No comprehensive paragraph-by-paragraph style verification. Missing metadata must remain UNVERIFIABLE. |
| Page numbering | Partial | PDF text regex; DOCX paragraph-text heuristic | DOCX headers/footers and PAGE fields are not comprehensively parsed. Plain numeric PDF footers can be missed. No sequence/location verification. |
| Tables/figures | Partial | PDF table/image counts; DOCX table/inline-shape counts | Counts do not validate numbering, placement, captions, cross-references, or table formatting. Matching a template's example table/image count is not a complete university-format policy. |
| Required sections/headings/order | Partial with verified defect | `_detected_headings`, fuzzy heading matching and section sequence checks | Order matching is partly exact while presence uses fuzzy matching. A misplaced else block emits repeated sequence PASS results inside the academic-consistency loop, even when sequence FAIL already exists. |
| References/appendices/captions | Basic checks present | Heading/count detection, optional required_references/required_appendices/required_captions | No reference-style validation, citation-to-bibliography matching, caption numbering/linking, or appendix content validation. |
| Academic consistency | Basic heuristic only, with verified defect | `_consistency_item`, five section pairs | Token overlap cannot establish academic feasibility, entailment, contradictions, or whether methods achieve objectives. Problem/Objectives reads problem_statement although extraction stores purpose. |

## Verified defects

### Problem/objectives field mismatch

The extractor stores a Problem Statement under `purpose`. The first consistency pair requests `problem_statement`. A test with identical purpose/objectives text produced UNVERIFIABLE: Problem Statement or Objectives was not detected. The field is present but read using the wrong key.

### Contradictory section-order results

A synthetic document with Methodology before Introduction, against the required Introduction/Methodology order, produced sequence statuses:

```text
FAIL, PASS, PASS, PASS, PASS, PASS
```

The PASS-generation else belongs to the academic-consistency item condition rather than the section-order condition. Failed academic-consistency checks also append an extra violation labelled Section Sequence. This contaminates categories, issue counts and overall scores.

### Change-summary provenance

`build_change_summary` imports no model client and makes no AI request. It compares string representations of extracted values and returns a list of changed section names. It does not explain what changed academically. Its output source/model labels are descriptive strings, not an actual trained model or inference result.

## Database and file map

| Data | Location |
|---|---|
| Proposal submissions and version metadata | PostgreSQL `fyphub_p1.public.proposal_compliance_submissions`; ORM `backend/app/models/proposal_compliance.py` |
| Extracted text/fields | Same submission table, TEXT and JSONB columns |
| Compliance reports/history summaries in report snapshots | `proposal_compliance_reports.report` JSONB |
| Official template versions | `template_references`, `template_reference_versions` |
| Approved rule snapshots | `academic_rule_versions` |
| Original compliance-uploaded files | Configured document-storage root, `module-3/submissions/<proposal_key>/v<version>-<filename>`; persistent document volume |
| Supervisor-selection proposals | Separate `supervisor_requests`, `supervisor_request_documents`, request history and note versions |
| Other legacy/foundation proposal records | `proposals`, `proposal_versions`, plus historical m03 tables; not interchangeable with the active compliance store |

## Main source files

- `frontend/src/modules/module-3/ProposalComplianceWorkspace.tsx`: student submission, history and report UI.
- `frontend/src/modules/module-3/AdminProposalTemplates.tsx`: university baseline/template UI.
- `backend/app/modules/module_03_proposal/router.py`: templates, uploads, version history, lifecycle actions, reports and downloads.
- `backend/app/modules/module_03_proposal/compliance_engine.py`: deterministic comparison, structural checks, consistency heuristic and change summaries.
- `backend/app/modules/module_03_proposal/template_extractor.py`: baseline measurements and heading extraction.
- `backend/app/pdf_extraction.py`: PDF/DOCX/TXT content and formatting extraction.
- `backend/app/models/proposal_compliance.py`: active compliance database models.
- `backend/app/ai_provider.py`: separate configurable AI infrastructure; not currently called by compliance change-summary or consistency functions.

The student portal mounts this workspace in Proposal Compliance Check. Supervisor compliance UI was intentionally removed in earlier requested changes; supervisor requests are a separate workflow. Do not interpret its absence from that portal as absence of backend compliance code.

## Verification performed

Executed the five existing test functions in `backend/tests/test_module3_compliance_engine.py`; all passed. Separately reproduced the field-name mismatch and contradictory sequence results above. Existing tests are insufficient to catch these defects because they primarily assert report presence/shape rather than academic correctness or contradictory results.

No genuine model-inference quality benchmark, full browser lifecycle test, or comprehensive PDF/DOCX format corpus evaluation was performed for this audit.

## Recommended completion order

1. Correct field mapping and sequence/violation categorization; add regression tests before altering scores.
2. Mark deterministic summaries and lexical consistency honestly in API/UI.
3. Integrate real advisory AI summaries for adjacent versions with schema validation, provenance, clear unavailability and deterministic fallback. Verify the configured model is installed.
4. Add semantic academic-consistency analysis with section evidence and human-review boundaries, keeping it separate from deterministic formatting scores.
5. Improve per-paragraph/per-page formatting, DOCX inherited styles and headers/footers, and explicit structural policies.
6. Consolidate lifecycle expectations across supervisor-selection and compliance proposals, then test draft, submit, changes requested, resubmit, approve/reject and history visibility by role.

For defence: describe the current system as a versioned proposal workflow with deterministic compliance and preliminary lexical consistency checks. Do not claim complete AI-generated version summaries or comprehensive semantic academic validation yet.
