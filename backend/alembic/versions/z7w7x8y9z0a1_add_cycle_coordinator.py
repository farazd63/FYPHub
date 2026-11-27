"""Add one cycle-scoped coordinator assignment per user."""

from alembic import op
import sqlalchemy as sa


revision = "z7w7x8y9z0a1"
down_revision = "z7v6w7x8y9z0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("academic_cycles", sa.Column("coordinator_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_academic_cycles_coordinator_id_users",
        "academic_cycles",
        "users",
        ["coordinator_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_academic_cycles_coordinator_id",
        "academic_cycles",
        ["coordinator_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_academic_cycles_coordinator_id", table_name="academic_cycles")
    op.drop_constraint("fk_academic_cycles_coordinator_id_users", "academic_cycles", type_="foreignkey")
    op.drop_column("academic_cycles", "coordinator_id")
