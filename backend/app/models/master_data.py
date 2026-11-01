"""Organization-scoped master data models for trading partners, products, and locations."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "customer_code", name="uq_customers_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_customers_id_org"),
        Index("ix_customers_org_name", "organization_id", "name"),
        CheckConstraint("payment_terms_days >= 0", name="ck_customers_payment_terms_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("organization_id", "supplier_code", name="uq_suppliers_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_suppliers_id_org"),
        Index("ix_suppliers_org_name", "organization_id", "name"),
        CheckConstraint("payment_terms_days >= 0", name="ck_suppliers_payment_terms_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku", name="uq_products_org_sku"),
        UniqueConstraint("id", "organization_id", name="uq_products_id_org"),
        Index("ix_products_org_name", "organization_id", "name"),
        CheckConstraint("purchase_price >= 0", name="ck_products_purchase_price_nonnegative"),
        CheckConstraint("selling_price >= 0", name="ck_products_selling_price_nonnegative"),
        CheckConstraint("reorder_threshold >= 0", name="ck_products_reorder_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(24), nullable=False, default="pcs", server_default="pcs")
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    selling_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    reorder_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_inventory_locations_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_inventory_locations_id_org"),
        Index("ix_inventory_locations_org_name", "organization_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
