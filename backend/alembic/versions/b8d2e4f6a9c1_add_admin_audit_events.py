"""add append-only administrator audit events

Revision ID: b8d2e4f6a9c1
Revises: f7a1c3d9e2b4
Create Date: 2026-10-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8d2e4f6a9c1"
down_revision: Union[str, Sequence[str], None] = "f7a1c3d9e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("affected_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("changed_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["affected_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_events_affected_user_id", "admin_audit_events", ["affected_user_id"])
    op.create_index("ix_admin_audit_events_created_at", "admin_audit_events", ["created_at"])
    op.execute("""
        CREATE FUNCTION prevent_admin_audit_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'admin_audit_events are append-only';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_admin_audit_events_append_only
        BEFORE UPDATE OR DELETE ON admin_audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_admin_audit_event_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_admin_audit_events_append_only ON admin_audit_events")
    op.execute("DROP FUNCTION prevent_admin_audit_event_mutation()")
    op.drop_index("ix_admin_audit_events_created_at", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_affected_user_id", table_name="admin_audit_events")
    op.drop_table("admin_audit_events")
