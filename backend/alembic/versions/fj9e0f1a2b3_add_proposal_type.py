"""Store the selected SHORT/LONG type on supervisor-request proposals."""

from alembic import op
import sqlalchemy as sa

revision = "fj9e0f1a2b3"
down_revision = "fi8d9e0f1a2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supervisor_requests", sa.Column("proposal_type", sa.String(5), nullable=False, server_default="SHORT"))
    op.create_check_constraint("ck_supervisor_requests_proposal_type", "supervisor_requests", "proposal_type IN ('SHORT','LONG')")


def downgrade() -> None:
    op.drop_constraint("ck_supervisor_requests_proposal_type", "supervisor_requests", type_="check")
    op.drop_column("supervisor_requests", "proposal_type")
