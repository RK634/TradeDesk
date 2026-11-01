"""Inventory balances and immutable ledger movements."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint("organization_id", "product_id", "location_id", name="uq_inventory_balance_org_product_location"),
        CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_balance_on_hand_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_balance_reserved_nonnegative"),
        CheckConstraint("reserved_quantity <= quantity_on_hand", name="ck_inventory_balance_reserved_within_stock"),
        ForeignKeyConstraint(["product_id", "organization_id"], ["products.id", "products.organization_id"], ondelete="CASCADE", name="fk_inventory_balance_product_org"),
        ForeignKeyConstraint(["location_id", "organization_id"], ["inventory_locations.id", "inventory_locations.organization_id"], ondelete="CASCADE", name="fk_inventory_balance_location_org"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_inventory_movement_org_idempotency"),
        Index("ix_inventory_movements_org_created", "organization_id", "created_at"),
        Index("ix_inventory_movements_org_product", "organization_id", "product_id"),
        ForeignKeyConstraint(["product_id", "organization_id"], ["products.id", "products.organization_id"], ondelete="RESTRICT", name="fk_inventory_movement_product_org"),
        ForeignKeyConstraint(["location_id", "organization_id"], ["inventory_locations.id", "inventory_locations.organization_id"], ondelete="RESTRICT", name="fk_inventory_movement_location_org"),
        CheckConstraint("quantity_delta != 0 OR reserved_delta != 0", name="ck_inventory_movement_nonzero"),
        CheckConstraint(
            "movement_type IN ('goods_received', 'goods_dispatched', 'reservation', 'reservation_release', 'adjustment_increase', 'adjustment_decrease', 'return')",
            name="ck_inventory_movement_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    reserved_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    quantity_on_hand_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reserved_quantity_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
