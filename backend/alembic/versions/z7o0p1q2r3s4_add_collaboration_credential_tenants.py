"""Add the institution tenant key to collaboration credential records."""

from alembic import op
import sqlalchemy as sa


revision = "z7o0p1q2r3s4"
down_revision = "z7n9o0p1q2r3"
branch_labels = None
depends_on = None


TABLES = (
    "collaboration_member_credentials",
    "collaboration_member_sessions",
    "collaboration_password_reset_requests",
)


def upgrade() -> None:
    for table_name in TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "institution_id",
                sa.Integer(),
                sa.ForeignKey("institutions.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table_name}_institution_id", table_name, ["institution_id"])


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_index(f"ix_{table_name}_institution_id", table_name=table_name)
        op.drop_column(table_name, "institution_id")
