"""Add multiple role assignments per user."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "z7z5a6b7c8d9"
down_revision = "z7z4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    role_enum = postgresql.ENUM(name="user_role", create_type=False)
    op.create_table(
        "user_role_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role", name="uq_user_role_assignments_user_role"),
    )
    op.create_index("ix_user_role_assignments_user_id", "user_role_assignments", ["user_id"], unique=False)
    op.execute(
        sa.text(
            "INSERT INTO user_role_assignments (institution_id, user_id, role) "
            "SELECT institution_id, id, role FROM users "
            "ON CONFLICT (user_id, role) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO user_role_assignments (institution_id, user_id, role) "
            "SELECT u.institution_id, u.id, 'COORDINATOR'::user_role "
            "FROM users u "
            "JOIN academic_cycles c ON c.coordinator_id = u.id "
            "ON CONFLICT (user_id, role) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_user_role_assignments_user_id", table_name="user_role_assignments")
    op.drop_table("user_role_assignments")
