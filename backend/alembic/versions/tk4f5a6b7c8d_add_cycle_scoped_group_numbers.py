"""Add stable group numbers scoped to each academic cycle."""

from alembic import op
import sqlalchemy as sa


revision = "tk4f5a6b7c8d"
down_revision = "sj3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("teams", sa.Column("group_number", sa.Integer(), nullable=True))
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE teams AS target
        SET group_number = numbered.group_number
        FROM (
            SELECT id, row_number() OVER (PARTITION BY academic_cycle_id ORDER BY created_at, id) AS group_number
            FROM teams
        ) AS numbered
        WHERE target.id = numbered.id
    """))
    op.create_unique_constraint("uq_teams_cycle_group_number", "teams", ["academic_cycle_id", "group_number"])
    op.create_check_constraint("ck_teams_group_number_positive", "teams", "group_number IS NULL OR group_number > 0")


def downgrade():
    op.drop_constraint("ck_teams_group_number_positive", "teams", type_="check")
    op.drop_constraint("uq_teams_cycle_group_number", "teams", type_="unique")
    op.drop_column("teams", "group_number")
