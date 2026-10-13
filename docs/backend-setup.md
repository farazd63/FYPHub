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
- `/docs` provides FastAPI's default interactive Swagger documentation.

## Status

Backend liveness and Swagger/OpenAPI verification passed using read-only local HTTP requests:

- `GET http://127.0.0.1:8010/health` returned HTTP 200 with `{"status":"ok","service":"fyphub-p1-api"}`.
- `GET http://127.0.0.1:8010/docs` returned HTTP 200.
- `GET http://127.0.0.1:8010/openapi.json` returned HTTP 200, confirmed title `FYPHub API`, and confirmed that `GET /health` is registered.

These checks verify application liveness, Swagger, and OpenAPI registration only. They do not verify or claim database connectivity.
