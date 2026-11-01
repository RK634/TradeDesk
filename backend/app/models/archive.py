"""Immutable archive and restore audit events."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArchiveEvent(Base):
    __tablename__ = "archive_events"
    __table_args__ = (
        CheckConstraint("record_type IN ('import_order', 'export_order')", name="ck_archive_event_record_type"),
        CheckConstraint("action IN ('archived', 'restored')", name="ck_archive_event_action"),
        Index("ix_archive_events_org_record", "organization_id", "record_type", "record_id", "created_at"),
        Index("ix_archive_events_org_created", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(24), nullable=False)
    record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    record_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
