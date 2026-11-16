"""allow jpg and png documents

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def upgrade() -> None:
    op.drop_constraint("ck_documents_content_type", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_content_type",
        "documents",
        f"content_type IN ('application/pdf', '{_DOCX}', 'image/jpeg', 'image/png')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_content_type", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_content_type",
        "documents",
        f"content_type IN ('application/pdf', '{_DOCX}')",
    )
