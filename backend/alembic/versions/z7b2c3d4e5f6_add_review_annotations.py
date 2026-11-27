"""Add persistent Module 6 PDF review annotations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "z7b2c3d4e5f6"
down_revision = "z7a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "proposal_review_annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("annotation_type", sa.String(length=32), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("geometry", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("drawing", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("suggested_text", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#F5C542"),
        sa.Column("stroke_width", sa.Float(), nullable=False, server_default="2"),
        sa.Column("publication_status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("feedback_id", sa.Integer(), nullable=True),
        sa.Column("revision_request_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["feedback_id"], ["proposal_review_feedback.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revision_request_id"], ["proposal_revision_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_proposal_review_annotations_submission_page", "proposal_review_annotations", ["submission_id", "page_number"])
    op.create_index("ix_proposal_review_annotations_team_status", "proposal_review_annotations", ["team_id", "publication_status"])
    op.create_index("ix_proposal_review_annotations_institution_id", "proposal_review_annotations", ["institution_id"])


def downgrade() -> None:
    op.drop_index("ix_proposal_review_annotations_institution_id", table_name="proposal_review_annotations")
    op.drop_index("ix_proposal_review_annotations_team_status", table_name="proposal_review_annotations")
    op.drop_index("ix_proposal_review_annotations_submission_page", table_name="proposal_review_annotations")
    op.drop_table("proposal_review_annotations")
