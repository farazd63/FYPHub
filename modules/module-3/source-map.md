# Source map

<<<<<<< HEAD
- `backend/app/modules/module_03_proposal/services/ast_parser.py`: normalized PDF/DOCX AST.
- `backend/app/modules/module_03_proposal/services/admin_template_extractor.py`: dynamic baseline rule extraction.
- `backend/app/modules/module_03_proposal/services/ai_template_extractor.py`: optional local Ollama structured baseline extraction with deterministic fallback.
- `backend/app/modules/module_03_proposal/services/check_1_visual.py`: deterministic formatting audit.
- `backend/app/modules/module_03_proposal/services/check_2_structural.py`: deterministic structure/citation audit.
- `backend/app/modules/module_03_proposal/services/check_3_semantic_llm.py`: optional local Ollama advisory audit.
- `backend/app/modules/module_03_proposal/router.py`: authorized API routes and transactional persistence.
- `frontend/src/modules/module_03_proposal/`: Admin and Student views using the existing FYPHub visual language.
- `backend/alembic/versions/fb1c2d3e4f5a_add_module03_proposal_compliance.py`: single migration linked to the current head.
- `backend/app/fyp_registry.py`: role-scoped Coordinator/Admin registry and student/supervisor privacy endpoints.
- `backend/app/models/fyp_registry.py` and `backend/alembic/versions/fd3e4f5a6b7c_add_fyp_registry_metadata.py`: audited administrative registry metadata.
- `frontend/src/portals/shared/FypRegistryPage.tsx`: responsive filter/table/detail UI reused by Coordinator and Admin wrappers.
=======
Paths link to existing source; they are not copies of a Module 3 implementation.

- Internal template and rule reference foundation: [models](../../backend/app/models/template_reference.py), [schemas](../../backend/app/schemas/templates.py), [admin endpoints](../../backend/app/main.py), [admin UI](../../frontend/src/AdminTemplateReferences.tsx), [migration](../../backend/alembic/versions/d5e6f7a8b9c0_add_template_reference_versions.py), [tests](../../backend/tests/test_template_references.py). These represent reference metadata and rules, not official proposal submissions or compliance analysis.
- Shared access and team context: [authentication](../../backend/app/auth.py), [team model](../../backend/app/models/team.py), [supervisor assignments](../../backend/app/supervisor_assignments.py) and [assignment tests](../../backend/tests/test_supervisor_assignments.py). They do not implement proposal-specific analysis access.
- Collaboration context: [group channels](../../backend/app/group_channels.py) include a Proposal channel; [group AI](../../backend/app/group_ai.py) is a separate advisory chatbot. Neither is a proposal lifecycle or compliance checker.
- Existing project records: [decisions](../../docs/decisions.md), [feature tracker](../../docs/p1-feature-tracker.md), [workflow record](../../docs/p1-workflows.md). The tracker and proposed pipeline are historical context, not evidence of implemented Module 3 behavior.

- Non-operational proposal identity and version foundation: [model](../../backend/app/models/proposal.py), [migration](../../backend/alembic/versions/c3d4e5f6a7b8_proposal_foundation.py), [tests](../../backend/tests/test_proposal_foundation.py). No proposal routes or lifecycle operations are supplied by these files. Migration application was not checked in this audit.
>>>>>>> c3b9ee80fadf2c13df694c08620da65daf55cb12
