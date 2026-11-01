"""Add organization-scoped master data and inventory ledger.

Revision ID: 0003_master_data_inventory
Revises: 0002_auth_organizations
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_master_data_inventory"
down_revision: Union[str, None] = "0002_auth_organizations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("customer_code", sa.String(48), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("company_name", sa.String(180), nullable=True),
        sa.Column("contact_person", sa.String(160), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("billing_address", sa.String(1000), nullable=True),
        sa.Column("delivery_address", sa.String(1000), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("tax_id", sa.String(80), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="EUR", nullable=False),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("payment_terms_days >= 0", name="ck_customers_payment_terms_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "customer_code", name="uq_customers_org_code"),
    )
    op.create_index("ix_customers_organization_id", "customers", ["organization_id"])
    op.create_index("ix_customers_org_name", "customers", ["organization_id", "name"])

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("supplier_code", sa.String(48), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("company_name", sa.String(180), nullable=True),
        sa.Column("contact_person", sa.String(160), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("address", sa.String(1000), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("tax_id", sa.String(80), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="EUR", nullable=False),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("payment_terms_days >= 0", name="ck_suppliers_payment_terms_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "supplier_code", name="uq_suppliers_org_code"),
    )
    op.create_index("ix_suppliers_organization_id", "suppliers", ["organization_id"])
    op.create_index("ix_suppliers_org_name", "suppliers", ["organization_id", "name"])

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("unit_of_measure", sa.String(24), server_default="pcs", nullable=False),
        sa.Column("purchase_price", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("selling_price", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="EUR", nullable=False),
        sa.Column("reorder_threshold", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purchase_price >= 0", name="ck_products_purchase_price_nonnegative"),
        sa.CheckConstraint("selling_price >= 0", name="ck_products_selling_price_nonnegative"),
        sa.CheckConstraint("reorder_threshold >= 0", name="ck_products_reorder_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "sku", name="uq_products_org_sku"),
        sa.UniqueConstraint("id", "organization_id", name="uq_products_id_org"),
    )
    op.create_index("ix_products_organization_id", "products", ["organization_id"])
    op.create_index("ix_products_org_name", "products", ["organization_id", "name"])

    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(48), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("address", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_inventory_locations_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inventory_locations_id_org"),
    )
    op.create_index("ix_inventory_locations_organization_id", "inventory_locations", ["organization_id"])
    op.create_index("ix_inventory_locations_org_name", "inventory_locations", ["organization_id", "name"])

    op.create_table(
        "inventory_balances",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("location_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("reserved_quantity", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_balance_on_hand_nonnegative"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_inventory_balance_reserved_nonnegative"),
        sa.CheckConstraint("reserved_quantity <= quantity_on_hand", name="ck_inventory_balance_reserved_within_stock"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id", "organization_id"], ["products.id", "products.organization_id"], ondelete="CASCADE", name="fk_inventory_balance_product_org"),
        sa.ForeignKeyConstraint(["location_id", "organization_id"], ["inventory_locations.id", "inventory_locations.organization_id"], ondelete="CASCADE", name="fk_inventory_balance_location_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "product_id", "location_id", name="uq_inventory_balance_org_product_location"),
    )
    op.create_index("ix_inventory_balances_organization_id", "inventory_balances", ["organization_id"])
    op.create_index("ix_inventory_balances_product_id", "inventory_balances", ["product_id"])
    op.create_index("ix_inventory_balances_location_id", "inventory_balances", ["location_id"])

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("location_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("movement_type", sa.String(32), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("reserved_delta", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("quantity_on_hand_after", sa.Numeric(18, 4), nullable=False),
        sa.Column("reserved_quantity_after", sa.Numeric(18, 4), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=True),
        sa.Column("source_reference", sa.String(120), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity_delta != 0 OR reserved_delta != 0", name="ck_inventory_movement_nonzero"),
        sa.CheckConstraint(
            "movement_type IN ('goods_received', 'goods_dispatched', 'reservation', 'reservation_release', 'adjustment_increase', 'adjustment_decrease', 'return')",
            name="ck_inventory_movement_type",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id", "organization_id"], ["products.id", "products.organization_id"], ondelete="RESTRICT", name="fk_inventory_movement_product_org"),
        sa.ForeignKeyConstraint(["location_id", "organization_id"], ["inventory_locations.id", "inventory_locations.organization_id"], ondelete="RESTRICT", name="fk_inventory_movement_location_org"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_inventory_movement_org_idempotency"),
    )
    op.create_index("ix_inventory_movements_organization_id", "inventory_movements", ["organization_id"])
    op.create_index("ix_inventory_movements_org_created", "inventory_movements", ["organization_id", "created_at"])
    op.create_index("ix_inventory_movements_org_product", "inventory_movements", ["organization_id", "product_id"])


def downgrade() -> None:
    op.drop_table("inventory_movements")
    op.drop_table("inventory_balances")
    op.drop_table("inventory_locations")
    op.drop_table("products")
    op.drop_table("suppliers")
    op.drop_table("customers")
