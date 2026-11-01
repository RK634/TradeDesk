"""Organization-scoped trade documents, immutable versions, requirements, and verification history.

The related entity is polymorphic because documents may belong to either side of trade
(import/export orders and shipments). Every API path resolves the target by both ID and
organization before reading or mutating this table.
"""
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer,
    String, UniqueConstraint, Uuid, func, true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


RELATED_ENTITY_TYPES = frozenset({"import_order", "import_shipment", "export_order", "export_shipment"})
DOCUMENT_TYPES = frozenset({
    "commercial_invoice", "packing_list", "bill_of_lading", "air_waybill",
    "certificate_of_origin", "insurance_certificate", "customs_declaration",
    "inspection_certificate", "product_certificate", "import_permit", "export_permit",
    "purchase_order", "sales_order", "other",
})


class TradeDocument(Base):
    __tablename__ = "trade_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_reference", name="uq_trade_documents_org_reference"),
        UniqueConstraint("id", "organization_id", name="uq_trade_documents_id_org"),
        CheckConstraint("related_entity_type IN ('import_order', 'import_shipment', 'export_order', 'export_shipment')", name="ck_trade_document_entity_type"),
        CheckConstraint("verification_status IN ('pending', 'verified', 'rejected')", name="ck_trade_document_verification_status"),
        CheckConstraint("current_version > 0", name="ck_trade_document_current_version_positive"),
        Index("ix_trade_documents_org_entity", "organization_id", "related_entity_type", "related_entity_id"),
        Index("ix_trade_documents_org_status", "organization_id", "verification_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    related_entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    related_entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    verification_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    uploaded_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    verified_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class TradeDocumentVersion(Base):
    __tablename__ = "trade_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_trade_document_version_number"),
        ForeignKeyConstraint(["document_id", "organization_id"], ["trade_documents.id", "trade_documents.organization_id"], ondelete="CASCADE", name="fk_trade_document_version_document_org"),
        UniqueConstraint("storage_key", name="uq_trade_document_version_storage_key"),
        CheckConstraint("version_number > 0", name="ck_trade_document_version_positive"),
        CheckConstraint("file_size > 0", name="ck_trade_document_version_size_positive"),
        Index("ix_trade_document_versions_document", "organization_id", "document_id", "version_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentVerificationEvent(Base):
    __tablename__ = "document_verification_events"
    __table_args__ = (
        ForeignKeyConstraint(["document_id", "organization_id"], ["trade_documents.id", "trade_documents.organization_id"], ondelete="CASCADE", name="fk_document_verification_event_document_org"),
        CheckConstraint("version_number > 0", name="ck_document_verification_event_version_positive"),
        CheckConstraint("from_status IN ('pending', 'verified', 'rejected') AND to_status IN ('pending', 'verified', 'rejected')", name="ck_document_verification_event_status"),
        Index("ix_document_verification_events_document", "organization_id", "document_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str] = mapped_column(String(16), nullable=False)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentRequirement(Base):
    __tablename__ = "document_requirements"
    __table_args__ = (
        UniqueConstraint("organization_id", "related_entity_type", "related_entity_id", "document_type", name="uq_document_requirement_entity_type"),
        CheckConstraint("related_entity_type IN ('import_order', 'import_shipment', 'export_order', 'export_shipment')", name="ck_document_requirement_entity_type"),
        Index("ix_document_requirements_entity", "organization_id", "related_entity_type", "related_entity_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    related_entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    related_entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
