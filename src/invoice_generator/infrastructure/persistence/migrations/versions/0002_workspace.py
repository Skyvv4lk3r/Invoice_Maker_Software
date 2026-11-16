"""Owner credentials, firm/catalog records and immutable custom template versions."""

import sqlalchemy as sa
from alembic import op

revision = "0002_workspace"
down_revision = "0001_drafts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace_owner",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("recovery_hash", sa.Text(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.String(40), nullable=False),
        sa.CheckConstraint("id = 1", name="single_workspace_owner"),
    )
    op.create_table(
        "workspace_record",
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "template_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Restore a verified backup instead of deleting workspace records.")
