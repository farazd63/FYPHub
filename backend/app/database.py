"""Synchronous SQLAlchemy database resources."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

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
