"""create project shares

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_shares",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_shares_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254", name="ck_project_shares_email_length"
        ),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name="ck_project_shares_token_hash_format"
        ),
        sa.UniqueConstraint("project_id", "email", name="uq_project_shares_project_id_email"),
        sa.UniqueConstraint("token_hash", name="uq_project_shares_token_hash"),
    )


def downgrade() -> None:
    op.drop_table("project_shares")
