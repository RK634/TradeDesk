"""Pydantic contracts for tasks, approvals, notifications, and automation logs."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TaskPriority = Literal["low", "normal", "high", "urgent"]
TaskStatus = Literal["open", "in_progress", "blocked", "completed", "cancelled"]
ApprovalAction = Literal["import_order", "export_order", "invoice", "payment", "task", "custom"]
ApprovalStatus = Literal["submitted", "approved", "rejected", "returned", "cancelled"]
NotificationCategory = Literal["task", "approval", "invoice", "shipment", "inventory", "document", "order", "system"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    assigned_to_user_id: UUID | None = None
    related_entity_type: Literal["import_order", "export_order", "shipment", "invoice", "document"] | None = None
    related_entity_id: UUID | None = None
    priority: TaskPriority = "normal"
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_related_pair(self):
        if (self.related_entity_type is None) != (self.related_entity_id is None):
            raise ValueError("related_entity_type and related_entity_id must be provided together.")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    assigned_to_user_id: UUID | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus
    note: str | None = Field(default=None, max_length=2000)


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class TaskCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_id: UUID
    author_user_id: UUID
    author_name: str
    body: str
    created_at: datetime


class TaskStatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    from_status: str | None
    to_status: str
    note: str | None
    actor_user_id: UUID
    actor_name: str
    created_at: datetime


class TaskOut(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    description: str | None
    assigned_to_user_id: UUID | None
    assigned_to_name: str | None
    related_entity_type: str | None
    related_entity_id: UUID | None
    priority: TaskPriority
    status: TaskStatus
    due_at: datetime | None
    completed_at: datetime | None
    created_by_user_id: UUID
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    comments: list[TaskCommentOut] = []
    history: list[TaskStatusHistoryOut] = []


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int


class ApprovalRuleUpsert(BaseModel):
    is_enabled: bool = True
    required_roles: list[Literal["organization_owner", "administrator", "import_manager", "export_manager", "operations_staff", "finance_staff"]] = Field(min_length=1)
    minimum_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    allow_self_approval: bool = False


class ApprovalRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID | None
    organization_id: UUID
    business_action: str
    is_enabled: bool
    required_roles: list[str]
    minimum_amount: Decimal | None
    allow_self_approval: bool
    updated_at: datetime


class ApprovalSubmit(BaseModel):
    business_action: ApprovalAction
    related_entity_type: ApprovalAction
    related_entity_id: UUID
    title: str = Field(min_length=2, max_length=180)
    request_note: str | None = Field(default=None, max_length=2000)
    requested_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_action_match(self):
        if self.business_action != self.related_entity_type and self.related_entity_type != "custom":
            raise ValueError("business_action must match related_entity_type unless the target type is custom.")
        if self.currency is not None:
            self.currency = self.currency.upper()
        return self


class ApprovalDecision(BaseModel):
    status: Literal["approved", "rejected", "returned"]
    decision_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_reason(self):
        if self.status in {"rejected", "returned"} and not (self.decision_note or "").strip():
            raise ValueError("A reason is required when an approval is rejected or returned.")
        return self


class ApprovalCancel(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)


class ApprovalEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    from_status: str | None
    to_status: str
    note: str | None
    actor_user_id: UUID
    actor_name: str
    created_at: datetime


class ApprovalRequestOut(BaseModel):
    id: UUID
    organization_id: UUID
    business_action: str
    related_entity_type: str
    related_entity_id: UUID
    title: str
    requested_by_user_id: UUID
    requested_by_name: str
    decided_by_user_id: UUID | None
    decided_by_name: str | None
    status: ApprovalStatus
    request_note: str | None
    decision_note: str | None
    requested_amount: Decimal | None
    currency: str | None
    submitted_at: datetime
    decided_at: datetime | None
    events: list[ApprovalEventOut] = []


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    user_id: UUID
    category: NotificationCategory
    title: str
    message: str
    link_path: str | None
    payload: dict
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationPreferenceUpdate(BaseModel):
    category: NotificationCategory
    in_app_enabled: bool


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category: NotificationCategory
    in_app_enabled: bool
    updated_at: datetime


class AutomationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    subject_type: str
    subject_id: UUID
    status: str
    recipient_count: int
    attempt_count: int
    last_error: str | None
    processed_at: datetime | None
    created_at: datetime
