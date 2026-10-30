# Student Portal visibility matrix

| Feature area | Frontend support | Backend/API support | Test status | Browser-usable | Decision |
|---|---|---|---|---|---|
| Team & Collaboration Hub | `StudentTeamPhase`, `GroupChannels` | `/api/v1/group-channels` and existing team/session authorization | Existing collaboration tests pass | Yes, subject to team membership | Visible (Partial) |
| Join requests, invitations, matching | Existing collaboration components/services | `/api/v1/join-requests`, `/api/v1/invitations`, `/api/v1/team-matching` | Existing backend workflow tests pass | Available through the collaboration workflow | Visible inside Team Hub |
| Supervisor selection and proposal requests | `StudentSupervisorSelectionPdf`, `RequestConversation`, `ProposalReferenceSearch` | `/api/v1/supervisor-requests`, `/api/v1/proposal-references`, conversation routes | Supervisor/reference/conversation tests pass | Yes | Visible (Partial) |
| Proposal PDF extraction | `StudentSupervisorSelectionPdf` | One-page PDF extraction and confirmation routes | Supervisor request tests pass | Yes | Visible inside Supervisor Requests |
| Proposal compliance | `ProposalComplianceView` | Mounted `/api/v1/module-03` routes; active Admin baseline required | Module 03 tests pass | Upload/report flow is usable when a baseline is activated | Visible (Partial) |
| Archive and deterministic knowledge search | `KnowledgeSearch`, `ArchivedProjectDetail` | `/api/v1/archived-projects/search` and authorized detail/document routes | Archive tests pass | Yes; semantic/LLM search is not advertised | Visible (Implemented) |
| Panel scheduling/evaluation | No mounted Student component | No Student route | Not implemented | No | Hidden |
| Coordinator proposal control | No mounted Student component | No Student route | Not implemented | No | Hidden |
| Progress/supervision dashboard | No mounted Student component | No Student route | Not implemented | No | Hidden |
| Final handover | No mounted Student component | No Student route | Not implemented | No | Hidden |

The Student sidebar and overview render only the four visible areas above. Future source files, backend routes, migrations, and documentation remain untouched.
