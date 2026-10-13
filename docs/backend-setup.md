# Backend Setup

## Virtual environment

The backend uses the existing project-local virtual environment at `backend/.venv`. Install and run backend dependencies only through `backend/.venv/Scripts/python.exe`; do not use a global Python installation or another project's environment.

## Dependencies

Install the pinned dependencies from the project root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pip install -r .\backend\requirements.txt
```

## Startup

When runtime verification is authorized, start the API from the project root with:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010 --reload
```

## Endpoints

- `GET /health` is an application-liveness endpoint. It returns `{"status": "ok", "service": "fyphub-p1-api"}` and does not check database connectivity.
- `GET /health/ready` is a database-readiness endpoint. It verifies a `SELECT 1` connection and the installed `vector` extension. It returns HTTP 503 with a sanitized unavailable response if either check fails.
- `/docs` provides FastAPI's default interactive Swagger documentation.

## Database connection

The backend loads the ignored root `.env` using an explicit path. `POSTGRES_PASSWORD` remains only in that file. Non-secret connection settings are documented in `.env.example`; local defaults target the isolated FYPHub database. The SQLAlchemy connection URL is constructed with `URL.create`, so special characters in the password are handled safely and never written to logs or documentation.

The synchronous SQLAlchemy engine uses `postgresql+psycopg`, connection pre-ping, bounded pool and connection timeouts, and a statement timeout. Database connections are used in context managers so they close correctly. This checkpoint does not create tables or run migrations.

## Status

Backend liveness, Swagger/OpenAPI, and readiness verification passed using read-only local HTTP requests:

- `GET http://127.0.0.1:8010/health` returned HTTP 200 with `{"status":"ok","service":"fyphub-p1-api"}`.
- `GET http://127.0.0.1:8010/docs` returned HTTP 200.
- `GET http://127.0.0.1:8010/openapi.json` returned HTTP 200, confirmed title `FYPHub API`, and confirmed that `GET /health` is registered.
- `GET http://127.0.0.1:8010/health/ready` returned HTTP 200 with the ready status after verifying database connectivity and the `vector` extension.

The direct read-only database check confirmed database `fyphub_p1` and `vector` extension version `0.8.6`. An isolated mocked database-failure ASGI request also returned the expected sanitized HTTP 503 response without exposing the simulated error.

`/health` remains a liveness-only check and does not verify or claim database connectivity. Database verification is performed only by `/health/ready`.
