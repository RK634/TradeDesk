"""Add operational reporting indexes and soft-archive metadata/audit events.

Revision ID: 0009_reports_archive
Revises: 0008_tasks_approvals_automation
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_reports_archive"
down_revision = "0008_tasks_approvals_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("import_orders", "export_orders"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column("archived_by_user_id", sa.Uuid(as_uuid=True), nullable=True))
            batch_op.add_column(sa.Column("archive_reason", sa.String(2000), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{table}_archived_by_user", "users", ["archived_by_user_id"], ["id"], ondelete="SET NULL"
            )
    op.create_index("ix_import_orders_org_archived", "import_orders", ["organization_id", "archived_at"])
    op.create_index("ix_export_orders_org_archived", "export_orders", ["organization_id", "archived_at"])

    op.create_table(
        "archive_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_type", sa.String(24), nullable=False),
        sa.Column("record_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("record_reference", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("record_type IN ('import_order', 'export_order')", name="ck_archive_event_record_type"),
        sa.CheckConstraint("action IN ('archived', 'restored')", name="ck_archive_event_action"),
    )
    op.create_index("ix_archive_events_organization_id", "archive_events", ["organization_id"])
    op.create_index("ix_archive_events_org_record", "archive_events", ["organization_id", "record_type", "record_id", "created_at"])
    op.create_index("ix_archive_events_org_created", "archive_events", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_archive_events_org_created", table_name="archive_events")
    op.drop_index("ix_archive_events_org_record", table_name="archive_events")
    op.drop_index("ix_archive_events_organization_id", table_name="archive_events")
    op.drop_table("archive_events")
    op.drop_index("ix_export_orders_org_archived", table_name="export_orders")
    op.drop_index("ix_import_orders_org_archived", table_name="import_orders")
    for table in ("export_orders", "import_orders"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_archived_by_user", type_="foreignkey")
            batch_op.drop_column("archive_reason")
            batch_op.drop_column("archived_by_user_id")
            batch_op.drop_column("archived_at")
