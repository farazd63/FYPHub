from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine

app = FastAPI(title="FYPHub API")


@app.get("/health")
def health() -> dict[str, str]:
    """Report application liveness only; this does not check database connectivity."""
    return {"status": "ok", "service": "fyphub-p1-api"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    """Report readiness only when the database and vector extension are available."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            vector_version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "service": "fyphub-p1-api"},
        ) from error

    if vector_version is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "service": "fyphub-p1-api"},
        )

    return {"status": "ready", "service": "fyphub-p1-api"}
