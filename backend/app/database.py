"""Synchronous SQLAlchemy database resources."""

from sqlalchemy import create_engine
from collections.abc import Generator

from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Shared declarative base for future application models."""

    pass

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=2,
    pool_timeout=5,
    connect_args={
        "connect_timeout": 5,
        "options": "-c statement_timeout=5000",
    },
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """Provide a request-scoped session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
