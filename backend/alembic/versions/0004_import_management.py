"""Add import orders, approval history, shipments, receipts, and private documents.

Revision ID: 0004_import_management
Revises: 0003_master_data_inventory
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_import_management"
down_revision: Union[str, None] = "0003_master_data_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "import_orders",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("reference", sa.String(36), nullable=False),
        sa.Column("supplier_id", UUID, nullable=False),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("currency", sa.String(3), server_default="EUR", nullable=False),
        sa.Column("purchase_terms", sa.String(120), nullable=True),
        sa.Column("country_of_origin", sa.String(2), nullable=True),
        sa.Column("destination", sa.String(300), nullable=True),
        sa.Column("estimated_departure_date", sa.Date(), nullable=True),
        sa.Column("estimated_arrival_date", sa.Date(), nullable=True),
        sa.Column("actual_departure_date", sa.Date(), nullable=True),
        sa.Column("actual_arrival_date", sa.Date(), nullable=True),
        sa.Column("estimated_freight_cost", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("estimated_insurance_cost", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("estimated_duties", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("estimated_other_costs", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("actual_freight_cost", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("actual_insurance_cost", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("actual_duties", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("actual_other_costs", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("assigned_user_id", UUID, nullable=True),
        sa.Column("notes", sa.String(3000), nullable=True),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", UUID, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'partially_received', 'received', 'cancelled')", name="ck_import_order_status"),
        sa.CheckConstraint("estimated_freight_cost >= 0 AND estimated_insurance_cost >= 0 AND estimated_duties >= 0 AND estimated_other_costs >= 0", name="ck_import_order_estimated_costs_nonnegative"),
        sa.CheckConstraint("actual_freight_cost >= 0 AND actual_insurance_cost >= 0 AND actual_duties >= 0 AND actual_other_costs >= 0", name="ck_import_order_actual_costs_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT", name="fk_import_order_supplier"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "reference", name="uq_import_orders_org_reference"),
        sa.UniqueConstraint("id", "organization_id", name="uq_import_orders_id_org"),
    )
    op.create_index("ix_import_orders_organization_id", "import_orders", ["organization_id"])
    op.create_index("ix_import_orders_org_status", "import_orders", ["organization_id", "status"])
    op.create_index("ix_import_orders_org_created", "import_orders", ["organization_id", "created_at"])

    op.create_table(
        "import_order_items",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("product_sku_snapshot", sa.String(64), nullable=False),
        sa.Column("product_name_snapshot", sa.String(180), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("quantity_ordered", sa.Numeric(18, 4), nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("line_number > 0", name="ck_import_order_item_line_number_positive"),
        sa.CheckConstraint("quantity_ordered > 0", name="ck_import_order_item_quantity_positive"),
        sa.CheckConstraint("quantity_received >= 0 AND quantity_received <= quantity_ordered", name="ck_import_order_item_received_range"),
        sa.CheckConstraint("unit_price >= 0", name="ck_import_order_item_price_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_order_item_order_org"),
        sa.ForeignKeyConstraint(["product_id", "organization_id"], ["products.id", "products.organization_id"], ondelete="RESTRICT", name="fk_import_order_item_product_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "order_id", "organization_id", name="uq_import_order_items_id_order_org"),
        sa.UniqueConstraint("order_id", "line_number", name="uq_import_order_item_line"),
    )
    op.create_index("ix_import_order_items_organization_id", "import_order_items", ["organization_id"])
    op.create_index("ix_import_order_items_order", "import_order_items", ["organization_id", "order_id"])

    op.create_table(
        "import_order_status_history",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=True),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_status_history_order_org"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_order_status_history_organization_id", "import_order_status_history", ["organization_id"])
    op.create_index("ix_import_status_history_order", "import_order_status_history", ["organization_id", "order_id", "created_at"])

    op.create_table(
        "import_shipments",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("shipment_reference", sa.String(64), nullable=False),
        sa.Column("carrier", sa.String(180), nullable=True),
        sa.Column("tracking_reference", sa.String(180), nullable=True),
        sa.Column("transport_mode", sa.String(16), server_default="sea", nullable=False),
        sa.Column("origin", sa.String(300), nullable=True),
        sa.Column("destination", sa.String(300), nullable=True),
        sa.Column("estimated_departure", sa.Date(), nullable=True),
        sa.Column("actual_departure", sa.Date(), nullable=True),
        sa.Column("estimated_arrival", sa.Date(), nullable=True),
        sa.Column("actual_arrival", sa.Date(), nullable=True),
        sa.Column("status", sa.String(24), server_default="planned", nullable=False),
        sa.Column("delay_reason", sa.String(2000), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("transport_mode IN ('sea', 'air', 'road', 'rail', 'courier', 'other')", name="ck_import_shipment_transport_mode"),
        sa.CheckConstraint("status IN ('planned', 'in_transit', 'arrived', 'delayed', 'delivered', 'cancelled')", name="ck_import_shipment_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_shipment_order_org"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "shipment_reference", name="uq_import_shipments_org_reference"),
        sa.UniqueConstraint("id", "order_id", "organization_id", name="uq_import_shipments_id_order_org"),
    )
    op.create_index("ix_import_shipments_organization_id", "import_shipments", ["organization_id"])
    op.create_index("ix_import_shipments_order", "import_shipments", ["organization_id", "order_id"])

    op.create_table(
        "import_shipment_milestones",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("shipment_id", UUID, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_id", "order_id", "organization_id"], ["import_shipments.id", "import_shipments.order_id", "import_shipments.organization_id"], ondelete="CASCADE", name="fk_import_milestone_shipment_order_org"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_shipment_milestones_organization_id", "import_shipment_milestones", ["organization_id"])
    op.create_index("ix_import_shipment_milestones_shipment", "import_shipment_milestones", ["organization_id", "shipment_id", "occurred_at"])

    op.create_table(
        "import_goods_receipts",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("location_id", UUID, nullable=False),
        sa.Column("receipt_reference", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("received_by_user_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="RESTRICT", name="fk_import_receipt_order_org"),
        sa.ForeignKeyConstraint(["location_id", "organization_id"], ["inventory_locations.id", "inventory_locations.organization_id"], ondelete="RESTRICT", name="fk_import_receipt_location_org"),
        sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "receipt_reference", name="uq_import_goods_receipts_org_reference"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_import_goods_receipts_org_idempotency"),
        sa.UniqueConstraint("id", "order_id", "organization_id", name="uq_import_goods_receipts_id_order_org"),
    )
    op.create_index("ix_import_goods_receipts_organization_id", "import_goods_receipts", ["organization_id"])
    op.create_index("ix_import_goods_receipts_order", "import_goods_receipts", ["organization_id", "order_id", "received_at"])

    op.create_table(
        "import_goods_receipt_items",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("receipt_id", UUID, nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("order_item_id", UUID, nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("quantity_received > 0", name="ck_import_receipt_item_quantity_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receipt_id", "order_id", "organization_id"], ["import_goods_receipts.id", "import_goods_receipts.order_id", "import_goods_receipts.organization_id"], ondelete="CASCADE", name="fk_import_receipt_item_receipt_order_org"),
        sa.ForeignKeyConstraint(["order_item_id", "order_id", "organization_id"], ["import_order_items.id", "import_order_items.order_id", "import_order_items.organization_id"], ondelete="RESTRICT", name="fk_import_receipt_item_order_item_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id", "order_item_id", name="uq_import_receipt_item_receipt_order_item"),
    )
    op.create_index("ix_import_goods_receipt_items_organization_id", "import_goods_receipt_items", ["organization_id"])

    op.create_table(
        "import_documents",
        sa.Column("id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("document_reference", sa.String(64), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("verification_status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("verification_notes", sa.String(2000), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("uploaded_by_user_id", UUID, nullable=False),
        sa.Column("verified_by_user_id", UUID, nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("verification_status IN ('pending', 'verified', 'rejected')", name="ck_import_document_verification_status"),
        sa.CheckConstraint("file_size > 0", name="ck_import_document_file_size_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id", "organization_id"], ["import_orders.id", "import_orders.organization_id"], ondelete="CASCADE", name="fk_import_document_order_org"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_import_documents_storage_key"),
    )
    op.create_index("ix_import_documents_organization_id", "import_documents", ["organization_id"])
    op.create_index("ix_import_documents_order", "import_documents", ["organization_id", "order_id", "created_at"])


def downgrade() -> None:
    op.drop_table("import_documents")
    op.drop_table("import_goods_receipt_items")
    op.drop_table("import_goods_receipts")
    op.drop_table("import_shipment_milestones")
    op.drop_table("import_shipments")
    op.drop_table("import_order_status_history")
    op.drop_table("import_order_items")
    op.drop_table("import_orders")
