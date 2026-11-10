"""Join existing histories; add proposal lifecycle and membership consent only.

Existing application data and all historical tables are preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m123a001"
down_revision = ("c3d4e5f6a7b8", "fh7c8d9e0f1a")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("evaluation_rubric_criteria", sa.Column("max_score", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("evaluation_rubric_criteria", sa.Column("weight", sa.Float(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_rubric_criterion_max_score", "evaluation_rubric_criteria", "max_score BETWEEN 1 AND 1000")
    op.create_check_constraint("ck_rubric_criterion_weight", "evaluation_rubric_criteria", "weight > 0 AND weight <= 100")
    op.create_table("m03_proposal_records", sa.Column("id", sa.String(128), primary_key=True), sa.Column("owner_user_id", sa.String(128), nullable=False), sa.Column("proposal_type", sa.String(16), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_m03_proposal_records_owner_user_id", "m03_proposal_records", ["owner_user_id"])
    op.execute("""INSERT INTO m03_proposal_records (id, owner_user_id, proposal_type, title, created_at, updated_at)
        SELECT DISTINCT ON (proposal_id) proposal_id, owner_user_id, proposal_type, left(filename,255), created_at, created_at
        FROM m03_proposal_documents ORDER BY proposal_id, version DESC""")
    op.create_table("m03_proposal_submissions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("proposal_id", sa.String(128), nullable=False), sa.Column("document_id", sa.Integer(), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("action", sa.String(24), nullable=False), sa.Column("actor_id", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("proposal_id", "document_id", name="uq_m03_submission_document"))
    op.create_index("ix_m03_proposal_submissions_proposal_id", "m03_proposal_submissions", ["proposal_id"])
    op.create_table("m03_proposal_access", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("proposal_id", sa.String(128), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("granted_by_id", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("proposal_id", "user_id", name="uq_m03_proposal_access_user"))
    op.create_index("ix_m03_proposal_access_proposal_id", "m03_proposal_access", ["proposal_id"])
    op.create_index("ix_m03_proposal_access_user_id", "m03_proposal_access", ["user_id"])
    op.create_table("m03_proposal_change_summaries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("document_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("runtime_metadata", postgresql.JSONB(), nullable=False), sa.UniqueConstraint("document_id", name="uq_m03_change_summary_document"))
    op.create_table("team_member_verifications", sa.Column("member_id", sa.Integer(), primary_key=True), sa.Column("code_hash", sa.String(255)), sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("sent_at", sa.DateTime(timezone=True)), sa.Column("verified_at", sa.DateTime(timezone=True)), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("window_started_at", sa.DateTime(timezone=True)), sa.Column("requests", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_table("team_member_verifications")
    op.drop_table("m03_proposal_change_summaries")
    op.drop_table("m03_proposal_access")
    op.drop_table("m03_proposal_submissions")
    op.drop_table("m03_proposal_records")
    op.drop_constraint("ck_rubric_criterion_weight", "evaluation_rubric_criteria", type_="check")
    op.drop_constraint("ck_rubric_criterion_max_score", "evaluation_rubric_criteria", type_="check")
    op.drop_column("evaluation_rubric_criteria", "weight")
    op.drop_column("evaluation_rubric_criteria", "max_score")
