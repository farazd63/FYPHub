"""Persist the year and session selected when creating an academic cycle."""

from alembic import op
import sqlalchemy as sa


revision = "n456a001"
down_revision = "m123a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("academic_cycles", sa.Column("academic_year", sa.Integer(), nullable=True))
    op.add_column("academic_cycles", sa.Column("session", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_academic_cycles_year_valid",
        "academic_cycles",
        "academic_year IS NULL OR academic_year BETWEEN 1900 AND 2200",
    )
    op.create_check_constraint(
        "ck_academic_cycles_session_valid",
        "academic_cycles",
        "session IS NULL OR session IN ('FALL','SPRING')",
    )
    op.create_index(
        "uq_academic_cycles_year_session",
        "academic_cycles",
        ["academic_year", "session"],
        unique=True,
        postgresql_where=sa.text("academic_year IS NOT NULL AND session IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_academic_cycles_year_session", table_name="academic_cycles")
    op.drop_constraint("ck_academic_cycles_session_valid", "academic_cycles", type_="check")
    op.drop_constraint("ck_academic_cycles_year_valid", "academic_cycles", type_="check")
    op.drop_column("academic_cycles", "session")
    op.drop_column("academic_cycles", "academic_year")
