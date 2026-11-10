"""Add editable proposal metadata snapshots to the existing lifecycle records."""

from alembic import op
import sqlalchemy as sa

revision = "fk0f1a2b3c4"
down_revision = "fj9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("problem_statement", "objectives", "scope", "methodology"):
        op.add_column("supervisor_requests", sa.Column(name, sa.Text(), nullable=True))


def downgrade() -> None:
    for name in ("methodology", "scope", "objectives", "problem_statement"):
        op.drop_column("supervisor_requests", name)
