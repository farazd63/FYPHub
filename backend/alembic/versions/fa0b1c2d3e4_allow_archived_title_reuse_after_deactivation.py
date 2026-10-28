"""allow archived title reuse after deactivation"""

from alembic import op
import sqlalchemy as sa


revision = "fa0b1c2d3e4"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("uq_archived_project_title_year", "archived_projects", type_="unique")
    op.create_index("uq_archived_project_active_title_year", "archived_projects", ["normalized_title", "academic_year"], unique=True, postgresql_where=sa.text("is_active = true"))


def downgrade():
    op.drop_index("uq_archived_project_active_title_year", table_name="archived_projects")
    op.create_unique_constraint("uq_archived_project_title_year", "archived_projects", ["normalized_title", "academic_year"])
