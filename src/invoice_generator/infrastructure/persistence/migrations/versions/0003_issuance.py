"""Atomic numbering, immutable issued snapshots, cancellation state and render outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0003_issuance"
down_revision = "0002_workspace"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice_counter",
        sa.Column("financial_year", sa.Integer(), primary_key=True),
        sa.Column("next_number", sa.Integer(), nullable=False),
    )
    op.create_table(
        "issued_invoice",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("financial_year", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("invoice_date", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("financial_year", "number", name="uq_fiscal_invoice_number"),
    )
    op.create_table(
        "render_job",
        sa.Column("invoice_id", sa.String(36), primary_key=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("artifact_name", sa.Text(), nullable=False),
    )
    op.create_index("ix_issued_date", "issued_invoice", ["invoice_date"])


def downgrade():
    raise RuntimeError("Issued records must never be deleted by a schema downgrade.")
