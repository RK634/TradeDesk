"""Financial records: invoices, payments, allocations, and immutable audit events."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    JSON, Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number", name="uq_invoices_org_number"),
        UniqueConstraint("id", "organization_id", name="uq_invoices_id_org"),
        ForeignKeyConstraint(["supplier_id", "organization_id"], ["suppliers.id", "suppliers.organization_id"], ondelete="RESTRICT", name="fk_invoice_supplier_org"),
        ForeignKeyConstraint(["customer_id", "organization_id"], ["customers.id", "customers.organization_id"], ondelete="RESTRICT", name="fk_invoice_customer_org"),
        ForeignKeyConstraint(["import_order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="RESTRICT", name="fk_invoice_import_order_org"),
        ForeignKeyConstraint(["export_order_id", "organization_id"], ["export_orders.id", "export_orders.organization_id"], ondelete="RESTRICT", name="fk_invoice_export_order_org"),
        CheckConstraint("invoice_type IN ('supplier', 'customer')", name="ck_invoice_type"),
        CheckConstraint("status IN ('draft', 'issued', 'partially_paid', 'paid', 'void')", name="ck_invoice_status"),
        CheckConstraint("(invoice_type = 'supplier' AND supplier_id IS NOT NULL AND customer_id IS NULL AND export_order_id IS NULL) OR (invoice_type = 'customer' AND customer_id IS NOT NULL AND supplier_id IS NULL AND import_order_id IS NULL)", name="ck_invoice_partner_type"),
        CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND discount_amount >= 0 AND total_amount >= 0", name="ck_invoice_amounts_nonnegative"),
        CheckConstraint("discount_amount <= subtotal + tax_amount", name="ck_invoice_discount_within_total"),
        Index("ix_invoices_org_status_due", "organization_id", "status", "due_date"),
        Index("ix_invoices_org_issue_date", "organization_id", "issue_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_type: Mapped[str] = mapped_column(String(16), nullable=False)
    supplier_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    import_order_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    export_order_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    notes: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    issued_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        ForeignKeyConstraint(["invoice_id", "organization_id"], ["invoices.id", "invoices.organization_id"], ondelete="CASCADE", name="fk_invoice_item_invoice_org"),
        UniqueConstraint("invoice_id", "line_number", name="uq_invoice_item_line"),
        CheckConstraint("line_number > 0", name="ck_invoice_item_line_positive"),
        CheckConstraint("quantity > 0 AND unit_price >= 0", name="ck_invoice_item_quantity_price"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_invoice_item_tax_rate"),
        CheckConstraint("net_amount >= 0 AND tax_amount >= 0 AND line_total >= 0", name="ck_invoice_item_amounts_nonnegative"),
        Index("ix_invoice_items_org_invoice", "organization_id", "invoice_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False, default=Decimal("0"), server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("organization_id", "payment_reference", name="uq_payments_org_reference"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_payments_org_idempotency"),
        UniqueConstraint("id", "organization_id", name="uq_payments_id_org"),
        CheckConstraint("payment_type IN ('incoming', 'outgoing')", name="ck_payment_type"),
        CheckConstraint("status IN ('posted', 'reversed')", name="ck_payment_status"),
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        Index("ix_payments_org_date", "organization_id", "payment_date"),
        Index("ix_payments_org_status", "organization_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(24), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="posted", server_default="posted")
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reversed_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        ForeignKeyConstraint(["payment_id", "organization_id"], ["payments.id", "payments.organization_id"], ondelete="RESTRICT", name="fk_payment_allocation_payment_org"),
        ForeignKeyConstraint(["invoice_id", "organization_id"], ["invoices.id", "invoices.organization_id"], ondelete="RESTRICT", name="fk_payment_allocation_invoice_org"),
        UniqueConstraint("payment_id", "invoice_id", name="uq_payment_allocation_invoice"),
        CheckConstraint("allocated_payment_amount > 0 AND allocated_invoice_amount > 0", name="ck_payment_allocation_amounts_positive"),
        CheckConstraint("exchange_rate > 0", name="ck_payment_allocation_exchange_rate_positive"),
        Index("ix_payment_allocations_org_invoice", "organization_id", "invoice_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    invoice_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    allocated_payment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    allocated_invoice_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"), server_default="1")
    exchange_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FinancialAuditEvent(Base):
    __tablename__ = "financial_audit_events"
    __table_args__ = (
        CheckConstraint("entity_type IN ('invoice', 'payment')", name="ck_financial_audit_entity_type"),
        Index("ix_financial_audit_org_entity", "organization_id", "entity_type", "entity_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
