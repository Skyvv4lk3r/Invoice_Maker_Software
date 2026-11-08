"""Initial draft and audit storage. No issued invoice or numbering tables yet."""

import sqlalchemy as sa
from alembic import op

revision = "0001_drafts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice_draft",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("invoice_date", sa.String(10), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_draft_revision_positive"),
    )
    op.create_index("ix_invoice_draft_invoice_date", "invoice_draft", ["invoice_date"])
    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_audit_event_draft_id", "audit_event", ["draft_id"])


def downgrade():
    raise RuntimeError(
        "Destructive downgrade is intentionally unavailable; restore a verified backup."
    )
