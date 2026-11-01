"""Organization-scoped dashboard aggregates based on persisted records only."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.permissions import ROLE_PERMISSIONS, require_org_permission
from app.core.security import utc_now
from app.db.session import get_db
from app.models import ExportOrder, ExportShipment, ImportOrder, ImportShipment, Organization, OrganizationInvitation, OrganizationMembership, User, Invoice, Payment, PaymentAllocation
from app.schemas.dashboard import (
    DashboardSummaryOut,
    DashboardWorkspaceMetrics,
    MemberJoinTrendPoint,
    MemberRoleBreakdown,
    OperationalModuleStatus,
    FinanceCurrencyMetric,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
ROLE_LABELS = {
    "organization_owner": "Organization owner",
    "administrator": "Administrator",
    "import_manager": "Import manager",
    "export_manager": "Export manager",
    "operations_staff": "Operations staff",
    "finance_staff": "Finance staff",
    "read_only": "Read-only user",
}

# These are capability declarations, not fabricated KPI values. A module is marked
# available only once its domain records and aggregation logic exist.
OPERATIONAL_MODULES = [
    OperationalModuleStatus(
        key="imports", label="Import orders", available=True, planned_phase=6,
        explanation="Import orders, approval workflow, partial goods receipts, manual shipment milestones, and private order documents are available.",
    ),
    OperationalModuleStatus(
        key="exports", label="Export orders", available=True, planned_phase=7,
        explanation="Export quotations/orders, approval, stock reservations, duplicate-safe dispatch, and partial delivery records are available. Customer invoicing remains planned for Phase 9.",
    ),
    OperationalModuleStatus(
        key="shipments", label="Shipment tracking", available=True, planned_phase=8,
        explanation="Unified import/export shipment timeline, manual milestones, delay tracking, and status updates are available; carrier API tracking is not integrated.",
    ),
    OperationalModuleStatus(
        key="documents", label="Documents", available=True, planned_phase=8,
        explanation="Private versioned documents, verification history, and configurable requirements are available across import/export orders and shipments.",
    ),
    OperationalModuleStatus(
        key="invoices_payments", label="Invoices and payments", available=True, planned_phase=9,
        explanation="Supplier/customer invoices, partial payment allocations, currency conversion snapshots, payment reversals, and financial audit history are available.",
    ),
    OperationalModuleStatus(
        key="inventory", label="Inventory", available=True, planned_phase=5,
        explanation="Products, locations, stock balances, and a transactional movement ledger are available.",
    ),
    OperationalModuleStatus(
        key="reports", label="Reports and analytics", available=True, planned_phase=11,
        explanation="Organization-scoped order, partner, inventory, shipment-performance, missing-document, import-cost, and currency-separated financial reports are available with permission-controlled CSV exports.",
    ),
    OperationalModuleStatus(
        key="archive", label="Archive", available=True, planned_phase=11,
        explanation="Completed or cancelled import/export orders can be archived and restored with reasons and an immutable archive event history; archived records remain retained and searchable by authorized users.",
    ),
]


def _as_utc(value: datetime) -> datetime:
    """SQLite may return naive datetimes; interpret them as UTC for comparisons."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.get("/summary", response_model=DashboardSummaryOut, summary="Get organization dashboard summary")
def get_dashboard_summary(
    organization_id: UUID,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummaryOut:
    """Return real workspace aggregates; unimplemented trade KPIs remain explicitly unavailable."""
    today = utc_now().date()
    resolved_end = end_date or today
    resolved_start = start_date or (resolved_end - timedelta(days=29))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    if (resolved_end - resolved_start).days > 365:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days.")

    membership = require_org_permission(db, user.id, organization_id, "organization.read")
    organization = db.get(Organization, organization_id)
    if organization is None:  # Defensive; require_org_permission already validates membership.
        raise HTTPException(status_code=404, detail="Organization not found.")

    member_scope = OrganizationMembership.organization_id == organization_id
    total_members = db.query(func.count(OrganizationMembership.id)).filter(member_scope).scalar() or 0
    active_members = db.query(func.count(OrganizationMembership.id)).filter(
        member_scope, OrganizationMembership.is_active.is_(True)
    ).scalar() or 0
    inactive_members = total_members - active_members

    start_dt = datetime.combine(resolved_start, time.min, tzinfo=timezone.utc)
    end_exclusive = datetime.combine(resolved_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    new_member_rows = db.query(OrganizationMembership.joined_at).filter(
        member_scope,
        OrganizationMembership.joined_at >= start_dt,
        OrganizationMembership.joined_at < end_exclusive,
    ).all()
    joined_counts: dict[date, int] = {}
    for (joined_at,) in new_member_rows:
        joined_day = _as_utc(joined_at).date()
        joined_counts[joined_day] = joined_counts.get(joined_day, 0) + 1
    trend: list[MemberJoinTrendPoint] = []
    cursor = resolved_start
    while cursor <= resolved_end:
        trend.append(MemberJoinTrendPoint(date=cursor, label=cursor.strftime("%b %d"), count=joined_counts.get(cursor, 0)))
        cursor += timedelta(days=1)

    role_rows = db.query(
        OrganizationMembership.role,
        func.count(OrganizationMembership.id),
    ).filter(
        member_scope,
        OrganizationMembership.is_active.is_(True),
    ).group_by(OrganizationMembership.role).all()
    role_breakdown = [
        MemberRoleBreakdown(role=role, label=ROLE_LABELS.get(role, role.replace("_", " ").title()), count=count)
        for role, count in sorted(role_rows, key=lambda pair: (-pair[1], pair[0]))
    ]

    can_view_invitations = "members.invite" in ROLE_PERMISSIONS.get(membership.role, frozenset())
    pending_invitation_count: int | None = None
    if can_view_invitations:
        now = utc_now()
        invitation_rows = db.query(OrganizationInvitation.expires_at).filter(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        ).all()
        pending_invitation_count = sum(1 for (expires_at,) in invitation_rows if _as_utc(expires_at) > now)

    import_status_counts: dict[str, int] = {key: 0 for key in ("draft", "submitted", "approved", "rejected", "partially_received", "received", "cancelled")}
    import_rows = db.query(ImportOrder.status, func.count(ImportOrder.id)).filter(ImportOrder.organization_id == organization_id, ImportOrder.archived_at.is_(None)).group_by(ImportOrder.status).all()
    for status_value, count in import_rows:
        import_status_counts[status_value] = count
    active_import_orders = sum(count for key, count in import_status_counts.items() if key in {"submitted", "approved", "partially_received"})
    delayed_import_shipments = db.query(func.count(ImportShipment.id)).join(ImportOrder, (ImportOrder.id == ImportShipment.order_id) & (ImportOrder.organization_id == ImportShipment.organization_id)).filter(ImportShipment.organization_id == organization_id, ImportShipment.status == "delayed", ImportOrder.status != "cancelled", ImportOrder.archived_at.is_(None)).scalar() or 0

    export_status_keys = ("draft", "submitted", "approved", "rejected", "partially_dispatched", "dispatched", "partially_delivered", "delivered", "cancelled")
    export_status_counts: dict[str, int] = {key: 0 for key in export_status_keys}
    for status_value, count in db.query(ExportOrder.status, func.count(ExportOrder.id)).filter(ExportOrder.organization_id == organization_id, ExportOrder.archived_at.is_(None)).group_by(ExportOrder.status).all():
        export_status_counts[status_value] = count
    active_export_orders = sum(count for key, count in export_status_counts.items() if key in {"submitted", "approved", "partially_dispatched", "dispatched", "partially_delivered"})
    delayed_export_shipments = db.query(func.count(ExportShipment.id)).join(ExportOrder, (ExportOrder.id == ExportShipment.order_id) & (ExportOrder.organization_id == ExportShipment.organization_id)).filter(ExportShipment.organization_id == organization_id, ExportShipment.status == "delayed", ExportOrder.archived_at.is_(None)).scalar() or 0

    financial_metrics = None
    if "invoices.read" in ROLE_PERMISSIONS.get(membership.role, frozenset()):
        financial_rows = db.query(Invoice).filter(
            Invoice.organization_id == organization_id,
            Invoice.status.in_(["issued", "partially_paid", "paid"]),
        ).all()
        paid_rows = db.query(
            PaymentAllocation.invoice_id,
            func.sum(PaymentAllocation.allocated_invoice_amount),
        ).join(
            Payment,
            (Payment.id == PaymentAllocation.payment_id)
            & (Payment.organization_id == PaymentAllocation.organization_id),
        ).filter(
            PaymentAllocation.organization_id == organization_id,
            Payment.status == "posted",
        ).group_by(PaymentAllocation.invoice_id).all()
        paid_by_invoice = {invoice_id: Decimal(str(amount or 0)) for invoice_id, amount in paid_rows}
        financial_acc: dict[str, dict[str, Decimal | int]] = {}
        for invoice in financial_rows:
            if invoice.status == "paid":
                continue
            paid = paid_by_invoice.get(invoice.id, Decimal("0"))
            outstanding = max(Decimal(invoice.total_amount) - paid, Decimal("0"))
            if outstanding <= 0:
                continue
            bucket = financial_acc.setdefault(invoice.currency, {
                "customer_receivables": Decimal("0"), "supplier_payables": Decimal("0"),
                "overdue_customer": Decimal("0"), "overdue_supplier": Decimal("0"), "open_invoice_count": 0,
            })
            bucket["open_invoice_count"] = int(bucket["open_invoice_count"]) + 1
            if invoice.invoice_type == "customer":
                bucket["customer_receivables"] = Decimal(bucket["customer_receivables"]) + outstanding
                if invoice.due_date < today:
                    bucket["overdue_customer"] = Decimal(bucket["overdue_customer"]) + outstanding
            else:
                bucket["supplier_payables"] = Decimal(bucket["supplier_payables"]) + outstanding
                if invoice.due_date < today:
                    bucket["overdue_supplier"] = Decimal(bucket["overdue_supplier"]) + outstanding
        financial_metrics = [
            FinanceCurrencyMetric(currency=currency, **values)
            for currency, values in sorted(financial_acc.items())
        ]

    return DashboardSummaryOut(
        organization_id=organization.id,
        organization_name=organization.name,
        organization_role=membership.role,
        period_start=resolved_start,
        period_end=resolved_end,
        generated_at=utc_now(),
        workspace=DashboardWorkspaceMetrics(
            total_members=total_members,
            active_members=active_members,
            inactive_members=inactive_members,
            new_members=len(new_member_rows),
            pending_invitations=pending_invitation_count,
            can_view_invitations=can_view_invitations,
        ),
        member_join_trend=trend,
        members_by_role=role_breakdown,
        operational_modules=OPERATIONAL_MODULES,
        import_metrics={"active_orders": active_import_orders, "awaiting_approval": import_status_counts["submitted"], "partially_received": import_status_counts["partially_received"], "received": import_status_counts["received"], "delayed_shipments": delayed_import_shipments},
        export_metrics={"active_orders": active_export_orders, "awaiting_approval": export_status_counts["submitted"], "partially_dispatched": export_status_counts["partially_dispatched"], "dispatched": export_status_counts["dispatched"], "partially_delivered": export_status_counts["partially_delivered"], "delivered": export_status_counts["delivered"], "delayed_shipments": delayed_export_shipments},
        financial_metrics=financial_metrics,
    )
