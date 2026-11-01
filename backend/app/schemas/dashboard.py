"""Typed response contracts for organization-scoped dashboard summaries."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DashboardWorkspaceMetrics(BaseModel):
    total_members: int
    active_members: int
    inactive_members: int
    new_members: int
    pending_invitations: int | None
    can_view_invitations: bool


class MemberJoinTrendPoint(BaseModel):
    date: date
    label: str
    count: int


class MemberRoleBreakdown(BaseModel):
    role: str
    label: str
    count: int


class OperationalModuleStatus(BaseModel):
    key: str
    label: str
    available: bool
    planned_phase: int
    explanation: str


class FinanceCurrencyMetric(BaseModel):
    currency: str
    customer_receivables: Decimal
    supplier_payables: Decimal
    overdue_customer: Decimal
    overdue_supplier: Decimal
    open_invoice_count: int


class DashboardSummaryOut(BaseModel):
    organization_id: UUID
    organization_name: str
    organization_role: str
    period_start: date
    period_end: date
    generated_at: datetime
    workspace: DashboardWorkspaceMetrics
    member_join_trend: list[MemberJoinTrendPoint]
    members_by_role: list[MemberRoleBreakdown]
    operational_modules: list[OperationalModuleStatus]
    import_metrics: dict[str, int | str | None] | None = None
    export_metrics: dict[str, int | str | None] | None = None
    financial_metrics: list[FinanceCurrencyMetric] | None = None

    model_config = ConfigDict(from_attributes=True)
