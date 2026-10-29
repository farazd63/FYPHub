# Verification

Run from `backend`: focused Module 03 tests, the full backend suite, `python -m alembic current`, `python -m alembic heads`, `python -m alembic check`, and `pip check`.

Run from `frontend`: focused Module 03 tests, `npm.cmd run lint`, and `npm.cmd run build`. Run `git diff --check` from the repository root.

Before release, confirm that the browser uses `http://localhost:8010`, no request uses the legacy API port, Ollama is local-only, and no private document or secret is staged.
