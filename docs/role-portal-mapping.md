# Role and portal mapping

The application keeps the existing database and authentication role value `PANEL_MEMBER` for compatibility. Its only user-facing portal and label are **Evaluator**.

| Stored role | User-facing label | Portal | Current authorized scope |
| --- | --- | --- | --- |
| `STUDENT` | Student | `StudentPortal` | Own student/team workflows exposed by the existing APIs |
| `SUPERVISOR` | Supervisor | `SupervisorPortal` | Assigned supervisor requests and related authorized records |
| `COORDINATOR` | Coordinator | `CoordinatorPortal` | Read-only supervisor-request monitoring and authorized request conversations, filtered by cycle, supervisor, status, and date |
| `PANEL_MEMBER` | Evaluator | `EvaluatorPortal` | Evaluator shell; no assignment/scoring API is currently available |
| `ADMIN` | Administrator | `AdminPortal` | Administrator-only configuration, read-only supervisor-request monitoring, audit history, and authorized request conversations |

## FYP registry visibility

| Role | Registry surface | Scope and mutation policy |
| --- | --- | --- |
| `COORDINATOR` | **FYP Students & Projects** | Authorized read-only student/team/project, proposal, assignment, history, conversation, audit, archive-match, and compliance metadata. |
| `ADMIN` | **FYP Registry & Project Monitoring** | Full authorized registry read plus audited administrative metadata corrections; cannot edit original PDFs, extraction snapshots, supervisor decisions, or audit history. |
| `SUPERVISOR` | Registry API only | Active assigned teams only; no global registry access. |
| `STUDENT` | Registry API only | Own request/team records only, including shared-team ownership. |
| `PANEL_MEMBER` | None | Registry endpoints are role-protected and Panel/Evaluator access is denied. |

The Evaluator portal deliberately shows safe unavailable states until evaluator assignment, proposal review, defense scheduling, scoring, feedback, and decision-history endpoints exist. It does not fabricate records or call unrelated APIs. There is no separate user-facing Panel Member portal or label.
