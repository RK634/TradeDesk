"""Add invoices, payments, payment allocations, and financial audit history.

Revision ID: 0007_financials
Revises: 0006_documents_shipments
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_financials"
down_revision: Union[str, None] = "0006_documents_shipments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Required for organization-scoped composite references from financial records.
    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.create_unique_constraint("uq_suppliers_id_org", ["id", "organization_id"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("invoice_type", sa.String(length=16), nullable=False),
        sa.Column("supplier_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("customer_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("import_order_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("export_order_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.String(length=3000), nullable=True),
        sa.Column("issued_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("invoice_type IN ('supplier', 'customer')", name="ck_invoice_type"),
        sa.CheckConstraint("status IN ('draft', 'issued', 'partially_paid', 'paid', 'void')", name="ck_invoice_status"),
        sa.CheckConstraint("(invoice_type = 'supplier' AND supplier_id IS NOT NULL AND customer_id IS NULL AND export_order_id IS NULL) OR (invoice_type = 'customer' AND customer_id IS NOT NULL AND supplier_id IS NULL AND import_order_id IS NULL)", name="ck_invoice_partner_type"),
        sa.CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND discount_amount >= 0 AND total_amount >= 0", name="ck_invoice_amounts_nonnegative"),
        sa.CheckConstraint("discount_amount <= subtotal + tax_amount", name="ck_invoice_discount_within_total"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id", "organization_id"], ["suppliers.id", "suppliers.organization_id"], ondelete="RESTRICT", name="fk_invoice_supplier_org"),
        sa.ForeignKeyConstraint(["customer_id", "organization_id"], ["customers.id", "customers.organization_id"], ondelete="RESTRICT", name="fk_invoice_customer_org"),
        sa.ForeignKeyConstraint(["import_order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="RESTRICT", name="fk_invoice_import_order_org"),
        sa.ForeignKeyConstraint(["export_order_id", "organization_id"], ["export_orders.id", "export_orders.organization_id"], ondelete="RESTRICT", name="fk_invoice_export_order_org"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "invoice_number", name="uq_invoices_org_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_invoices_id_org"),
    )
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
    op.create_index("ix_invoices_org_status_due", "invoices", ["organization_id", "status", "due_date"])
    op.create_index("ix_invoices_org_issue_date", "invoices", ["organization_id", "issue_date"])

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("invoice_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("tax_rate", sa.Numeric(9, 4), server_default="0", nullable=False),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("line_number > 0", name="ck_invoice_item_line_positive"),
        sa.CheckConstraint("quantity > 0 AND unit_price >= 0", name="ck_invoice_item_quantity_price"),
        sa.CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_invoice_item_tax_rate"),
        sa.CheckConstraint("net_amount >= 0 AND tax_amount >= 0 AND line_total >= 0", name="ck_invoice_item_amounts_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id", "organization_id"], ["invoices.id", "invoices.organization_id"], ondelete="CASCADE", name="fk_invoice_item_invoice_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id", "line_number", name="uq_invoice_item_line"),
    )
    op.create_index("ix_invoice_items_organization_id", "invoice_items", ["organization_id"])
    op.create_index("ix_invoice_items_org_invoice", "invoice_items", ["organization_id", "invoice_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("payment_reference", sa.String(length=64), nullable=False),
        sa.Column("payment_type", sa.String(length=16), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=24), nullable=False),
        sa.Column("external_reference", sa.String(length=160), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="posted", nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("reversed_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("payment_type IN ('incoming', 'outgoing')", name="ck_payment_type"),
        sa.CheckConstraint("status IN ('posted', 'reversed')", name="ck_payment_status"),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "payment_reference", name="uq_payments_org_reference"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_payments_org_idempotency"),
        sa.UniqueConstraint("id", "organization_id", name="uq_payments_id_org"),
    )
    op.create_index("ix_payments_organization_id", "payments", ["organization_id"])
    op.create_index("ix_payments_org_date", "payments", ["organization_id", "payment_date"])
    op.create_index("ix_payments_org_status", "payments", ["organization_id", "status"])

    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("payment_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("invoice_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("allocated_payment_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("allocated_invoice_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(18, 8), server_default="1", nullable=False),
        sa.Column("exchange_rate_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("allocated_payment_amount > 0 AND allocated_invoice_amount > 0", name="ck_payment_allocation_amounts_positive"),
        sa.CheckConstraint("exchange_rate > 0", name="ck_payment_allocation_exchange_rate_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id", "organization_id"], ["payments.id", "payments.organization_id"], ondelete="RESTRICT", name="fk_payment_allocation_payment_org"),
        sa.ForeignKeyConstraint(["invoice_id", "organization_id"], ["invoices.id", "invoices.organization_id"], ondelete="RESTRICT", name="fk_payment_allocation_invoice_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", "invoice_id", name="uq_payment_allocation_invoice"),
    )
    op.create_index("ix_payment_allocations_organization_id", "payment_allocations", ["organization_id"])
    op.create_index("ix_payment_allocations_org_invoice", "payment_allocations", ["organization_id", "invoice_id"])

    op.create_table(
        "financial_audit_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("entity_type IN ('invoice', 'payment')", name="ck_financial_audit_entity_type"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_audit_events_organization_id", "financial_audit_events", ["organization_id"])
    op.create_index("ix_financial_audit_org_entity", "financial_audit_events", ["organization_id", "entity_type", "entity_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_financial_audit_org_entity", table_name="financial_audit_events")
    op.drop_index("ix_financial_audit_events_organization_id", table_name="financial_audit_events")
    op.drop_table("financial_audit_events")
    op.drop_index("ix_payment_allocations_org_invoice", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_organization_id", table_name="payment_allocations")
    op.drop_table("payment_allocations")
    op.drop_index("ix_payments_org_status", table_name="payments")
    op.drop_index("ix_payments_org_date", table_name="payments")
    op.drop_index("ix_payments_organization_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_invoice_items_org_invoice", table_name="invoice_items")
    op.drop_index("ix_invoice_items_organization_id", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_index("ix_invoices_org_issue_date", table_name="invoices")
    op.drop_index("ix_invoices_org_status_due", table_name="invoices")
    op.drop_index("ix_invoices_organization_id", table_name="invoices")
    op.drop_table("invoices")
    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.drop_constraint("uq_suppliers_id_org", type_="unique")
