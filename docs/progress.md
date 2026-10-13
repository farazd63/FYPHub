# Project Progress

## Verified setup

- Project directory created.
- Eight project folders created.
- Git initialized on `main`; no commits yet.
- Python 3.12.10
- Node v24.20.0
- npm 11.19.0
- Git 2.55.0.windows.5
- Docker 29.7.2
- Docker Compose v5.5.1

## Current target

P1 Mid, Modules 1–3.

## Implementation status

All module features are not yet implemented.

## Checkpoint 2A

The isolated PostgreSQL + pgvector configuration was created.

## Checkpoint 2B

- Dedicated database container started successfully and its current health is `healthy`.
- Database: `fyphub_p1`.
- Database user: `fyphub_p1_user`.
- Local binding: `127.0.0.1:55732`.
- SQL connection verification passed.
- The `vector` extension was verified at version `0.8.6`.

## Checkpoint 3B

- Minimal FastAPI backend foundation created using `backend/.venv`.
- `GET /health` provides application liveness only and does not claim database connectivity.
- Default Swagger documentation remains available at `/docs`.
- Backend liveness and Swagger/OpenAPI verification passed:
  - `GET /health` returned HTTP 200 with `{"status":"ok","service":"fyphub-p1-api"}`.
  - `GET /docs` returned HTTP 200.
  - `GET /openapi.json` returned HTTP 200, confirmed title `FYPHub API`, and confirmed `GET /health` registration.
- This verification does not verify or claim database connectivity.

## Checkpoint 4A

- Added the PostgreSQL connection foundation using synchronous SQLAlchemy and `postgresql+psycopg`.
- Root `.env` is loaded with an explicit path; its existing password is reused and remains private.
- `GET /health` remains liveness only and does not access the database.
- Added `GET /health/ready`, which verifies `SELECT 1` and the installed `vector` extension, returning a sanitized HTTP 503 response if either check fails.
- Python compilation and dependency integrity checks passed.
- A read-only database check confirmed `fyphub_p1` and `vector` extension version `0.8.6`.
- Runtime endpoint verification passed: `/health` and `/health/ready` both returned HTTP 200.
- An isolated mocked database-failure ASGI request returned the expected sanitized HTTP 503 response; no Docker service or credentials were changed.

## Checkpoint 4B

- Added Alembic migration infrastructure under `backend/alembic` and `backend/alembic.ini`.
- Added the shared SQLAlchemy `Base` and exposed its metadata to Alembic for future models.
- Alembic reuses the application database configuration without storing credentials in `alembic.ini` and supports online and offline modes.
- Python compilation and dependency integrity checks passed.
- Alembic `heads`, `history`, and `current` were verified with no revisions present.
- Database inspection found no public application tables and no `alembic_version` infrastructure table was created.
- Running `/health` and `/health/ready` checks both returned HTTP 200 after the infrastructure changes.

## Checkpoint 5A

- Added the `users` and `user_role` database foundation through Alembic revision `9c227dc337bf`.
- Database rules enforce canonical normalized email and registration-number storage, case-insensitive email uniqueness, registration-number uniqueness when present, valid roles, and required student registration numbers.
- The migration contains no pgvector extension changes and pgvector remains at version `0.8.6`.
- Alembic current matches head; a second autogenerate check found no pending changes.
- Users schema columns, constraints, and indexes were verified. No accounts have been created.
- Running `/health` and `/health/ready` checks both returned HTTP 200 after the migration.
- Authentication, password hashing, account creation, and frontend work remain unimplemented.

## Deadline

Before the 6th; month and year are not yet confirmed.
