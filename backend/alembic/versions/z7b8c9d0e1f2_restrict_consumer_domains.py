"""Keep legacy consumer-email accounts while blocking consumer domains for signup."""

from alembic import op


revision = "z7b8c9d0e1f2"
down_revision = ("z7a8b9c0d1e2",)
branch_labels = None
depends_on = None


CONSUMER_DOMAINS = ("gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com")


def upgrade() -> None:
    op.create_index("ix_announcements_institution_id", "announcements", ["institution_id"])
    domains_sql = ", ".join(f"'{domain}'" for domain in CONSUMER_DOMAINS)
    op.execute(
        "UPDATE institution_domains SET is_active = FALSE, is_verified = FALSE, "
        f"disabled_at = COALESCE(disabled_at, NOW()) WHERE domain IN ({domains_sql})"
    )


def downgrade() -> None:
    domains_sql = ", ".join(f"'{domain}'" for domain in CONSUMER_DOMAINS)
    op.execute(
        "UPDATE institution_domains SET is_active = TRUE, is_verified = TRUE, "
        f"disabled_at = NULL, verified_at = COALESCE(verified_at, NOW()) WHERE domain IN ({domains_sql})"
    )
    op.drop_index("ix_announcements_institution_id", table_name="announcements")
