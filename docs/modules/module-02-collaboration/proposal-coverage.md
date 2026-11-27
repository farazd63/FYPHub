# Current Module 2 coverage

This document describes the current implementation boundary. Retired proposal-era matching and multi-channel code is not part of the current product flow.

| Current requirement | Status | Evidence |
| --- | --- | --- |
| Registered teams, membership and cycle-scoped ownership | Complete | `backend/app/main.py`, `backend/app/models/team.py`, team-registration schemas and tests. |
| Assignment-scoped group collaboration | Complete | `backend/app/collaboration_channels.py`, `frontend/src/portals/student/modules/StudentCollaborationChannel.tsx`, supervisor workspace components, and collaboration access tests. One active channel is created per team-supervisor assignment; reassignment archives the previous channel. |
| Student AI assistant | Partial | `backend/app/group_ai.py`, `backend/app/models/student_ai.py`, and `frontend/src/GroupAIChat.tsx`. The local Ollama integration is implemented; live model availability remains environment-dependent. |
| Project progress and supervision records | Complete | `backend/app/project_workflow.py`, `frontend/src/portals/student/modules/StudentProgressDashboard.tsx`, supervisor workspace, and `backend/tests/test_project_workflow.py`. |
| AI teammate compatibility matching, invitations, join requests and temporary match chat | Retired | These flows are not mounted by the current frontend and their routes/components/models/tests were removed. |

The current product therefore has one assignment-scoped collaboration channel, not the former seven named group channels.
