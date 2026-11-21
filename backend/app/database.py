"""Synchronous SQLAlchemy database resources and tenant query guards."""

from sqlalchemy import ForeignKey, create_engine, event
from collections.abc import Generator

from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker, with_loader_criteria

from .config import settings


class Base(DeclarativeBase):
    """Shared base for university-owned records.

    Keeping the tenant key on the common base means every existing and future
    application record gets the same isolation primitive without relying on a
    developer remembering to add it to each model.
    """

    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class ControlPlaneBase(DeclarativeBase):
    """Base for the cross-tenant institution control plane."""

    metadata = Base.metadata


TENANT_FILTER_EXEMPT_TABLES = {
    "institutions",
    "institution_domains",
    "institution_memberships",
    "institution_invitations",
    "email_verification_tokens",
}


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(execute_state) -> None:
    """Apply a tenant predicate to every ORM read in an authenticated scope.

    Platform administrators deliberately run without a tenant predicate so
    they can inspect all institutions. Control-plane tables are handled by
    their explicit service authorization and are never accidentally hidden by
    the data-plane tenant filter.
    """

    if execute_state.is_column_load or execute_state.is_relationship_load:
        return
    session = execute_state.session
    institution_id = session.info.get("institution_id")
    if institution_id is None or session.info.get("platform_admin"):
        return

    # ORM/Core UPDATE and DELETE statements executed through Session are also
    # tenant scoped. This closes the write-side gap that loader criteria alone
    # cannot cover.
    if execute_state.is_update or execute_state.is_delete:
        table = getattr(execute_state.statement, "table", None)
        if table is not None and table.name not in TENANT_FILTER_EXEMPT_TABLES and "institution_id" in table.c:
            execute_state.statement = execute_state.statement.where(table.c.institution_id == institution_id)
        return

    if not execute_state.is_select:
        return

    statement = execute_state.statement
    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if table.name in TENANT_FILTER_EXEMPT_TABLES or "institution_id" not in table.c:
            continue
        model = mapper.class_
        tenant_id = institution_id
        statement = statement.options(
            with_loader_criteria(
                model,
                lambda cls: cls.institution_id == tenant_id,
                include_aliases=True,
            )
        )
    execute_state.statement = statement


@event.listens_for(Session, "before_flush")
def _assign_new_records_to_tenant(session: Session, _flush_context, _instances) -> None:
    """Stamp new data-plane records with the authenticated tenant."""

    institution_id = session.info.get("institution_id")
    if institution_id is None:
        return
    for record in session.new:
        table = getattr(record, "__table__", None)
        if table is None or table.name in TENANT_FILTER_EXEMPT_TABLES or "institution_id" not in table.c:
            continue
        if getattr(record, "institution_id", None) is None:
            record.institution_id = institution_id

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
