# FYPHub

FYPHub is a final-year-project platform built with React/Vite, FastAPI, PostgreSQL, and pgvector.

## Technology stack

- Frontend: React 19, Vite 8, TypeScript 6, and Tailwind CSS 4
- Backend: Python 3.12 and FastAPI
- Data: PostgreSQL 17 with pgvector 0.8.6
- Migrations: Alembic
- Local AI: Ollama

## Repository layout

- `backend/` — FastAPI application, SQLAlchemy models, migrations, tests, and Docker build files.
- `database/` — PostgreSQL initialization SQL.
- `docs/` — project documentation and workflow records.
- `frontend/` — React/Vite application and Docker build files.
- `scripts/` — administrative and development seed scripts.
- `modules/` — feature documentation.

## Docker Desktop setup

Docker Desktop with the WSL 2 backend is recommended on Windows. The default Compose stack starts:

- PostgreSQL with pgvector
- an Alembic migration job
- the FastAPI backend
- Ollama with a persistent model volume
- the React production build served by Nginx

Redis and Celery are not included because the application does not currently use them.

### Computer 1 or Computer 2

1. Clone or copy the repository.
2. Create the local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Edit `.env` and set a unique `POSTGRES_PASSWORD`. Keep `.env` private; it is ignored by Git.
4. Build the images:

   ```powershell
   docker compose -f docker-compose.yml build
   ```

5. Start the application:

   ```powershell
   docker compose -f docker-compose.yml up -d
   ```

6. Check the services:

   ```powershell
   docker compose -f docker-compose.yml ps
   Invoke-WebRequest http://localhost:8010/health
   Invoke-WebRequest http://localhost:8010/health/ready
   ```

Open the frontend at <http://localhost:5173>.

The first startup may take several minutes because Ollama downloads the configured models. Model files are stored in the `fyphub-p1-ollama-models` named volume.

### Stop and restart

Stop containers without deleting data:

```powershell
docker compose -f docker-compose.yml stop
```

Restart them:

```powershell
docker compose -f docker-compose.yml up -d
```

`docker compose down` also preserves named volumes. Do not use `docker compose down -v`; that deletes the database, uploaded files, and downloaded Ollama models.

### Persistent data

The Compose stack uses these named volumes:

- `fyphub-p1-postgres-data` — PostgreSQL records.
- `fyphub-p1-document-data` — uploaded documents and team files.
- `fyphub-p1-ollama-models` — downloaded AI models.

PostgreSQL is bound only to `127.0.0.1:55732` for compatibility with the existing local Python backend and test commands; it is not exposed to the LAN. The Docker backend uses the internal `db:5432` address. Use `docker compose -f docker-compose.yml exec db psql ...` for administrative access.

### Useful diagnostics

```powershell
docker compose -f docker-compose.yml logs --tail=200 db
docker compose -f docker-compose.yml logs --tail=200 migrate
docker compose -f docker-compose.yml logs --tail=200 backend
docker compose -f docker-compose.yml logs --tail=200 ollama
docker compose -f docker-compose.yml logs --tail=200 frontend
```

If the migration service fails, inspect its logs before retrying. If the backend is unhealthy, verify PostgreSQL readiness and confirm that the named database volume belongs to this project. If Ollama fails, check available memory and model-download connectivity.

### GPU support for Ollama

The default configuration is CPU-compatible and does not reserve a GPU. NVIDIA GPU acceleration requires Docker Desktop GPU support, WSL 2 integration, compatible NVIDIA drivers, and a Compose override that adds a GPU device reservation. The Ollama model volume remains the same.

### Backing up application data

Back up PostgreSQL before moving data to another computer:

```powershell
docker compose -f docker-compose.yml exec -T db pg_dump -U fyphub_p1_user -d fyphub_p1 > fyphub-p1.sql
```

The uploaded-files volume and Ollama model volume are separate from the SQL dump and must be backed up separately if they need to move with the database.

## Local non-Docker development

The existing direct development commands remain available. The backend entry point is `app.main:app`; the frontend entry point is `frontend/src/main.tsx`.
