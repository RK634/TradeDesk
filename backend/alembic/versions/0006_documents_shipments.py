"""Add versioned cross-workflow documents and unified export shipment milestones.

Revision ID: 0006_documents_shipments
Revises: c4b14ad0e571
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_documents_shipments"
down_revision: Union[str, None] = "c4b14ad0e571"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RELATED_TYPES = "'import_order', 'import_shipment', 'export_order', 'export_shipment'"


def upgrade() -> None:
    op.add_column("export_shipments", sa.Column("delay_reason", sa.String(length=2000), nullable=True))
    op.add_column("export_shipments", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    op.create_table(
        "export_shipment_milestones",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("shipment_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_id", "order_id", "organization_id"], ["export_shipments.id", "export_shipments.order_id", "export_shipments.organization_id"], ondelete="CASCADE", name="fk_export_milestone_shipment_order_org"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_shipment_milestones_organization_id", "export_shipment_milestones", ["organization_id"])
    op.create_index("ix_export_shipment_milestones_shipment", "export_shipment_milestones", ["organization_id", "shipment_id", "occurred_at"])

    op.create_table(
        "trade_documents",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_reference", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("related_entity_type", sa.String(length=24), nullable=False),
        sa.Column("related_entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("verification_status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("verification_notes", sa.String(length=2000), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"related_entity_type IN ({RELATED_TYPES})", name="ck_trade_document_entity_type"),
        sa.CheckConstraint("verification_status IN ('pending', 'verified', 'rejected')", name="ck_trade_document_verification_status"),
        sa.CheckConstraint("current_version > 0", name="ck_trade_document_current_version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "document_reference", name="uq_trade_documents_org_reference"),
        sa.UniqueConstraint("id", "organization_id", name="uq_trade_documents_id_org"),
    )
    op.create_index("ix_trade_documents_organization_id", "trade_documents", ["organization_id"])
    op.create_index("ix_trade_documents_org_entity", "trade_documents", ["organization_id", "related_entity_type", "related_entity_id"])
    op.create_index("ix_trade_documents_org_status", "trade_documents", ["organization_id", "verification_status"])

    op.create_table(
        "trade_document_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_number > 0", name="ck_trade_document_version_positive"),
        sa.CheckConstraint("file_size > 0", name="ck_trade_document_version_size_positive"),
        sa.ForeignKeyConstraint(["document_id", "organization_id"], ["trade_documents.id", "trade_documents.organization_id"], ondelete="CASCADE", name="fk_trade_document_version_document_org"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_trade_document_version_number"),
        sa.UniqueConstraint("storage_key", name="uq_trade_document_version_storage_key"),
    )
    op.create_index("ix_trade_document_versions_organization_id", "trade_document_versions", ["organization_id"])
    op.create_index("ix_trade_document_versions_document", "trade_document_versions", ["organization_id", "document_id", "version_number"])

    op.create_table(
        "document_verification_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=False),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_number > 0", name="ck_document_verification_event_version_positive"),
        sa.CheckConstraint("from_status IN ('pending', 'verified', 'rejected') AND to_status IN ('pending', 'verified', 'rejected')", name="ck_document_verification_event_status"),
        sa.ForeignKeyConstraint(["document_id", "organization_id"], ["trade_documents.id", "trade_documents.organization_id"], ondelete="CASCADE", name="fk_document_verification_event_document_org"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_verification_events_organization_id", "document_verification_events", ["organization_id"])
    op.create_index("ix_document_verification_events_document", "document_verification_events", ["organization_id", "document_id", "created_at"])

    op.create_table(
        "document_requirements",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("related_entity_type", sa.String(length=24), nullable=False),
        sa.Column("related_entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"related_entity_type IN ({RELATED_TYPES})", name="ck_document_requirement_entity_type"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "related_entity_type", "related_entity_id", "document_type", name="uq_document_requirement_entity_type"),
    )
    op.create_index("ix_document_requirements_organization_id", "document_requirements", ["organization_id"])
    op.create_index("ix_document_requirements_entity", "document_requirements", ["organization_id", "related_entity_type", "related_entity_id"])


def downgrade() -> None:
    op.drop_index("ix_document_requirements_entity", table_name="document_requirements")
    op.drop_index("ix_document_requirements_organization_id", table_name="document_requirements")
    op.drop_table("document_requirements")
    op.drop_index("ix_document_verification_events_document", table_name="document_verification_events")
    op.drop_index("ix_document_verification_events_organization_id", table_name="document_verification_events")
    op.drop_table("document_verification_events")
    op.drop_index("ix_trade_document_versions_document", table_name="trade_document_versions")
    op.drop_index("ix_trade_document_versions_organization_id", table_name="trade_document_versions")
    op.drop_table("trade_document_versions")
    op.drop_index("ix_trade_documents_org_status", table_name="trade_documents")
    op.drop_index("ix_trade_documents_org_entity", table_name="trade_documents")
    op.drop_index("ix_trade_documents_organization_id", table_name="trade_documents")
    op.drop_table("trade_documents")
    op.drop_index("ix_export_shipment_milestones_shipment", table_name="export_shipment_milestones")
    op.drop_index("ix_export_shipment_milestones_organization_id", table_name="export_shipment_milestones")
    op.drop_table("export_shipment_milestones")
    op.drop_column("export_shipments", "updated_at")
    op.drop_column("export_shipments", "delay_reason")
