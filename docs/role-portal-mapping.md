# Role and portal mapping

The application keeps the existing database and authentication role value `PANEL_MEMBER` for compatibility. Its only user-facing portal and label are **Evaluator**.

| Stored role | User-facing label | Portal | Current authorized scope |
| --- | --- | --- | --- |
| `STUDENT` | Student | `StudentPortal` | Own student/team workflows exposed by the existing APIs |
| `SUPERVISOR` | Supervisor | `SupervisorPortal` | Assigned supervisor requests and related authorized records |
| `COORDINATOR` | Coordinator | `CoordinatorPortal` | Coordinator-scoped monitoring and workflow records |
| `PANEL_MEMBER` | Evaluator | `EvaluatorPortal` | Evaluator shell; no assignment/scoring API is currently available |
| `ADMIN` | Administrator | `AdminPortal` | Administrator-only configuration and monitoring |

The Evaluator portal deliberately shows safe unavailable states until evaluator assignment, proposal review, defense scheduling, scoring, feedback, and decision-history endpoints exist. It does not fabricate records or call unrelated APIs. There is no separate user-facing Panel Member portal or label.
