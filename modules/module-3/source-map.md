# Source map

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
