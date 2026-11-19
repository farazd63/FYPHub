"""Add year/session identity to supervisor capacity policies.

Existing cycle links are retained for historical compatibility.  New policy
writes identify a policy by supervisor, academic year, and session.
"""

from alembic import op
import sqlalchemy as sa


revision = "p567a001"
down_revision = "n456a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("supervisor_capacity_policies")}
    # Existing cycle links stay; academic_cycle_id may already be nullable.
    if "academic_cycle_id" in columns:
        op.alter_column("supervisor_capacity_policies", "academic_cycle_id", existing_type=sa.Integer(), nullable=True)
    if "academic_year" not in columns:
        op.add_column("supervisor_capacity_policies", sa.Column("academic_year", sa.Integer(), nullable=True))
    if "session" not in columns:
        op.add_column("supervisor_capacity_policies", sa.Column("session", sa.String(length=16), nullable=True))

    # Prefer the normalized cycle fields.  Older rows are best-effort migrated
    # from the legacy cycle label/code without deleting any capacity data.
    op.execute(
        """
        UPDATE supervisor_capacity_policies AS policy
        SET academic_year = cycle.academic_year,
            session = cycle.session
        FROM academic_cycles AS cycle
        WHERE policy.academic_cycle_id = cycle.id
        """
    )
    op.execute(
        """
        UPDATE supervisor_capacity_policies AS policy
        SET academic_year = CASE
                WHEN upper(coalesce(cycle.display_name, '') || ' ' || coalesce(cycle.code, '')) ~ '(19|20|21|22)[0-9]{2}'
                THEN substring(upper(coalesce(cycle.display_name, '') || ' ' || coalesce(cycle.code, '')) from '((19|20|21|22)[0-9]{2})')::integer
                ELSE NULL
            END,
            session = CASE
                WHEN upper(coalesce(cycle.display_name, '') || ' ' || coalesce(cycle.code, '')) LIKE '%SPRING%' THEN 'SPRING'
                WHEN upper(coalesce(cycle.display_name, '') || ' ' || coalesce(cycle.code, '')) LIKE '%FALL%' THEN 'FALL'
                ELSE NULL
            END
        FROM academic_cycles AS cycle
        WHERE policy.academic_cycle_id = cycle.id
          AND (policy.academic_year IS NULL OR policy.session IS NULL)
        """
    )
    checks = {item["name"] for item in inspector.get_check_constraints("supervisor_capacity_policies") if item.get("name")}
    # Re-read after alters
    inspector = sa.inspect(op.get_bind())
    checks = {item["name"] for item in inspector.get_check_constraints("supervisor_capacity_policies") if item.get("name")}
    if "ck_supervisor_capacity_policies_year_valid" not in checks:
        op.create_check_constraint(
            "ck_supervisor_capacity_policies_year_valid",
            "supervisor_capacity_policies",
            "academic_year IS NULL OR academic_year BETWEEN 1900 AND 2200",
        )
    if "ck_supervisor_capacity_policies_session_valid" not in checks:
        op.create_check_constraint(
            "ck_supervisor_capacity_policies_session_valid",
            "supervisor_capacity_policies",
            "session IS NULL OR session IN ('FALL','SPRING')",
        )
    indexes = {index["name"] for index in inspector.get_indexes("supervisor_capacity_policies")}
    if "uq_supervisor_capacity_policies_supervisor_period" not in indexes:
        op.create_index(
            "uq_supervisor_capacity_policies_supervisor_period",
            "supervisor_capacity_policies",
            ["supervisor_id", "academic_year", "session"],
            unique=True,
            postgresql_where=sa.text("academic_year IS NOT NULL AND session IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("uq_supervisor_capacity_policies_supervisor_period", table_name="supervisor_capacity_policies")
    op.drop_constraint("ck_supervisor_capacity_policies_session_valid", "supervisor_capacity_policies", type_="check")
    op.drop_constraint("ck_supervisor_capacity_policies_year_valid", "supervisor_capacity_policies", type_="check")
    op.drop_column("supervisor_capacity_policies", "session")
    op.drop_column("supervisor_capacity_policies", "academic_year")
