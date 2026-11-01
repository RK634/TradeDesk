"""Export orders, stock-backed shipments, deliveries, and audit history."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExportOrder(Base):
    __tablename__ = "export_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "reference", name="uq_export_orders_org_reference"),
        UniqueConstraint("id", "organization_id", name="uq_export_orders_id_org"),
        ForeignKeyConstraint(["customer_id", "organization_id"], ["customers.id", "customers.organization_id"], ondelete="RESTRICT", name="fk_export_order_customer_org"),
        ForeignKeyConstraint(["inventory_location_id", "organization_id"], ["inventory_locations.id", "inventory_locations.organization_id"], ondelete="RESTRICT", name="fk_export_order_location_org"),
        CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'partially_dispatched', 'dispatched', 'partially_delivered', 'delivered', 'cancelled')", name="ck_export_order_status"),
        Index("ix_export_orders_org_status", "organization_id", "status"),
        Index("ix_export_orders_org_created", "organization_id", "created_at"),
        Index("ix_export_orders_org_archived", "organization_id", "archived_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    inventory_location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    destination_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    shipping_terms: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    requested_ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    assigned_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
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


class ExportOrderItem(Base):
    __tablename__ = "export_order_items"
    __table_args__ = (
        ForeignKeyConstraint(["order_id", "organization_id"], ["export_orders.id", "export_orders.organization_id"], ondelete="CASCADE", name="fk_export_order_item_order_org"),
        ForeignKeyConstraint(["product_id", "organization_id"], ["products.id", "products.organization_id"], ondelete="RESTRICT", name="fk_export_order_item_product_org"),
        UniqueConstraint("id", "order_id", "organization_id", name="uq_export_order_item_id_order_org"),
        UniqueConstraint("order_id", "line_number", name="uq_export_order_item_line"),
        CheckConstraint("line_number > 0", name="ck_export_item_line_positive"),
        CheckConstraint("quantity_ordered > 0", name="ck_export_item_quantity_positive"),
        CheckConstraint("quantity_reserved >= 0 AND quantity_dispatched >= 0 AND quantity_delivered >= 0", name="ck_export_item_quantities_nonnegative"),
        CheckConstraint("quantity_reserved + quantity_dispatched <= quantity_ordered", name="ck_export_item_reserved_dispatch_range"),
        CheckConstraint("quantity_delivered <= quantity_dispatched", name="ck_export_item_delivered_range"),
        CheckConstraint("unit_price >= 0", name="ck_export_item_price_nonnegative"),
        Index("ix_export_order_items_order", "organization_id", "order_id"),
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
    quantity_reserved: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    quantity_dispatched: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    quantity_delivered: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ExportOrderStatusHistory(Base):
    __tablename__ = "export_order_status_history"
    __table_args__ = (
        ForeignKeyConstraint(["order_id", "organization_id"], ["export_orders.id", "export_orders.organization_id"], ondelete="CASCADE", name="fk_export_status_history_order_org"),
        Index("ix_export_status_history_order", "organization_id", "order_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ExportShipment(Base):
    __tablename__ = "export_shipments"
    __table_args__ = (
        UniqueConstraint("organization_id", "shipment_reference", name="uq_export_shipments_org_reference"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_export_shipments_org_idempotency"),
        UniqueConstraint("id", "order_id", "organization_id", name="uq_export_shipments_id_order_org"),
        ForeignKeyConstraint(["order_id", "organization_id"], ["export_orders.id", "export_orders.organization_id"], ondelete="RESTRICT", name="fk_export_shipment_order_org"),
        CheckConstraint("transport_mode IN ('sea', 'air', 'road', 'rail', 'courier', 'other')", name="ck_export_shipment_transport_mode"),
        CheckConstraint("status IN ('in_transit', 'delayed', 'delivered')", name="ck_export_shipment_status"),
        Index("ix_export_shipments_order", "organization_id", "order_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    shipment_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    carrier: Mapped[str | None] = mapped_column(String(180), nullable=True)
    tracking_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    transport_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="road", server_default="road")
    origin: Mapped[str | None] = mapped_column(String(300), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_transit", server_default="in_transit")
    estimated_departure: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_departure: Mapped[date] = mapped_column(Date, nullable=False)
    estimated_arrival: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_arrival: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    delay_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ExportShipmentMilestone(Base):
    __tablename__ = "export_shipment_milestones"
    __table_args__ = (
        ForeignKeyConstraint(["shipment_id", "order_id", "organization_id"], ["export_shipments.id", "export_shipments.order_id", "export_shipments.organization_id"], ondelete="CASCADE", name="fk_export_milestone_shipment_order_org"),
        Index("ix_export_shipment_milestones_shipment", "organization_id", "shipment_id", "occurred_at"),
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


class ExportShipmentItem(Base):
    __tablename__ = "export_shipment_items"
    __table_args__ = (
        ForeignKeyConstraint(["shipment_id", "order_id", "organization_id"], ["export_shipments.id", "export_shipments.order_id", "export_shipments.organization_id"], ondelete="CASCADE", name="fk_export_shipment_item_shipment_org"),
        ForeignKeyConstraint(["order_item_id", "order_id", "organization_id"], ["export_order_items.id", "export_order_items.order_id", "export_order_items.organization_id"], ondelete="RESTRICT", name="fk_export_shipment_item_order_item_org"),
        UniqueConstraint("id", "order_id", "organization_id", name="uq_export_shipment_item_id_order_org"),
        UniqueConstraint("shipment_id", "order_item_id", name="uq_export_shipment_item_line"),
        CheckConstraint("quantity_dispatched > 0", name="ck_export_shipment_item_quantity_positive"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity_dispatched: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class ExportDelivery(Base):
    __tablename__ = "export_deliveries"
    __table_args__ = (
        UniqueConstraint("organization_id", "delivery_reference", name="uq_export_deliveries_org_reference"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_export_deliveries_org_idempotency"),
        UniqueConstraint("id", "order_id", "organization_id", name="uq_export_deliveries_id_order_org"),
        ForeignKeyConstraint(["order_id", "organization_id"], ["export_orders.id", "export_orders.organization_id"], ondelete="RESTRICT", name="fk_export_delivery_order_org"),
        ForeignKeyConstraint(["shipment_id", "order_id", "organization_id"], ["export_shipments.id", "export_shipments.order_id", "export_shipments.organization_id"], ondelete="RESTRICT", name="fk_export_delivery_shipment_org"),
        Index("ix_export_deliveries_order", "organization_id", "order_id", "delivered_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    shipment_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    delivery_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    delivered_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class ExportDeliveryItem(Base):
    __tablename__ = "export_delivery_items"
    __table_args__ = (
        ForeignKeyConstraint(["delivery_id", "order_id", "organization_id"], ["export_deliveries.id", "export_deliveries.order_id", "export_deliveries.organization_id"], ondelete="CASCADE", name="fk_export_delivery_item_delivery_org"),
        ForeignKeyConstraint(["shipment_item_id", "order_id", "organization_id"], ["export_shipment_items.id", "export_shipment_items.order_id", "export_shipment_items.organization_id"], ondelete="RESTRICT", name="fk_export_delivery_item_shipment_item_org"),
        UniqueConstraint("delivery_id", "shipment_item_id", name="uq_export_delivery_item_shipment_item"),
        CheckConstraint("quantity_delivered > 0", name="ck_export_delivery_item_quantity_positive"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    shipment_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity_delivered: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
