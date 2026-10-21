"""Add non-operational workflow policy drafts."""
from alembic import op
import sqlalchemy as sa
revision = "e5f6a7b8c9d0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("workflow_policies", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("workflow_policy_versions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("policy_id", sa.Integer(), sa.ForeignKey("workflow_policies.id", ondelete="RESTRICT"), nullable=False), sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("states", sa.JSON(), nullable=False), sa.Column("transitions", sa.JSON(), nullable=False), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("policy_id", "version_number", name="uq_workflow_policy_version"))

def downgrade():
    op.drop_table("workflow_policy_versions")
    op.drop_table("workflow_policies")
