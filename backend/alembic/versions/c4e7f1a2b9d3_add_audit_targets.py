"""add explicit audit targets

Revision ID: c4e7f1a2b9d3
Revises: b8d2e4f6a9c1
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c4e7f1a2b9d3"
down_revision: Union[str, Sequence[str], None] = "b8d2e4f6a9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.alter_column("admin_audit_events", "affected_user_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("admin_audit_events", sa.Column("target_type", sa.String(length=32), server_default="USER", nullable=False))
    op.add_column("admin_audit_events", sa.Column("target_id", sa.Integer(), nullable=True))
    op.execute("UPDATE admin_audit_events SET target_id = affected_user_id WHERE target_id IS NULL")
    op.alter_column("admin_audit_events", "target_id", nullable=False)

def downgrade() -> None:
    op.drop_column("admin_audit_events", "target_id")
    op.drop_column("admin_audit_events", "target_type")
    op.alter_column("admin_audit_events", "affected_user_id", existing_type=sa.Integer(), nullable=False)
