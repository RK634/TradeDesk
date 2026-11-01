"""Import orders, approvals, shipments, receipts, and private order documents."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImportOrder(Base):
    __tablename__ = "import_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "reference", name="uq_import_orders_org_reference"),
        UniqueConstraint("id", "organization_id", name="uq_import_orders_id_org"),
        ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT", name="fk_import_order_supplier"),
        CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'partially_received', 'received', 'cancelled')", name="ck_import_order_status"),
        CheckConstraint("estimated_freight_cost >= 0 AND estimated_insurance_cost >= 0 AND estimated_duties >= 0 AND estimated_other_costs >= 0", name="ck_import_order_estimated_costs_nonnegative"),
        CheckConstraint("actual_freight_cost >= 0 AND actual_insurance_cost >= 0 AND actual_duties >= 0 AND actual_other_costs >= 0", name="ck_import_order_actual_costs_nonnegative"),
        Index("ix_import_orders_org_status", "organization_id", "status"),
        Index("ix_import_orders_org_created", "organization_id", "created_at"),
        Index("ix_import_orders_org_archived", "organization_id", "archived_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(36), nullable=False)
    supplier_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    purchase_terms: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(2), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(300), nullable=True)
    estimated_departure_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_departure_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_freight_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    estimated_insurance_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    estimated_duties: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    estimated_other_costs: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    actual_freight_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    actual_insurance_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    actual_duties: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    actual_other_costs: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    assigned_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ImportOrderItem(Base):
    __tablename__ = "import_order_items"
    __table_args__ = (
        UniqueConstraint("id", "order_id", "organization_id", name="uq_import_order_items_id_order_org"),
        ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_order_item_order_org"),
        ForeignKeyConstraint(["product_id", "organization_id"], ["products.id", "products.organization_id"], ondelete="RESTRICT", name="fk_import_order_item_product_org"),
        CheckConstraint("line_number > 0", name="ck_import_order_item_line_number_positive"),
        CheckConstraint("quantity_ordered > 0", name="ck_import_order_item_quantity_positive"),
        CheckConstraint("quantity_received >= 0 AND quantity_received <= quantity_ordered", name="ck_import_order_item_received_range"),
        CheckConstraint("unit_price >= 0", name="ck_import_order_item_price_nonnegative"),
        UniqueConstraint("order_id", "line_number", name="uq_import_order_item_line"),
        Index("ix_import_order_items_order", "organization_id", "order_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ImportOrderStatusHistory(Base):
    __tablename__ = "import_order_status_history"
    __table_args__ = (
        ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_status_history_order_org"),
        Index("ix_import_status_history_order", "organization_id", "order_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ImportShipment(Base):
    __tablename__ = "import_shipments"
    __table_args__ = (
        UniqueConstraint("organization_id", "shipment_reference", name="uq_import_shipments_org_reference"),
        UniqueConstraint("id", "order_id", "organization_id", name="uq_import_shipments_id_order_org"),
        ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_shipment_order_org"),
        CheckConstraint("transport_mode IN ('sea', 'air', 'road', 'rail', 'courier', 'other')", name="ck_import_shipment_transport_mode"),
        CheckConstraint("status IN ('planned', 'in_transit', 'arrived', 'delayed', 'delivered', 'cancelled')", name="ck_import_shipment_status"),
        Index("ix_import_shipments_order", "organization_id", "order_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    shipment_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    carrier: Mapped[str | None] = mapped_column(String(180), nullable=True)
    tracking_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    transport_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="sea", server_default="sea")
    origin: Mapped[str | None] = mapped_column(String(300), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(300), nullable=True)
    estimated_departure: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_departure: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_arrival: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_arrival: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="planned", server_default="planned")
    delay_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ImportShipmentMilestone(Base):
    __tablename__ = "import_shipment_milestones"
    __table_args__ = (
        ForeignKeyConstraint(["shipment_id", "order_id", "organization_id"], ["import_shipments.id", "import_shipments.order_id", "import_shipments.organization_id"], ondelete="CASCADE", name="fk_import_milestone_shipment_order_org"),
        Index("ix_import_shipment_milestones_shipment", "organization_id", "shipment_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    shipment_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ImportGoodsReceipt(Base):
    __tablename__ = "import_goods_receipts"
    __table_args__ = (
        UniqueConstraint("organization_id", "receipt_reference", name="uq_import_goods_receipts_org_reference"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_import_goods_receipts_org_idempotency"),
        UniqueConstraint("id", "order_id", "organization_id", name="uq_import_goods_receipts_id_order_org"),
        ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="RESTRICT", name="fk_import_receipt_order_org"),
        ForeignKeyConstraint(["location_id", "organization_id"], ["inventory_locations.id", "inventory_locations.organization_id"], ondelete="RESTRICT", name="fk_import_receipt_location_org"),
        Index("ix_import_goods_receipts_order", "organization_id", "order_id", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    receipt_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    received_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class ImportGoodsReceiptItem(Base):
    __tablename__ = "import_goods_receipt_items"
    __table_args__ = (
        ForeignKeyConstraint(["receipt_id", "order_id", "organization_id"], ["import_goods_receipts.id", "import_goods_receipts.order_id", "import_goods_receipts.organization_id"], ondelete="CASCADE", name="fk_import_receipt_item_receipt_order_org"),
        ForeignKeyConstraint(["order_item_id", "order_id", "organization_id"], ["import_order_items.id", "import_order_items.order_id", "import_order_items.organization_id"], ondelete="RESTRICT", name="fk_import_receipt_item_order_item_org"),
        UniqueConstraint("receipt_id", "order_item_id", name="uq_import_receipt_item_receipt_order_item"),
        CheckConstraint("quantity_received > 0", name="ck_import_receipt_item_quantity_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class ImportDocument(Base):
    __tablename__ = "import_documents"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_import_documents_storage_key"),
        ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_document_order_org"),
        CheckConstraint("verification_status IN ('pending', 'verified', 'rejected')", name="ck_import_document_verification_status"),
        CheckConstraint("file_size > 0", name="ck_import_document_file_size_positive"),
        Index("ix_import_documents_order", "organization_id", "order_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    verification_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    verified_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
