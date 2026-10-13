# Database Setup

## Isolation

FYPHub P1 uses an isolated PostgreSQL and pgvector configuration:

- Host binding: `127.0.0.1:55732`
- Database: `fyphub_p1`
- Database user: `fyphub_p1_user`
- Container: `fyphub-p1-db`
- Named volume: `fyphub-p1-postgres-data`
- Network: `fyphub-p1-network`

It does not use the ports, containers, database storage, or networks of older projects. The database is reachable only from this computer through the loopback interface.

## Configuration

Copy `.env.example` to `.env` if it is not already present, then set a unique, non-empty local password. Keep `.env` private; it is ignored by Git. Do not place credentials in documentation or source code.

The image is explicitly pinned to `pgvector/pgvector:0.8.6-pg17-trixie`, which uses PostgreSQL 17. Its data directory is `/var/lib/postgresql/data`.

## Startup and verification

When runtime work is authorized, start only this project's service from the repository root:

```powershell
docker compose up -d
```

Verify its health and the pgvector extension:

```powershell
docker compose ps
docker compose exec db psql -U fyphub_p1_user -d fyphub_p1 -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

## Verified runtime status (Checkpoint 2B)

The dedicated database container started successfully and its current health is `healthy`. SQL connection verification passed for database `fyphub_p1` using database user `fyphub_p1_user` through the local binding `127.0.0.1:55732`. The `vector` extension is installed and was verified at version `0.8.6`.

## Initialization behavior

`database/init/001_extensions.sql` is mounted read-only into PostgreSQL's initialization directory. It runs only when the named data volume is first initialized. It enables the `vector` extension in this FYPHub database; it does not modify any other database.
