"""Store roster-bound verification challenges and one-use proofs."""
from alembic import op
import sqlalchemy as sa
revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("identity_challenges", sa.Column("id", sa.Integer, primary_key=True), sa.Column("student_id", sa.Integer, sa.ForeignKey("approved_students.id", ondelete="RESTRICT"), nullable=False), sa.Column("cycle_id", sa.Integer, sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False), sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("purpose", sa.String(20), nullable=False), sa.Column("code_hash", sa.String(255), nullable=False), sa.Column("attempts", sa.Integer, server_default="0", nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)), sa.CheckConstraint("purpose IN ('join_request', 'invitation')", name="ck_identity_challenge_purpose"))
    op.create_index("ix_identity_challenges_student_id", "identity_challenges", ["student_id"])
    op.create_index("ix_identity_challenges_actor_id", "identity_challenges", ["actor_id"])
    op.create_table("identity_proofs", sa.Column("id", sa.Integer, primary_key=True), sa.Column("challenge_id", sa.Integer, sa.ForeignKey("identity_challenges.id", ondelete="RESTRICT"), unique=True, nullable=False), sa.Column("student_id", sa.Integer, sa.ForeignKey("approved_students.id", ondelete="RESTRICT"), nullable=False), sa.Column("cycle_id", sa.Integer, sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False), sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("purpose", sa.String(20), nullable=False), sa.Column("token_hash", sa.String(64), unique=True, nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)))

def downgrade():
    op.drop_table("identity_proofs")
    op.drop_index("ix_identity_challenges_actor_id", table_name="identity_challenges")
    op.drop_index("ix_identity_challenges_student_id", table_name="identity_challenges")
    op.drop_table("identity_challenges")
