"""make document version content optional for persistent file storage

Revision ID: jk4d5e6f7a8b
Revises: hn3c4d5e6f7a
"""
from alembic import op
import sqlalchemy as sa
revision = "jk4d5e6f7a8b"
down_revision = "hn3c4d5e6f7a"
branch_labels = None
depends_on = None
def upgrade():
    op.alter_column("document_submission_versions", "content", existing_type=sa.LargeBinary(), nullable=True)
def downgrade():
    op.alter_column("document_submission_versions", "content", existing_type=sa.LargeBinary(), nullable=False)
