# Verification

Run from `backend`: focused Module 03 tests, the full backend suite, `python -m alembic current`, `python -m alembic heads`, `python -m alembic check`, and `pip check`.

Run from `frontend`: focused Module 03 tests, `npm.cmd run lint`, and `npm.cmd run build`. Run `git diff --check` from the repository root.

Before release, confirm that the browser uses `http://localhost:8010`, no request uses the legacy API port, Ollama is local-only, and no private document or secret is staged.

The registry/template checkpoint also verifies `tests.test_module03_proposal`, the registry-focused supervisor request tests, all frontend tests, and role-specific registry privacy. Browser verification of the new Coordinator/Admin surfaces remains pending when no browser surface is available.
