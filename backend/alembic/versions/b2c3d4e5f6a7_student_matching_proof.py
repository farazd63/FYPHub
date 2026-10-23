"""Allow a distinct anonymous student matching proof."""
from alembic import op

revision = 'b2c3d4e5f6a7'
down_revision = 'a8467cad28da'
branch_labels = None
depends_on = None

def upgrade():
    for table, name in (("anonymous_verification_challenges", "ck_anon_challenge_purpose"), ("anonymous_identity_proofs", "ck_anon_proof_purpose")):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, "purpose IN ('join_request', 'invitation', 'student_matching')")

def downgrade():
    for table, name in (("anonymous_verification_challenges", "ck_anon_challenge_purpose"), ("anonymous_identity_proofs", "ck_anon_proof_purpose")):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, "purpose IN ('join_request', 'invitation')")
