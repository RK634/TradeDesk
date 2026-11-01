"""Tasks, approval workflows, in-app notifications, and automation execution logs."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    JSON, Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_tasks_id_org"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_tasks_priority"),
        CheckConstraint("status IN ('open', 'in_progress', 'blocked', 'completed', 'cancelled')", name="ck_tasks_status"),
        CheckConstraint("related_entity_type IS NULL OR related_entity_type IN ('import_order', 'export_order', 'shipment', 'invoice', 'document')", name="ck_tasks_related_type"),
        Index("ix_tasks_org_status_due", "organization_id", "status", "due_at"),
        Index("ix_tasks_org_assignee_status", "organization_id", "assigned_to_user_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    related_entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class TaskComment(Base):
    __tablename__ = "task_comments"
    __table_args__ = (
        ForeignKeyConstraint(["task_id", "organization_id"], ["tasks.id", "tasks.organization_id"], ondelete="CASCADE", name="fk_task_comments_task_org"),
        Index("ix_task_comments_task_created", "organization_id", "task_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TaskStatusHistory(Base):
    __tablename__ = "task_status_history"
    __table_args__ = (
        ForeignKeyConstraint(["task_id", "organization_id"], ["tasks.id", "tasks.organization_id"], ondelete="CASCADE", name="fk_task_status_history_task_org"),
        Index("ix_task_status_history_task_created", "organization_id", "task_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ApprovalRule(Base):
    __tablename__ = "approval_rules"
    __table_args__ = (
        UniqueConstraint("organization_id", "business_action", name="uq_approval_rules_org_action"),
        CheckConstraint("business_action IN ('import_order', 'export_order', 'invoice', 'payment', 'task', 'custom')", name="ck_approval_rules_action"),
        CheckConstraint("minimum_amount IS NULL OR minimum_amount >= 0", name="ck_approval_rules_minimum_amount"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    business_action: Mapped[str] = mapped_column(String(32), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    required_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    minimum_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    allow_self_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_approval_requests_id_org"),
        CheckConstraint("business_action IN ('import_order', 'export_order', 'invoice', 'payment', 'task', 'custom')", name="ck_approval_requests_action"),
        CheckConstraint("related_entity_type IN ('import_order', 'export_order', 'invoice', 'payment', 'task', 'custom')", name="ck_approval_requests_related_type"),
        CheckConstraint("status IN ('submitted', 'approved', 'rejected', 'returned', 'cancelled')", name="ck_approval_requests_status"),
        Index("ix_approval_requests_org_status", "organization_id", "status", "submitted_at"),
        Index("ix_approval_requests_org_entity", "organization_id", "related_entity_type", "related_entity_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    business_action: Mapped[str] = mapped_column(String(32), nullable=False)
    related_entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    related_entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted", server_default="submitted")
    request_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    requested_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ApprovalEvent(Base):
    __tablename__ = "approval_events"
    __table_args__ = (
        ForeignKeyConstraint(["approval_request_id", "organization_id"], ["approval_requests.id", "approval_requests.organization_id"], ondelete="CASCADE", name="fk_approval_events_request_org"),
        Index("ix_approval_events_request_created", "organization_id", "approval_request_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    approval_request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        CheckConstraint("category IN ('task', 'approval', 'invoice', 'shipment', 'inventory', 'document', 'order', 'system')", name="ck_notifications_category"),
        Index("ix_notifications_user_unread", "organization_id", "user_id", "read_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    link_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", "category", name="uq_notification_preferences_user_category"),
        CheckConstraint("category IN ('task', 'approval', 'invoice', 'shipment', 'inventory', 'document', 'order', 'system')", name="ck_notification_preferences_category"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AutomationLog(Base):
    __tablename__ = "automation_logs"
    __table_args__ = (
        UniqueConstraint("organization_id", "dedupe_key", name="uq_automation_logs_org_dedupe"),
        CheckConstraint("status IN ('sent', 'skipped', 'failed')", name="ck_automation_logs_status"),
        Index("ix_automation_logs_org_created", "organization_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sent", server_default="sent")
    recipient_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
