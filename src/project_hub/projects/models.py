from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from project_hub.db.base import Base


class ProjectModel(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="ck_projects_name_length"),
        CheckConstraint("char_length(description) <= 2000", name="ck_projects_description_length"),
        CheckConstraint("storage_used_bytes >= 0", name="ck_projects_storage_used_non_negative"),
        Index("ix_projects_owner_id", "owner_id"),
    )
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", name="fk_projects_owner_id_users", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    storage_used_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    storage_counted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProjectMemberModel(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        PrimaryKeyConstraint("project_id", "user_id", name="pk_project_members"),
        Index("ix_project_members_user_id", "user_id"),
    )
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "projects.id", name="fk_project_members_project_id_projects", ondelete="CASCADE"
        ),
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", name="fk_project_members_user_id_users", ondelete="CASCADE"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
