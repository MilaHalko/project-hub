from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from project_hub.db.base import Base


class ShareModel(Base):
    __tablename__ = "project_shares"
    __table_args__ = (
        CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254", name="ck_project_shares_email_length"
        ),
        CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name="ck_project_shares_token_hash_format"
        ),
        UniqueConstraint("project_id", "email", name="uq_project_shares_project_id_email"),
        UniqueConstraint("token_hash", name="uq_project_shares_token_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", name="fk_project_shares_project_id_projects", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
