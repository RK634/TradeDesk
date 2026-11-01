"""Add task management, configurable approvals, notifications, and automation logs.

Revision ID: 0008_tasks_approvals_automation
Revises: 0007_financials
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_tasks_approvals_automation"
down_revision = "0007_financials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_entity_type", sa.String(24), nullable=True),
        sa.Column("related_entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("priority", sa.String(16), server_default="normal", nullable=False),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_tasks_id_org"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_tasks_priority"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'blocked', 'completed', 'cancelled')", name="ck_tasks_status"),
        sa.CheckConstraint("related_entity_type IS NULL OR related_entity_type IN ('import_order', 'export_order', 'shipment', 'invoice', 'document')", name="ck_tasks_related_type"),
    )
    op.create_index("ix_tasks_organization_id", "tasks", ["organization_id"])
    op.create_index("ix_tasks_assigned_to_user_id", "tasks", ["assigned_to_user_id"])
    op.create_index("ix_tasks_org_status_due", "tasks", ["organization_id", "status", "due_at"])
    op.create_index("ix_tasks_org_assignee_status", "tasks", ["organization_id", "assigned_to_user_id", "status"])

    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("author_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id", "organization_id"], ["tasks.id", "tasks.organization_id"], ondelete="CASCADE", name="fk_task_comments_task_org"),
    )
    op.create_index("ix_task_comments_organization_id", "task_comments", ["organization_id"])
    op.create_index("ix_task_comments_task_created", "task_comments", ["organization_id", "task_id", "created_at"])

    op.create_table(
        "task_status_history",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("note", sa.String(2000), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id", "organization_id"], ["tasks.id", "tasks.organization_id"], ondelete="CASCADE", name="fk_task_status_history_task_org"),
    )
    op.create_index("ix_task_status_history_organization_id", "task_status_history", ["organization_id"])
    op.create_index("ix_task_status_history_task_created", "task_status_history", ["organization_id", "task_id", "created_at"])

    op.create_table(
        "approval_rules",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_action", sa.String(32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("required_roles", sa.JSON(), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("allow_self_approval", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "business_action", name="uq_approval_rules_org_action"),
        sa.CheckConstraint("business_action IN ('import_order', 'export_order', 'invoice', 'payment', 'task', 'custom')", name="ck_approval_rules_action"),
        sa.CheckConstraint("minimum_amount IS NULL OR minimum_amount >= 0", name="ck_approval_rules_minimum_amount"),
    )
    op.create_index("ix_approval_rules_organization_id", "approval_rules", ["organization_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_action", sa.String(32), nullable=False),
        sa.Column("related_entity_type", sa.String(32), nullable=False),
        sa.Column("related_entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decided_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), server_default="submitted", nullable=False),
        sa.Column("request_note", sa.String(2000), nullable=True),
        sa.Column("decision_note", sa.String(2000), nullable=True),
        sa.Column("requested_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_approval_requests_id_org"),
        sa.CheckConstraint("business_action IN ('import_order', 'export_order', 'invoice', 'payment', 'task', 'custom')", name="ck_approval_requests_action"),
        sa.CheckConstraint("related_entity_type IN ('import_order', 'export_order', 'invoice', 'payment', 'task', 'custom')", name="ck_approval_requests_related_type"),
        sa.CheckConstraint("status IN ('submitted', 'approved', 'rejected', 'returned', 'cancelled')", name="ck_approval_requests_status"),
    )
    op.create_index("ix_approval_requests_organization_id", "approval_requests", ["organization_id"])
    op.create_index("ix_approval_requests_org_status", "approval_requests", ["organization_id", "status", "submitted_at"])
    op.create_index("ix_approval_requests_org_entity", "approval_requests", ["organization_id", "related_entity_type", "related_entity_id"])

    op.create_table(
        "approval_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approval_request_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("note", sa.String(2000), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["approval_request_id", "organization_id"], ["approval_requests.id", "approval_requests.organization_id"], ondelete="CASCADE", name="fk_approval_events_request_org"),
    )
    op.create_index("ix_approval_events_organization_id", "approval_events", ["organization_id"])
    op.create_index("ix_approval_events_request_created", "approval_events", ["organization_id", "approval_request_id", "created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("link_path", sa.String(300), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        sa.CheckConstraint("category IN ('task', 'approval', 'invoice', 'shipment', 'inventory', 'document', 'order', 'system')", name="ck_notifications_category"),
    )
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_unread", "notifications", ["organization_id", "user_id", "read_at", "created_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", "category", name="uq_notification_preferences_user_category"),
        sa.CheckConstraint("category IN ('task', 'approval', 'invoice', 'shipment', 'inventory', 'document', 'order', 'system')", name="ck_notification_preferences_category"),
    )
    op.create_index("ix_notification_preferences_organization_id", "notification_preferences", ["organization_id"])
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])

    op.create_table(
        "automation_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.Column("status", sa.String(16), server_default="sent", nullable=False),
        sa.Column("recipient_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_error", sa.String(2000), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "dedupe_key", name="uq_automation_logs_org_dedupe"),
        sa.CheckConstraint("status IN ('sent', 'skipped', 'failed')", name="ck_automation_logs_status"),
    )
    op.create_index("ix_automation_logs_organization_id", "automation_logs", ["organization_id"])
    op.create_index("ix_automation_logs_org_created", "automation_logs", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_automation_logs_org_created", table_name="automation_logs")
    op.drop_index("ix_automation_logs_organization_id", table_name="automation_logs")
    op.drop_table("automation_logs")
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_index("ix_notification_preferences_organization_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_organization_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_approval_events_request_created", table_name="approval_events")
    op.drop_index("ix_approval_events_organization_id", table_name="approval_events")
    op.drop_table("approval_events")
    op.drop_index("ix_approval_requests_org_entity", table_name="approval_requests")
    op.drop_index("ix_approval_requests_org_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_organization_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_approval_rules_organization_id", table_name="approval_rules")
    op.drop_table("approval_rules")
    op.drop_index("ix_task_status_history_task_created", table_name="task_status_history")
    op.drop_index("ix_task_status_history_organization_id", table_name="task_status_history")
    op.drop_table("task_status_history")
    op.drop_index("ix_task_comments_task_created", table_name="task_comments")
    op.drop_index("ix_task_comments_organization_id", table_name="task_comments")
    op.drop_table("task_comments")
    op.drop_index("ix_tasks_org_assignee_status", table_name="tasks")
    op.drop_index("ix_tasks_org_status_due", table_name="tasks")
    op.drop_index("ix_tasks_assigned_to_user_id", table_name="tasks")
    op.drop_index("ix_tasks_organization_id", table_name="tasks")
    op.drop_table("tasks")
