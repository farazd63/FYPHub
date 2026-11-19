# Phase 2 contrast fix — review report

**Phase 3 not started.** Stop here for Phase 2 review.

Live crawl: five roles × every nav route (+ key sub-views). Fail if any visible text < 4.5:1 (3:1 large).

## Contrast counts per screen

### ADMIN — 6 screens, 0 below AA

| Screen | Below AA | Total | H1 |
|---|---:|---:|---|
| Overview | **0** | 40 | Academic cycles |
| FYP Archive | **0** | 10 |  |
| Student Groups | **0** | 96 | Student Groups |
| Users & Roles | **0** | 138 | Users & Roles |
| Supervisor Capacity | **0** | 68 | Supervisor Capacity |
| Required Documents | **0** | 61 | Required Documents |

### STUDENT — 7 screens, 0 below AA

| Screen | Below AA | Total | H1 |
|---|---:|---:|---|
| Overview | **0** | 46 | Your FYP workspace |
| Required Documents & Uploads | **0** | 16 |  |
| Proposal Compliance Check | **0** | 11 | Compliance Report |
| Supervisor Information | **0** | 13 | Supervisor information |
| Supervisor Selection & Proposal Requests | **0** | 14 | Supervisor Selection & Allocation |
| Project Progress & Supervision Dashboard | **0** | 68 | Project progress |
| FYP Archive & Knowledge Search | **0** | 3 | FYP Knowledge Search & Analytics |

### SUPERVISOR — 6 screens, 0 below AA

| Screen | Below AA | Total | H1 |
|---|---:|---:|---|
| Overview | **0** | 28 | Overview |
| Overview › view group|open group|open request | **0** | 20 | Supervisor Requests |
| Supervisor Requests | **0** | 20 | Supervisor Requests |
| Assigned Students & Teams | **0** | 2 | Assigned Students & Teams |
| Supervisor Capacity | **0** | 25 | Supervisor Capacity |
| Decision History | **0** | 47 | Decision History |

### COORDINATOR — 5 screens, 0 below AA

| Screen | Below AA | Total | H1 |
|---|---:|---:|---|
| Supervisor Requests | **0** | 278 | Supervisor Request Monitoring |
| Supervisor Requests › open panel scheduling | **0** | 179 | Panel Scheduling & Defense |
| Supervisor Requests › panel scheduling | **0** | 17 | Panel Scheduling & Defense |
| Panel Scheduling | **0** | 17 | Panel Scheduling & Defense |
| Panel Scheduling › panel scheduling | **0** | 17 | Panel Scheduling & Defense |

### EVALUATOR — 12 screens, 0 below AA

| Screen | Below AA | Total | H1 |
|---|---:|---:|---|
| Overview | **0** | 46 | Evaluation workspace |
| Evaluation Queue | **0** | 15 | Evaluation Queue |
| Evaluation Queue › add criterion | **0** | 15 | Evaluation Queue |
| Proposal Review | **0** | 161 | Compliance Report |
| Evaluation Criteria | **0** | 15 | Evaluation Criteria |
| Evaluation Criteria › add criterion | **0** | 15 | Evaluation Criteria |
| Scoring & Feedback | **0** | 15 | Scoring & Feedback |
| Scoring & Feedback › add criterion | **0** | 15 | Scoring & Feedback |
| Defense Schedule | **0** | 15 | Defense Schedule |
| Defense Schedule › add criterion | **0** | 15 | Defense Schedule |
| Decision History | **0** | 15 | Decision History |
| Decision History › add criterion | **0** | 15 | Decision History |

**Crawl total below-AA: 0**

## Phone width (390px)

| Portal | Target | Overflow-X | Below AA |
|---|---|---:|---:|
| ADMIN | __phone_390__::Supervisor Capacity | 0 | 0 |
| ADMIN | __phone_390__::Users & Roles | 0 | 0 |
| STUDENT | __phone_390__::Supervisor Selection & Allocation | 0 | 0 |
| STUDENT | __phone_390__::Project progress | 0 | 0 |
| SUPERVISOR | __phone_390__::Supervisor Capacity | 0 | 0 |
| SUPERVISOR | __phone_390__::Decision History | 0 | 0 |
| COORDINATOR | __phone_390__::Panel Scheduling & Defense | 0 | 0 |
| COORDINATOR | __phone_390__::Supervisor Request Monitoring | 0 | 0 |
| EVALUATOR | __phone_390__::Scoring & Feedback | 0 | 0 |
| EVALUATOR | __phone_390__::Evaluation Queue | 0 | 0 |
| SUPERVISOR | supervisor-capacity.png (capture) | 0 | — |
| STUDENT | student-project-progress.png (capture) | 0 | — |
| EVALUATOR | evaluator-scoring-feedback.png (capture) | 0 | — |
| COORDINATOR | coordinator-panel-scheduling.png (capture) | 0 | — |

## Layout width

| Role | Viewport | Content width | Dead right |
|---|---:|---:|---:|
| SUPERVISOR | 1366 | 1022 | 24 |
| SUPERVISOR | 1680 | 1336 | 24 |
| SUPERVISOR | 1920 | 1576 | 24 |
| STUDENT | 1366 | 1022 | 24 |
| STUDENT | 1680 | 1336 | 24 |
| STUDENT | 1920 | 1576 | 24 |
| EVALUATOR | 1366 | 1022 | 24 |
| EVALUATOR | 1680 | 1336 | 24 |
| EVALUATOR | 1920 | 1576 | 24 |
| COORDINATOR | 1366 | 1022 | 24 |
| COORDINATOR | 1680 | 1336 | 24 |
| COORDINATOR | 1920 | 1576 | 24 |

Content column fills the pane after the sidebar (`max-width: none`). ~24px right is shell padding.

## Screenshots

- `supervisor-capacity.png` — Supervisor Capacity (dark metric tiles + Available pill)

- `student-project-progress.png` — Student Project Progress (token-based cards/bars/buttons)

- `evaluator-scoring-feedback.png` — Evaluator Scoring & Feedback (labels + fy-btn primary/secondary)

- `coordinator-panel-scheduling.png` — Coordinator Panel Scheduling (labels + Reschedule / Create)

## Auth

- After login: `http://127.0.0.1:5173/admin`
- After logout: `http://127.0.0.1:5173/login`
- Email cleared: `''`

## Root fixes

1. Labels → `--fy-text` (no leftover navy label ink).

2. Progress cards/icons/buttons/milestone bars → theme tokens.

3. Capacity year tiles → dark surfaces; Available pill success ink ≥4.5:1.

4. `--fy-text-secondary` → `#d5dce8` (Decision History).

5. Admin Upload Excel / Save capacity → `fy-btn--primary` + on-brand ink.

6. Shared `fy-btn` on Evaluator/Coordinator/Supervisor actions; disabled primary keeps gold.

7. Content fills 1366 / 1680 / 1920.

8. Login → role home; logout → `/login` + clear email.

9. `tests/portal-contrast-crawl.test.mjs` — five-role full-route crawl.

**Stop for Phase 2 review.**
