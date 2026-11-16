"""add projects storage used

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("storage_used_bytes", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column("projects", sa.Column("storage_counted_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_projects_storage_used_non_negative", "projects", "storage_used_bytes >= 0"
    )
    op.execute(
        "UPDATE projects p SET "
        "storage_used_bytes = COALESCE("
        "(SELECT SUM(d.size) FROM documents d WHERE d.project_id = p.id), 0), "
        "storage_counted_at = now()"
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_storage_used_non_negative", "projects", type_="check")
    op.drop_column("projects", "storage_counted_at")
    op.drop_column("projects", "storage_used_bytes")
