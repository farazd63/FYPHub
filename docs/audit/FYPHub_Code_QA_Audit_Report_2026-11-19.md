# FYPHub — Independent Code, QA, Security & Examiner Audit Report

**Date:** 19 November 2026 (Asia/Karachi)  
**Scope:** Latest repository snapshot on `main` (clean working tree)  
**Role of this document:** Audit / QA / examiner readiness only — **no application code changes** were made as part of this engagement.  
**Auditor posture:** Combined code auditor, QA analyst, security reviewer, and examiner-demo readiness assessor.

---

## 1. Executive summary

FYPHub is a **web-based Final Year Project lifecycle platform** (not a Flutter app). The current codebase is a substantial P1 Mid implementation of **Modules 1–3** (governance, collaboration, proposal/compliance), with role portals for Admin, Student, Supervisor, Coordinator, and Panel/Evaluator.

**Overall maturity judgment**

| Dimension | Judgment |
| --- | --- |
| Architecture & stack | Strong, modern, defence-ready narrative |
| Module 1–3 functional depth | High for a university FYP; many workflows exist |
| Production / clean-install readiness | **Weak** — migration graph and schema drift are blocking |
| Security baseline | Good foundations; several examiner-visible gaps remain |
| Proposal completeness (12 modules) | **Incomplete by design for P1 Mid**; Modules 4–12 largely future |
| Demo polish / “graceful end-to-end” | Risk of examiner “why isn’t X working?” questions |

**Bottom line for defence / examiner delivery:** The project is impressive in breadth and documentation, but a clean examiner machine will **not** currently install and run reliably from migrations alone. Demonstration must be rehearsed on a **known-good database image** (or a repaired single Alembic head), with clear verbal ownership of what is implemented vs. proposed for later phases.

---

## 2. What the repository is

### 2.1 Product intent (from short/long proposals)

Proposed as an agentic AI-driven platform covering the **full FYP lifecycle** across **twelve modules**, five roles, LLM/RAG/GraphRAG assistance, originality analysis, defence scheduling, evaluation, progress/risk intelligence, archive, and institutional knowledge search.

### 2.2 Actual delivered boundary (code + docs)

Active delivery target is **P1 Mid = Modules 1–3**, evidenced by:

- `docs/p1-feature-tracker.md`
- `docs/architecture/module-inventory.md`
- `docs/defence/` (145-page defence guide + inventory)
- Implementation concentrated in Admin/Student/Supervisor/Coordinator/Evaluator portals and Module 3 compliance workspace

### 2.3 Technology stack (verified)

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 8, TypeScript 6, Tailwind CSS 4 |
| Backend | Python 3.12-targeted FastAPI (`fastapi==0.143.0`), Uvicorn |
| ORM / DB | SQLAlchemy 2, PostgreSQL 17 (Compose) / pgvector 0.8.6 |
| Migrations | Alembic (**68 revision files**; **3 heads** at audit time) |
| Auth | Opaque HttpOnly cookie sessions; Argon2id passwords; SHA-256 token hashes |
| AI | Ollama (local) and optional Groq; deterministic fallbacks |
| Packaging | Docker Compose (db, migrate, ollama, backend, frontend/Nginx) |
| Tests | ~45 backend `unittest` modules; ~34 frontend Node test files |

**Note:** Folder path `Flutter_Projects` is historical naming only; there is no Flutter/`pubspec.yaml` application in this repository.

---

## 3. Repository inventory — what already exists

### 3.1 Module map (current code)

**Module 01 — Governance & academic configuration**

- Users/roles, academic cycles & group policies, supervisor capacity  
- Template-reference / evaluation-rubric / deadline / reminder **versioned drafts**  
- Document upload requirements, dashboard requirements  
- Append-only admin audit events  
- Admin portal screens and many ADMIN APIs in `backend/app/main.py` and related routers  

**Module 02 — Teams & collaboration**

- Shared student group accounts, team registration, duplicate-member constraints  
- Compatibility preferences / matching / join requests / invitations (per later migrations & tracker updates)  
- Collaboration channels, messages, read markers, group AI assistant hooks  
- Student collaboration UI under `frontend/src/portals/student/`  

**Module 03 — Proposal, compliance, supervisor requests, archive, evaluation/progress foundations**

- Template upload/activation, submissions, deterministic compliance engine, AI summary hooks  
- Supervisor request workflow + conversations + PDF helpers across portals  
- Archived project import/search (currently **deterministic**, not proven vector/RAG search)  
- Project progress / panel schedule / evaluation APIs and UI pieces  

**Shared core**

- Auth, password reset, CORS/origin checks, structured request logging (`X-Request-ID`)  
- Role portals: Admin, Student, Supervisor, Coordinator, Evaluator  

### 3.2 Scale indicators

- Backend application Python: ~12k+ LOC under `backend/app`  
- Frontend TS/TSX: ~5k LOC under `frontend/src` (plus large `App.tsx` ~1.3k LOC)  
- OpenAPI at runtime: **230 paths / 264 operations**  
- Restored demo DB: **75 public tables**, multi-role sample users  
- Defence package already generated (PDF/DOCX/MD + `technical-inventory.json`)  

### 3.3 Documentation strength (examiner asset)

The repository already contains unusually strong academic/defence documentation:

- Complete defence guide  
- Feature tracker with verified/partial/not-started language  
- Workflow docs, matrices, module manifests, orphan-audit notes  

This is a **positive differentiator** if claims stay aligned with runnable reality.

---

## 4. Runtime verification performed on this machine

### 4.1 Environment constraints observed

| Dependency | Status on audit machine |
| --- | --- |
| Docker Desktop / `docker` CLI | **Not installed** — Compose stack could not be used |
| Homebrew PostgreSQL 16 | Running on `127.0.0.1:5432` |
| pgvector | Not present initially; built/installed locally for PG16 as `0.8.6` |
| Ollama | **Not installed** — live AI model calls not verified |
| Node / npm | Available; frontend deps installed; **production build succeeded** |
| Python | 3.13 venv used for backend (project targets 3.12 in Docker) |

### 4.2 What was started

1. Created local `.env` from `.env.example` (gitignored).  
2. Created DB `fyphub_p1` + role `fyphub_p1_user`.  
3. **Fresh `alembic upgrade heads` failed** (see §5).  
4. Restored `fyphub_backup_20261109_234143.sql` → 75 tables, sample accounts.  
5. Started FastAPI on `http://127.0.0.1:8010`.  
6. Started Vite on `http://127.0.0.1:5173` (HTTP 200).  
7. Frontend `npm run build` passed (chunk size warning >500 KB).  

### 4.3 Smoke results (API)

| Check | Result |
| --- | --- |
| `GET /health` | **200** `{"status":"ok","service":"fyphub-p1-api"}` |
| `GET /health/ready` | **200** after pgvector installed |
| OpenAPI load | **230 paths / 264 operations** |
| Bad login | **401** `Invalid credentials.` |
| Foreign Origin login | **403** `Origin is not allowed.` |
| Unauthenticated `/api/v1/admin/me` | **401** |
| Password-reset status | **200** (`development_mode: true`, SMTP not configured) |
| Login + `/api/v1/admin/me` (after local schema patch for missing columns) | **200** ADMIN session |
| `GET /api/v1/academic-cycles` (after patch) | **200** (cycles returned) |
| `GET /api/v1/admin/users` | **200** (23 users in restored dump) |
| Focused backend unit tests (`password_policy`, ollama provider mocks, groq config) | **12/12 OK** |

### 4.4 Critical runtime defect before schema repair

Against the restored Nov-9 dump **without** later columns, both:

- `GET /api/v1/academic-cycles`
- `POST /api/v1/auth/login` (because login builds account/cycle context)

failed with:

```text
UndefinedColumn: column academic_cycles.academic_year does not exist
```

A temporary local SQL patch adding `academic_year` / `session` unblocked login for smoke testing. **That confirms schema drift between latest ORM/code and the checked-in SQL backup**, and that migrations which should have applied those columns are not cleanly reachable from a single head.

---

## 5. Highest-severity findings (fix first)

### P0 — Migration graph is broken for clean installs

- `alembic heads` reports **three heads**:
  - `fb1c2d3e4f5`
  - `qa1b2c3d4e5f`
  - `ri2d3e4f5a6b`
- `alembic upgrade head` fails by design; `upgrade heads` fails with:
  - `UndefinedTable: relation "m03_reference_templates" does not exist`
- Restored dump stamps only `qa1b2c3d4e5f`, while code expects schema from other branches (e.g. `n456a001` year/session columns).

**Impact:** Examiner/faculty machine “clone → compose up / alembic upgrade” is **not trustworthy**.  
**Recommendation:** Create a single merge migration to one head; verify empty-DB upgrade; refresh a new dump; document the one approved recovery path.

### P0 — Schema/code mismatch causes HTTP 500 on core auth/cycle routes

Without aligned migrations, the product appears “down” at first login — the worst possible examiner first impression.

### P1 — SQL dump committed in repository

`fyphub_backup_20261109_234143.sql` (~2.1 MB) contains live-like emails, roles, and password hashes. `gitleaks` reported findings against this dump. Even if hashes are Argon2id, **shipping a populated database dump in git is an institutional/privacy risk** and confuses “sample” vs “production-like” data.

**Recommendation:** Keep dumps out of git (or use anonymized seed SQL only); rotate any real credentials that ever lived in that environment.

### P1 — Unauthenticated academic-cycle listing

`GET /api/v1/academic-cycles` and group-policy read are reachable without auth (by design today). For a university system, confirm whether public cycle metadata is intentional; if not, require auth.

### P1 — Temporary auth diagnostic logging still active

`TEMP_AUTH_DIAGNOSTIC` warnings fire on login/`/auth/me`/`/admin/me`. Safe metadata, but examiner-visible noise and a sign of unfinished cleanup.

### P1 — Login has no account lockout / IP rate limit

Password-reset has an in-memory IP rate limit; **login does not**. Argon2id slows brute force, but a defence discussion should acknowledge missing lockout/CAPTCHA/WAF.

### P2 — Frontend dead/duplicate stubs

Nine `AdminDocumentRequirementManager*.tsx` variants exist (mostly tiny stubs). This looks unfinished to an examiner browsing source.

### P2 — Frontend npm audit: 9 moderate vulnerabilities

Build succeeds, but dependency hygiene should be cleaned before final submission packaging.

### P2 — Large monolithic surfaces

- `backend/app/main.py` ~2.2k lines  
- `frontend/src/App.tsx` ~1.3k lines  
Harder to defend modularity claims under deep questioning.

### P2 — AI / RAG marketing vs implementation honesty

Proposal language includes RAG/GraphRAG/vector similarity. Runtime evidence and project docs already note **deterministic archive search** and AI fallbacks. pgvector is installed for readiness, but **semantic originality / GraphRAG are not proven as complete modules**.

### P3 — Reminder/deadline “configuration without enforcement”

Deadlines and reminder rules can be authored, but delivery/enforcement/escalation remain incomplete — correctly marked Partial in the tracker; examiners will ask “does it actually remind anyone?”

---

## 6. Security assessment (examiner + auditor view)

### 6.1 Strengths

- Argon2id password hashing; opaque session tokens hashed at rest  
- HttpOnly + SameSite=Lax cookies; Secure flag when HTTPS  
- CORS allowlist + mutating Origin validation  
- Role guards via `require_roles`  
- Dummy password verify path on unknown login (timing hygiene intent)  
- Password reset: hashed tokens, expiry, single-use, session revoke, generic responses (with controlled demo/dev exceptions)  
- Last-active-admin protection with advisory lock  
- Append-only audit events with DB protections claimed in docs  
- Structured request logging with request IDs  
- Document storage root configurable; Docker non-root backend user  

### 6.2 Weaknesses / residual risk

| Area | Risk | Notes |
| --- | --- | --- |
| Migration integrity | High | Clean install unsafe |
| Secrets in repo dump | High/Medium | SQL backup with hashes + personal emails |
| Brute-force on login | Medium | No lockout |
| Dev reset link endpoint | Medium if mis-deployed | Guarded by `APP_ENV` + loopback; keep production locked |
| Registration mode `demo` | Medium | Broadens signup; must not ship as default |
| File upload threat model | Medium | Type/size limits exist conceptually; no antivirus; Nginx body size defaults may surprise |
| AI provider SSRF controls | Low–Medium | Ollama host allowlist present — good; keep strict |
| In-memory rate limits | Low–Medium | Lost on multi-instance; not durable |
| Public cycle endpoints | Low–Medium | Confirm policy |
| Temporary diagnostics | Low | Remove before final defence build |

### 6.3 What was **not** found

No evidence of obvious `eval`/`pickle`/`subprocess` shell abuse in application code during quick scan. Parameterized SQLAlchemy usage appears dominant (no f-string raw SQL hits in the quick scan).

---

## 7. Proposal vs implementation — examiner “question mark” map

Use this section to eliminate “why didn’t you build X?” surprises.

### Covered well enough to demo (with rehearsal)

1. Multi-role login and portal shells  
2. Admin user/role management narrative  
3. Academic cycles / group policy story  
4. Supervisor capacity configuration story  
5. Student group registration / shared account model  
6. Collaboration channel foundation (Module 2)  
7. Proposal template + compliance report baseline (Module 3)  
8. Supervisor request / conversation workflow across roles  
9. Archive import/search as institutional knowledge **starter**  
10. Defence documentation package  

### Partial — say “configured but not fully operational”

- Deadline reminders / escalation **execution**  
- Evaluation criteria **approval & live scoring authority**  
- Workflow policy **publication / state machine**  
- Official blank template file lifecycle vs internal metadata versions  
- AI summaries when Ollama/Groq unavailable (deterministic fallback)  

### Proposed but largely future (Modules 4–12 / advanced AI)

Be explicit these are **roadmap**, not current claims:

- Full semantic originality / RAG / GraphRAG knowledge system  
- Optimized defence scheduling AI  
- Deep progress risk intelligence / agentic orchestration at proposal scale  
- Full institutional analytics suite  

**Recommendation:** Prepare a one-page “Implemented / Partial / Future” slide that matches `docs/p1-feature-tracker.md`.

---

## 8. QA matrix — what an examiner can check

### 8.1 Happy-path demo script (recommended order)

1. Open frontend; show sign-in for Admin / Supervisor / Student / Coordinator / Evaluator.  
2. Admin: users & roles; cycles; capacity; deadlines (preview); audit history.  
3. Student: group context; collaboration channel; required documents; supervisor selection/request.  
4. Supervisor: requests inbox; capacity; assigned teams.  
5. Module 3: template activation → student submission → compliance report download.  
6. Archive: search a known archived title; open detail.  
7. Show `/health` and `/health/ready`; briefly open `/docs` if allowed.  
8. Show defence guide PDF as documentation evidence — not as a substitute for live demo.

### 8.2 Negative / security checks an examiner may try

- Wrong password → generic 401  
- Access Admin API without cookie → 401  
- Student cookie against Admin route → 403  
- Cross-origin mutating request → 403  
- Inactive user / dissolved student group login rejection  
- Password reset enumeration behaviour in production vs development  
- Upload oversized/unsupported file  
- Attempt to register individual student via retired `/api/v1/auth/register` → 403  

### 8.3 Quality risks to rehearse answers for

- “Is search semantic?” → Currently deterministic/title/metadata oriented; vector extension present for future.  
- “Do reminders send email?” → Rules stored; delivery not complete.  
- “Where is GraphRAG?” → Proposed; not P1 Mid complete.  
- “Why multiple Alembic heads?” → Known technical debt; must be closed before handover.  
- “Can I install from zero?” → Not until merge migration + verified Compose path.

---

## 9. What is working vs not working (as of this audit)

### Working / verified here

- Backend process boots; health endpoints; large OpenAPI surface  
- Frontend Vite serves; production build compiles  
- Auth controls (401/403) behave correctly on smoke tests  
- After schema alignment patch: Admin login, `/admin/me`, users list, cycles list  
- Focused security-related unit tests pass  
- Extensive automated test files exist (full suite not re-run end-to-end in this session due to migration/schema instability)

### Not working / blocked without repair

- Clean DB migration to all heads  
- Out-of-the-box Docker Compose on this Mac (Docker missing)  
- Live Ollama AI paths (Ollama missing)  
- Backup DB alone against latest code (schema drift → 500s)  
- Some frontend source tests (e.g. password-policy frontend test failed under Node test runner in this environment — investigate before claiming 100% frontend green)

### Flaky operational observation

Uvicorn needed restarts during the session after heavy local experimentation. Treat as environment noise, but rehearse a clean start script for defence day.

---

## 10. Recommended future inclusions (to remove examiner doubt)

These are **additions / completions**, not removals of FYP scope.

### Must-do before a high-stakes demo

1. **Merge Alembic to one head** + empty-DB upgrade test + new anonymized seed.  
2. **One-command demo runbook** (Compose preferred) with known accounts.  
3. Remove `TEMP_AUTH_DIAGNOSTIC` logging.  
4. Rehearse 10-minute script covering all five roles.  
5. Prepare honest “AI boundary” statement (what LLM does vs deterministic engines).  
6. Strip or replace committed SQL dump with sanitized seed.  

### Should-do for stronger impression (still in Modules 1–3)

7. Login rate-limit / lockout policy.  
8. End-to-end browser test of one student→supervisor→coordinator path.  
9. Consolidate duplicate Admin Document Requirement manager files to one real screen.  
10. Enforce or clearly label public academic-cycle endpoints.  
11. Deadline reminder **at least** as “in-app notification” if email SMTP is not ready.  
12. Compliance report golden screenshots + sample PDFs in `sample-data/`.  
13. Reduce `App.tsx` / `main.py` monoliths via routers/components (maintainability viva).  
14. Add CI job: `alembic upgrade heads` on empty Postgres + backend tests + frontend build.  
15. npm audit cleanup; pin Node engine in README.  

### Nice-to-have differentiators (if time remains)

16. Semantic archive search using pgvector on a small embedding set (even limited) to justify the extension.  
17. Supervisor matching explanation UI (“why this supervisor?”).  
18. Panel scheduling conflict demo with a deliberate collision.  
19. Accessibility pass (contrast already has a frontend test file — run and fix).  
20. Printable “examiner checklist” one-pager derived from this report.

### Do **not** remove

Do not gut Module 1–3 features to “simplify.” Extra scope cleanup should target **stubs, dead duplicates, temporary diagnostics, and unsafe dumps** — not core FYP workflows.

---

## 11. Suggested viva / examiner questions (and safe answers)

1. **Why cookie sessions instead of JWT?** — Server-side revocation, hashed tokens, academic admin control.  
2. **How do you prevent last admin lockout?** — Advisory lock + active admin count check.  
3. **How is student identity modelled?** — Shared group account; individual public signup retired.  
4. **Is AI the authority?** — No; human roles retain final academic authority; AI is assistive with fallbacks.  
5. **What does compliance check actually verify?** — Deterministic structural/rule engine first; AI summary optional.  
6. **Why pgvector if search is deterministic?** — Readiness for semantic features; current archive path is explicit/deterministic.  
7. **What is P1 vs full proposal?** — P1 Mid Modules 1–3; remaining modules are phased.  

---

## 12. Immediate non-code actions for the team

1. Install Docker Desktop **or** publish a verified non-Docker runbook for Mac/Windows.  
2. Fix migration heads this week — treat as release blocker.  
3. Create a defence-day database snapshot that matches current code exactly.  
4. Decide demo AI mode: Ollama models pre-pulled **or** Groq key **or** deterministic-only with scripted honesty.  
5. Walk the five portals with a stopwatch; cut any screen that 500s.  
6. Keep this audit report beside the defence guide during rehearsal.

---

## 13. Conclusion

FYPHub already looks like a serious engineering FYP: real role portals, substantial APIs, thoughtful security primitives, and excellent written defence material. The largest threats to a graceful ending are **not missing “extra features”** — they are:

1. **broken multi-head migrations / schema drift**,  
2. **over-claiming AI/RAG relative to what runs**, and  
3. **demo environment fragility** (Docker/Ollama/dump mismatch).

Close those three, rehearse a tight Modules 1–3 story, and the examiner experience becomes coherent: a finished P1 Mid product with a credible roadmap rather than a partially bootable prototype.

---

## Appendix A — Commands used for verification (reference)

```bash
# Backend
cd backend && source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010

# Frontend
cd frontend && ./node_modules/.bin/vite --host 127.0.0.1 --port 5173
npm run build

# Health
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8010/health/ready

# Alembic (currently problematic)
cd backend && alembic heads
alembic upgrade heads
```

## Appendix B — Audit limitations

- Full backend suite not re-executed against a fully migrated empty database (blocked by P0 migrations).  
- Browser UI click-through not exhaustively automated in this session.  
- Live LLM inference not verified (Ollama absent).  
- Docker Compose path not executable here (Docker absent).  
- Local temporary password was set on one restored admin account **only for smoke testing** on the auditor machine; rotate before any shared defence environment.

---

*End of report.*
