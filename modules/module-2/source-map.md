# Module 2 source map

Paths are repository-relative. The Long Proposal section 9.3 on pages 9?10 defines scope.

- Formation, roster and uniqueness: `backend/app/main.py`, `backend/app/models/team.py`, `backend/app/schemas/team_registration.py`, `backend/app/models/student_roster.py`; `backend/tests/test_team_registration.py`, `test_team_constraints.py`, `test_cycle_concurrency.py`.
- Preferences and team suggestions: `backend/app/team_matching.py`, `backend/app/team_compatibility.py`, `backend/app/models/team_preference.py`, `frontend/src/TeamMatching.tsx`; `backend/tests/test_team_matching.py`, `test_team_compatibility.py`.
- Requests, invitations and identity proof: `backend/app/join_requests.py`, `invitations.py`, `anonymous_verification.py`, `individual_verification.py`, corresponding `models/`, `frontend/src/JoinRequests.tsx`, `Invitations.tsx`; `backend/tests/test_join_requests.py`, `test_invitations.py`, `test_anonymous_verification.py`, `test_individual_verification.py`.
- Match chat: `backend/app/match_chat.py`, `backend/app/models/match_chat.py`, `frontend/src/MatchChat.tsx`, `frontend/src/matchChatView.mjs`; `backend/tests/test_match_chat.py`, `frontend/tests/match-chat.test.mjs`.
- Channels and group chatbot: `backend/app/group_channels.py`, `group_ai.py`, `backend/app/models/group_message.py`, `frontend/src/GroupChannels.tsx`, `GroupAI.tsx`; `backend/tests/test_group_channels.py`, `test_group_ai.py`.
- Decisions: `docs/decisions.md` records shared team accounts and creator/invitee verification authority. `modules/module-2/verification.md` records actual checks.

- Individual student-to-group discovery: `backend/app/team_matching.py`, `backend/app/anonymous_verification.py`, `backend/app/models/anonymous_verification.py`, `backend/alembic/versions/b2c3d4e5f6a7_student_matching_proof.py`, `frontend/src/StudentMatching.tsx`; `backend/tests/test_student_matching.py`.
