"""Restrict portal access and signup to the SZABIST institution."""

from alembic import op


revision = "z7e1f2a3b4c5d"
down_revision = ("z7d0e1f2a3b4",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep all existing records, but make the one configured institutional
    # domain the only active entry point for this single-university deployment.
    op.execute(
        """
        DO $$
        DECLARE primary_institution_id INTEGER;
        BEGIN
            SELECT institution_id INTO primary_institution_id
            FROM institution_domains
            WHERE domain = 'szabist-isb.pk'
            LIMIT 1;

            IF primary_institution_id IS NULL THEN
                INSERT INTO institutions (slug, name, status)
                VALUES ('szabist', 'SZABIST', 'ACTIVE')
                ON CONFLICT (slug) DO UPDATE SET name = 'SZABIST', status = 'ACTIVE'
                RETURNING id INTO primary_institution_id;

                INSERT INTO institution_domains
                    (institution_id, domain, is_verified, is_active, verified_at)
                VALUES (primary_institution_id, 'szabist-isb.pk', TRUE, TRUE, NOW())
                ON CONFLICT (domain) DO NOTHING;
            END IF;

            UPDATE institutions
            SET name = CASE WHEN id = primary_institution_id THEN 'SZABIST' ELSE name END,
                status = CASE WHEN id = primary_institution_id THEN 'ACTIVE' ELSE 'DISABLED' END;

            UPDATE institution_domains
            SET is_verified = (domain = 'szabist-isb.pk'),
                is_active = (domain = 'szabist-isb.pk'),
                disabled_at = CASE WHEN domain = 'szabist-isb.pk' THEN NULL ELSE COALESCE(disabled_at, NOW()) END;
        END $$;
        """
    )


def downgrade() -> None:
    # Historical tenant records remain intact. Re-enabling them is deliberately
    # not automatic; a future multi-tenant rollout must verify each domain.
    pass
