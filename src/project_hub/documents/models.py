from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from project_hub.db.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 255", name="ck_documents_name_length"),
        CheckConstraint(
            "content_type IN ('application/pdf', "
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', "
            "'image/jpeg', 'image/png')",
            name="ck_documents_content_type",
        ),
        CheckConstraint("size > 0", name="ck_documents_size_positive"),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        Index("ix_documents_project_id", "project_id"),
    )
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", name="fk_documents_project_id_projects", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", name="fk_documents_uploaded_by_users", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
