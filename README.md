# FYPHub

FYPHub is a final-year-project platform being established in small, verifiable implementation checkpoints.

## Agreed technology stack

- Frontend: React, Vite, TypeScript, and Tailwind CSS
- Backend: Python 3.12 and FastAPI
- Data: PostgreSQL with pgvector
- Development environment: Docker Compose

## Repository layout

- `ai/` — AI-related services, experiments, and supporting assets.
- `backend/` — FastAPI application and backend services.
- `database/` — database schema, migrations, and database configuration.
- `docs/` — project documentation, decisions, progress records, and diagrams.
- `frontend/` — React/Vite web application.
- `sample-data/` — safe example data for development and testing.
- `scripts/` — project automation and utility scripts.
- `tests/` — cross-project and integration tests.

## Status

The isolated PostgreSQL + pgvector configuration has been verified. The FastAPI backend now has two health endpoints: `/health` is application liveness only and does not access the database, while `/health/ready` verifies database connectivity and the pgvector extension. Both endpoints have been runtime-verified for the local P1 environment. Alembic now manages the initial users-and-roles database foundation; authentication implementation has not started.
