"""Alembic environment using the FYPHub application database configuration."""

import sys
from pathlib import Path

from alembic import context

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.database import Base, engine  # noqa: E402
from app.models import AcademicCycle, AcademicGroupPolicy, User  # noqa: F401, E402

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""
    context.configure(
        url=engine.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with the shared synchronous application engine."""
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
