# Source map

Paths link to existing source; they are not copies of a Module 3 implementation.

- Internal template and rule reference foundation: [models](../../backend/app/models/template_reference.py), [schemas](../../backend/app/schemas/templates.py), [admin endpoints](../../backend/app/main.py), [admin UI](../../frontend/src/AdminTemplateReferences.tsx), [migration](../../backend/alembic/versions/d5e6f7a8b9c0_add_template_reference_versions.py), [tests](../../backend/tests/test_template_references.py). These represent reference metadata and rules, not official proposal submissions or compliance analysis.
- Shared access and team context: [authentication](../../backend/app/auth.py), [team model](../../backend/app/models/team.py), [supervisor assignments](../../backend/app/supervisor_assignments.py) and [assignment tests](../../backend/tests/test_supervisor_assignments.py). They do not implement proposal-specific analysis access.
- Collaboration context: [group channels](../../backend/app/group_channels.py) include a Proposal channel; [group AI](../../backend/app/group_ai.py) is a separate advisory chatbot. Neither is a proposal lifecycle or compliance checker.
- Existing project records: [decisions](../../docs/decisions.md), [feature tracker](../../docs/p1-feature-tracker.md), [workflow record](../../docs/p1-workflows.md). The tracker and proposed pipeline are historical context, not evidence of implemented Module 3 behavior.

- Non-operational proposal identity and version foundation: [model](../../backend/app/models/proposal.py), [migration](../../backend/alembic/versions/c3d4e5f6a7b8_proposal_foundation.py), [tests](../../backend/tests/test_proposal_foundation.py). No proposal routes or lifecycle operations are supplied by these files. Migration application was not checked in this audit.
