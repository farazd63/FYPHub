# Verification

<<<<<<< HEAD
Run from `backend`: focused Module 03 tests, the full backend suite, `python -m alembic current`, `python -m alembic heads`, `python -m alembic check`, and `pip check`.

Run from `frontend`: focused Module 03 tests, `npm.cmd run lint`, and `npm.cmd run build`. Run `git diff --check` from the repository root.

Before release, confirm that the browser uses `http://localhost:8010`, no request uses the legacy API port, Ollama is local-only, and no private document or secret is staged.

The registry/template checkpoint also verifies `tests.test_module03_proposal`, the registry-focused supervisor request tests, all frontend tests, and role-specific registry privacy. Browser verification of the new Coordinator/Admin surfaces remains pending when no browser surface is available.
=======
Documentation audit on 23 October 2026: read `D:/FYP Project/long proposal.pdf`, section 9.3, PDF page 10; inspected the repository's proposal/template source, tests, decisions and existing tracker/workflow. The existing [template-reference tests](../../backend/tests/test_template_references.py) test shared administrative reference behavior, not Module 3 proposal processing.

No application code, database or migrations were changed. No backend tests, browser checks, live AI or document-processing checks were run in this documentation-only pass. Requirement statuses reflect source inspection, not execution. `git diff --check` checks tracked diffs only and does not include newly untracked Module 3 files; those files were separately checked for whitespace.

Recovery audit: `backend/.venv/Scripts/python.exe -m unittest tests.test_proposal_foundation` passed 4 isolated tests (SQLite schema constraints and absence of proposal routes). No database migration, browser, live AI, or document-processing check was performed.
>>>>>>> c3b9ee80fadf2c13df694c08620da65daf55cb12
