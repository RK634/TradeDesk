"""Organization-scoped operational, inventory, shipment, and financial reports."""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.permissions import ROLE_PERMISSIONS, require_org_permission
from app.core.security import utc_now
from app.db.session import get_db
from app.models import (
    Customer, DocumentRequirement, ExportOrder, ExportOrderItem, ExportShipment,
    ImportOrder, ImportOrderItem, ImportShipment, InventoryBalance, InventoryLocation,
    InventoryMovement, Invoice, Payment, PaymentAllocation, Product, Supplier, TradeDocument, User,
)
from app.schemas.reports import (
    FinancialCurrencySummary, FinancialReport, ImportCostReportRow, InventoryMovementReportRow,
    InventoryReportRow, MissingDocumentReportRow, OrderReportRow, PartnerReportRow,
    ReportSummary, ShipmentPerformanceRow,
)

router = APIRouter(prefix="/reports", tags=["reports"])
ZERO = Decimal("0")


def _date_bounds(start_date: date | None, end_date: date | None) -> tuple[date, date, datetime, datetime]:
    resolved_end = end_date or utc_now().date()
    resolved_start = start_date or (resolved_end - timedelta(days=29))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    if (resolved_end - resolved_start).days > 366:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 367 days.")
    return (
        resolved_start,
        resolved_end,
        datetime.combine(resolved_start, time.min, tzinfo=timezone.utc),
        datetime.combine(resolved_end + timedelta(days=1), time.min, tzinfo=timezone.utc),
    )


def _require_reports(db: Session, user: User, organization_id: UUID) -> str:
    membership = require_org_permission(db, user.id, organization_id, "reports.read")
    return membership.role


def _financial_rows(db: Session, organization_id: UUID, start_dt: datetime, end_dt: datetime) -> list[FinancialCurrencySummary]:
    invoices = db.query(Invoice).filter(
        Invoice.organization_id == organization_id,
        Invoice.status.in_(["issued", "partially_paid", "paid"]),
        Invoice.issue_date >= start_dt.date(),
        Invoice.issue_date < end_dt.date(),
    ).all()
    invoice_ids = [row.id for row in invoices]
    paid_rows = []
    if invoice_ids:
        paid_rows = db.query(
            PaymentAllocation.invoice_id,
            func.coalesce(func.sum(PaymentAllocation.allocated_invoice_amount), 0),
        ).join(
            Payment,
            (Payment.id == PaymentAllocation.payment_id) & (Payment.organization_id == PaymentAllocation.organization_id),
        ).filter(
            PaymentAllocation.organization_id == organization_id,
            PaymentAllocation.invoice_id.in_(invoice_ids),
            Payment.status == "posted",
        ).group_by(PaymentAllocation.invoice_id).all()
    paid_by_invoice = {invoice_id: Decimal(str(amount or 0)) for invoice_id, amount in paid_rows}
    totals: dict[str, dict[str, Decimal]] = {}
    today = utc_now().date()
    for invoice in invoices:
        amount_paid = paid_by_invoice.get(invoice.id, ZERO)
        outstanding = max(Decimal(invoice.total_amount) - amount_paid, ZERO)
        if outstanding <= 0:
            continue
        bucket = totals.setdefault(invoice.currency, {
            "receivables_outstanding": ZERO, "payables_outstanding": ZERO,
            "overdue_receivables": ZERO, "overdue_payables": ZERO,
        })
        if invoice.invoice_type == "customer":
            bucket["receivables_outstanding"] += outstanding
            if invoice.due_date < today:
                bucket["overdue_receivables"] += outstanding
        else:
            bucket["payables_outstanding"] += outstanding
            if invoice.due_date < today:
                bucket["overdue_payables"] += outstanding
    return [FinancialCurrencySummary(currency=currency, **values) for currency, values in sorted(totals.items())]


def _order_rows(db: Session, organization_id: UUID, start_dt: datetime, end_dt: datetime, direction: str | None = None) -> list[OrderReportRow]:
    results: list[OrderReportRow] = []
    if direction in (None, "import"):
        rows = db.query(ImportOrder, Supplier.name).join(
            Supplier, (Supplier.id == ImportOrder.supplier_id) & (Supplier.organization_id == organization_id),
        ).filter(
            ImportOrder.organization_id == organization_id,
            ImportOrder.archived_at.is_(None),
            ImportOrder.created_at >= start_dt,
            ImportOrder.created_at < end_dt,
        ).all()
        for order, partner in rows:
            items = db.query(ImportOrderItem).filter(
                ImportOrderItem.organization_id == organization_id, ImportOrderItem.order_id == order.id,
            ).all()
            goods = sum((Decimal(item.quantity_ordered) * Decimal(item.unit_price) for item in items), ZERO)
            costs = sum((Decimal(value or 0) for value in (
                order.estimated_freight_cost, order.estimated_insurance_cost,
                order.estimated_duties, order.estimated_other_costs,
            )), ZERO)
            results.append(OrderReportRow(
                record_id=order.id, direction="import", reference=order.reference,
                partner_name=partner, status=order.status, currency=order.currency,
                order_total=goods + costs, created_at=order.created_at,
            ))
    if direction in (None, "export"):
        rows = db.query(ExportOrder, Customer.name).join(
            Customer, (Customer.id == ExportOrder.customer_id) & (Customer.organization_id == organization_id),
        ).filter(
            ExportOrder.organization_id == organization_id,
            ExportOrder.archived_at.is_(None),
            ExportOrder.created_at >= start_dt,
            ExportOrder.created_at < end_dt,
        ).all()
        for order, partner in rows:
            items = db.query(ExportOrderItem).filter(
                ExportOrderItem.organization_id == organization_id, ExportOrderItem.order_id == order.id,
            ).all()
            goods = sum((Decimal(item.quantity_ordered) * Decimal(item.unit_price) for item in items), ZERO)
            results.append(OrderReportRow(
                record_id=order.id, direction="export", reference=order.reference,
                partner_name=partner, status=order.status, currency=order.currency,
                order_total=goods, created_at=order.created_at,
            ))
    return sorted(results, key=lambda row: (row.created_at, row.reference), reverse=True)


def _inventory_rows(db: Session, organization_id: UUID, low_stock_only: bool = False) -> list[InventoryReportRow]:
    rows = db.query(InventoryBalance, Product, InventoryLocation).join(
        Product, (Product.id == InventoryBalance.product_id) & (Product.organization_id == InventoryBalance.organization_id),
    ).join(
        InventoryLocation, (InventoryLocation.id == InventoryBalance.location_id) & (InventoryLocation.organization_id == InventoryBalance.organization_id),
    ).filter(InventoryBalance.organization_id == organization_id).order_by(Product.sku.asc(), InventoryLocation.code.asc()).all()
    result: list[InventoryReportRow] = []
    for balance, product, location in rows:
        on_hand = Decimal(balance.quantity_on_hand)
        reserved = Decimal(balance.reserved_quantity)
        available = on_hand - reserved
        low_stock = available <= Decimal(product.reorder_threshold)
        if low_stock_only and not low_stock:
            continue
        result.append(InventoryReportRow(
            product_id=product.id, sku=product.sku, product_name=product.name,
            location_id=location.id, location_code=location.code, location_name=location.name,
            quantity_on_hand=on_hand, reserved_quantity=reserved, available_quantity=available,
            reorder_threshold=Decimal(product.reorder_threshold), is_low_stock=low_stock,
        ))
    return result


def _movement_rows(db: Session, organization_id: UUID, start_dt: datetime, end_dt: datetime, movement_type: str | None = None) -> list[InventoryMovementReportRow]:
    query = db.query(InventoryMovement, Product, InventoryLocation).join(
        Product, (Product.id == InventoryMovement.product_id) & (Product.organization_id == InventoryMovement.organization_id),
    ).join(
        InventoryLocation, (InventoryLocation.id == InventoryMovement.location_id) & (InventoryLocation.organization_id == InventoryMovement.organization_id),
    ).filter(
        InventoryMovement.organization_id == organization_id,
        InventoryMovement.created_at >= start_dt,
        InventoryMovement.created_at < end_dt,
    )
    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type)
    rows = query.order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.asc()).all()
    return [InventoryMovementReportRow(
        id=movement.id, product_id=product.id, sku=product.sku, product_name=product.name,
        location_id=location.id, location_code=location.code, movement_type=movement.movement_type,
        quantity_delta=Decimal(movement.quantity_delta), reserved_delta=Decimal(movement.reserved_delta),
        quantity_on_hand_after=Decimal(movement.quantity_on_hand_after),
        reserved_quantity_after=Decimal(movement.reserved_quantity_after),
        source_type=movement.source_type, source_reference=movement.source_reference,
        created_by_user_id=movement.created_by_user_id, created_at=movement.created_at,
    ) for movement, product, location in rows]


def _active_requirement_context(db: Session, organization_id: UUID, entity_type: str, entity_id: UUID):
    """Return (reference, partner) for an active order/shipment requirement, else None."""
    if entity_type == "import_order":
        row = db.query(ImportOrder, Supplier.name).join(
            Supplier, (Supplier.id == ImportOrder.supplier_id) & (Supplier.organization_id == organization_id),
        ).filter(ImportOrder.id == entity_id, ImportOrder.organization_id == organization_id, ImportOrder.archived_at.is_(None)).one_or_none()
        return (row[0].reference, row[1]) if row else None
    if entity_type == "export_order":
        row = db.query(ExportOrder, Customer.name).join(
            Customer, (Customer.id == ExportOrder.customer_id) & (Customer.organization_id == organization_id),
        ).filter(ExportOrder.id == entity_id, ExportOrder.organization_id == organization_id, ExportOrder.archived_at.is_(None)).one_or_none()
        return (row[0].reference, row[1]) if row else None
    if entity_type == "import_shipment":
        row = db.query(ImportShipment, ImportOrder, Supplier.name).join(
            ImportOrder, (ImportOrder.id == ImportShipment.order_id) & (ImportOrder.organization_id == ImportShipment.organization_id),
        ).join(Supplier, (Supplier.id == ImportOrder.supplier_id) & (Supplier.organization_id == organization_id)).filter(
            ImportShipment.id == entity_id, ImportShipment.organization_id == organization_id, ImportOrder.archived_at.is_(None),
        ).one_or_none()
        return (row[0].shipment_reference, row[2]) if row else None
    if entity_type == "export_shipment":
        row = db.query(ExportShipment, ExportOrder, Customer.name).join(
            ExportOrder, (ExportOrder.id == ExportShipment.order_id) & (ExportOrder.organization_id == ExportShipment.organization_id),
        ).join(Customer, (Customer.id == ExportOrder.customer_id) & (Customer.organization_id == organization_id)).filter(
            ExportShipment.id == entity_id, ExportShipment.organization_id == organization_id, ExportOrder.archived_at.is_(None),
        ).one_or_none()
        return (row[0].shipment_reference, row[2]) if row else None
    return None


def _missing_document_rows(db: Session, organization_id: UUID) -> list[MissingDocumentReportRow]:
    requirements = db.query(DocumentRequirement).filter(
        DocumentRequirement.organization_id == organization_id,
        DocumentRequirement.is_required.is_(True),
    ).order_by(DocumentRequirement.created_at.desc()).all()
    missing: list[MissingDocumentReportRow] = []
    for requirement in requirements:
        context = _active_requirement_context(
            db, organization_id, requirement.related_entity_type, requirement.related_entity_id,
        )
        if context is None:
            continue
        verified = db.query(TradeDocument.id).filter(
            TradeDocument.organization_id == organization_id,
            TradeDocument.related_entity_type == requirement.related_entity_type,
            TradeDocument.related_entity_id == requirement.related_entity_id,
            TradeDocument.document_type == requirement.document_type,
            TradeDocument.verification_status == "verified",
        ).first()
        if verified:
            continue
        missing.append(MissingDocumentReportRow(
            requirement_id=requirement.id,
            related_entity_type=requirement.related_entity_type,
            related_entity_id=requirement.related_entity_id,
            record_reference=context[0], partner_name=context[1],
            document_type=requirement.document_type, label=requirement.label,
            created_at=requirement.created_at,
        ))
    return missing


def _missing_required_documents(db: Session, organization_id: UUID) -> int:
    return len(_missing_document_rows(db, organization_id))


def _import_cost_rows(db: Session, organization_id: UUID, start_dt: datetime, end_dt: datetime) -> list[ImportCostReportRow]:
    orders = db.query(ImportOrder, Supplier.name).join(
        Supplier, (Supplier.id == ImportOrder.supplier_id) & (Supplier.organization_id == organization_id),
    ).filter(
        ImportOrder.organization_id == organization_id, ImportOrder.archived_at.is_(None),
        ImportOrder.created_at >= start_dt, ImportOrder.created_at < end_dt,
    ).order_by(ImportOrder.created_at.desc()).all()
    rows: list[ImportCostReportRow] = []
    for order, supplier_name in orders:
        items = db.query(ImportOrderItem).filter(
            ImportOrderItem.organization_id == organization_id, ImportOrderItem.order_id == order.id,
        ).all()
        goods = sum((Decimal(item.quantity_ordered) * Decimal(item.unit_price) for item in items), ZERO)
        estimated_costs = sum((Decimal(value or 0) for value in (
            order.estimated_freight_cost, order.estimated_insurance_cost, order.estimated_duties, order.estimated_other_costs,
        )), ZERO)
        actual_costs = sum((Decimal(value or 0) for value in (
            order.actual_freight_cost, order.actual_insurance_cost, order.actual_duties, order.actual_other_costs,
        )), ZERO)
        estimated_total = goods + estimated_costs
        actual_total = goods + actual_costs
        rows.append(ImportCostReportRow(
            record_id=order.id, reference=order.reference, supplier_name=supplier_name,
            status=order.status, currency=order.currency, estimated_goods_total=goods,
            estimated_costs=estimated_costs, estimated_total=estimated_total,
            actual_costs=actual_costs, actual_total=actual_total,
            variance=actual_total - estimated_total, created_at=order.created_at,
        ))
    return rows


def _partner_rows(db: Session, organization_id: UUID, start_dt: datetime, end_dt: datetime) -> list[PartnerReportRow]:
    groups: dict[tuple[str, str, str], list[Decimal | int]] = {}
    for row in _order_rows(db, organization_id, start_dt, end_dt):
        key = (row.direction, row.partner_name, row.currency)
        bucket = groups.setdefault(key, [0, ZERO])
        bucket[0] = int(bucket[0]) + 1
        bucket[1] = Decimal(bucket[1]) + row.order_total
    return [PartnerReportRow(
        direction=direction, partner_name=partner, currency=currency,
        order_count=int(values[0]), order_value=Decimal(values[1]),
    ) for (direction, partner, currency), values in sorted(groups.items())]


def _shipment_performance_rows(db: Session, organization_id: UUID, start_dt: datetime, end_dt: datetime) -> list[ShipmentPerformanceRow]:
    results: list[ShipmentPerformanceRow] = []
    today = utc_now().date()
    imports = db.query(ImportShipment, ImportOrder, Supplier.name).join(
        ImportOrder, (ImportOrder.id == ImportShipment.order_id) & (ImportOrder.organization_id == ImportShipment.organization_id),
    ).join(Supplier, (Supplier.id == ImportOrder.supplier_id) & (Supplier.organization_id == organization_id)).filter(
        ImportShipment.organization_id == organization_id, ImportOrder.archived_at.is_(None),
        ImportShipment.created_at >= start_dt, ImportShipment.created_at < end_dt,
    ).all()
    exports = db.query(ExportShipment, ExportOrder, Customer.name).join(
        ExportOrder, (ExportOrder.id == ExportShipment.order_id) & (ExportOrder.organization_id == ExportShipment.organization_id),
    ).join(Customer, (Customer.id == ExportOrder.customer_id) & (Customer.organization_id == organization_id)).filter(
        ExportShipment.organization_id == organization_id, ExportOrder.archived_at.is_(None),
        ExportShipment.created_at >= start_dt, ExportShipment.created_at < end_dt,
    ).all()
    for shipment, order, partner in imports:
        eta = shipment.estimated_arrival
        arrival = shipment.actual_arrival
        days_late = max((arrival - eta).days, 0) if eta and arrival else (max((today - eta).days, 0) if eta and not arrival and eta < today else None)
        results.append(ShipmentPerformanceRow(
            shipment_id=shipment.id, direction="import", shipment_reference=shipment.shipment_reference,
            order_reference=order.reference, partner_name=partner, status=shipment.status,
            transport_mode=shipment.transport_mode, estimated_arrival=eta, actual_arrival=arrival,
            days_late=days_late, delay_reason=shipment.delay_reason, created_at=shipment.created_at,
        ))
    for shipment, order, partner in exports:
        eta = shipment.estimated_arrival
        arrival = shipment.actual_arrival
        days_late = max((arrival - eta).days, 0) if eta and arrival else (max((today - eta).days, 0) if eta and not arrival and eta < today else None)
        results.append(ShipmentPerformanceRow(
            shipment_id=shipment.id, direction="export", shipment_reference=shipment.shipment_reference,
            order_reference=order.reference, partner_name=partner, status=shipment.status,
            transport_mode=shipment.transport_mode, estimated_arrival=eta, actual_arrival=arrival,
            days_late=days_late, delay_reason=shipment.delay_reason, created_at=shipment.created_at,
        ))
    return sorted(results, key=lambda row: row.created_at, reverse=True)


@router.get("/summary", response_model=ReportSummary, summary="Get operational and financial report summary")
def get_report_summary(
    organization_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportSummary:
    role = _require_reports(db, user, organization_id)
    start, end, start_dt, end_dt = _date_bounds(start_date, end_date)
    imports = db.query(ImportOrder.status, func.count(ImportOrder.id)).filter(
        ImportOrder.organization_id == organization_id,
        ImportOrder.archived_at.is_(None),
        ImportOrder.created_at >= start_dt, ImportOrder.created_at < end_dt,
    ).group_by(ImportOrder.status).all()
    exports = db.query(ExportOrder.status, func.count(ExportOrder.id)).filter(
        ExportOrder.organization_id == organization_id,
        ExportOrder.archived_at.is_(None),
        ExportOrder.created_at >= start_dt, ExportOrder.created_at < end_dt,
    ).group_by(ExportOrder.status).all()
    import_statuses = {status: count for status, count in imports}
    export_statuses = {status: count for status, count in exports}
    total_imports = sum(import_statuses.values())
    total_exports = sum(export_statuses.values())

    import_shipments = db.query(ImportShipment).join(
        ImportOrder, (ImportOrder.id == ImportShipment.order_id) & (ImportOrder.organization_id == ImportShipment.organization_id),
    ).filter(
        ImportShipment.organization_id == organization_id,
        ImportOrder.archived_at.is_(None),
        ImportShipment.created_at >= start_dt, ImportShipment.created_at < end_dt,
    ).all()
    export_shipments = db.query(ExportShipment).join(
        ExportOrder, (ExportOrder.id == ExportShipment.order_id) & (ExportOrder.organization_id == ExportShipment.organization_id),
    ).filter(
        ExportShipment.organization_id == organization_id,
        ExportOrder.archived_at.is_(None),
        ExportShipment.created_at >= start_dt, ExportShipment.created_at < end_dt,
    ).all()
    inventory = _inventory_rows(db, organization_id)
    result = ReportSummary(
        start_date=start, end_date=end,
        imports={"total": total_imports, "by_status": [{"status": key, "count": value} for key, value in sorted(import_statuses.items())]},
        exports={"total": total_exports, "by_status": [{"status": key, "count": value} for key, value in sorted(export_statuses.items())]},
        shipments={
            "total": len(import_shipments) + len(export_shipments),
            "delayed": sum(1 for shipment in [*import_shipments, *export_shipments] if shipment.status == "delayed"),
            "import_total": len(import_shipments), "export_total": len(export_shipments),
        },
        inventory={"balance_rows": len(inventory), "low_stock_rows": sum(1 for row in inventory if row.is_low_stock)},
        missing_required_documents=_missing_required_documents(db, organization_id),
        financial=_financial_rows(db, organization_id, start_dt, end_dt) if "reports.finance.read" in ROLE_PERMISSIONS.get(role, frozenset()) else None,
    )
    return result


@router.get("/orders", response_model=list[OrderReportRow], summary="List import/export report rows")
def get_order_report(
    organization_id: UUID,
    direction: str | None = Query(default=None, pattern="^(import|export)$"),
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrderReportRow]:
    _require_reports(db, user, organization_id)
    _, _, start_dt, end_dt = _date_bounds(start_date, end_date)
    return _order_rows(db, organization_id, start_dt, end_dt, direction)


@router.get("/inventory", response_model=list[InventoryReportRow], summary="Get current stock and low-stock report")
def get_inventory_report(
    organization_id: UUID,
    low_stock_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InventoryReportRow]:
    _require_reports(db, user, organization_id)
    return _inventory_rows(db, organization_id, low_stock_only)


@router.get("/inventory-movements", response_model=list[InventoryMovementReportRow], summary="Get inventory movement history report")
def get_inventory_movement_report(
    organization_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    movement_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InventoryMovementReportRow]:
    _require_reports(db, user, organization_id)
    _, _, start_dt, end_dt = _date_bounds(start_date, end_date)
    return _movement_rows(db, organization_id, start_dt, end_dt, movement_type)


@router.get("/import-costs", response_model=list[ImportCostReportRow], summary="Compare estimated and actual import costs")
def get_import_cost_report(
    organization_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ImportCostReportRow]:
    _require_reports(db, user, organization_id)
    _, _, start_dt, end_dt = _date_bounds(start_date, end_date)
    return _import_cost_rows(db, organization_id, start_dt, end_dt)


@router.get("/partners", response_model=list[PartnerReportRow], summary="Summarize order values by customer or supplier and currency")
def get_partner_report(
    organization_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PartnerReportRow]:
    _require_reports(db, user, organization_id)
    _, _, start_dt, end_dt = _date_bounds(start_date, end_date)
    return _partner_rows(db, organization_id, start_dt, end_dt)


@router.get("/shipment-performance", response_model=list[ShipmentPerformanceRow], summary="Report shipment arrival performance and delays")
def get_shipment_performance_report(
    organization_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShipmentPerformanceRow]:
    _require_reports(db, user, organization_id)
    _, _, start_dt, end_dt = _date_bounds(start_date, end_date)
    return _shipment_performance_rows(db, organization_id, start_dt, end_dt)


@router.get("/missing-documents", response_model=list[MissingDocumentReportRow], summary="List required documents without a verified document")
def get_missing_documents_report(
    organization_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MissingDocumentReportRow]:
    _require_reports(db, user, organization_id)
    return _missing_document_rows(db, organization_id)


@router.get("/financial", response_model=FinancialReport, summary="Get currency-separated receivables and payables report")
def get_financial_report(
    organization_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialReport:
    role = _require_reports(db, user, organization_id)
    require_org_permission(db, user.id, organization_id, "reports.finance.read")
    start, end, start_dt, end_dt = _date_bounds(start_date, end_date)
    return FinancialReport(start_date=start, end_date=end, by_currency=_financial_rows(db, organization_id, start_dt, end_dt))


def _safe_text(value: object) -> str:
    text = "" if value is None else str(value)
    candidate = text.lstrip(" \t\r\n")
    if candidate[:1] in {"=", "+", "-", "@"}:
        return "'" + text
    return text


def _csv_response(filename: str, headers: list[str], rows: Iterable[Iterable[object]]) -> StreamingResponse:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe_text(value) if isinstance(value, str) else value for value in row])
    payload = output.getvalue()
    return StreamingResponse(
        iter([payload]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.get("/csv", summary="Export an authorized report as CSV")
def export_report_csv(
    organization_id: UUID,
    report_type: str = Query(pattern="^(orders|inventory|inventory_movements|import_costs|partners|shipment_performance|missing_documents|invoices|payments)$"),
    start_date: date | None = None,
    end_date: date | None = None,
    direction: str | None = Query(default=None, pattern="^(import|export)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _require_reports(db, user, organization_id)
    require_org_permission(db, user.id, organization_id, "reports.export")
    start, end, start_dt, end_dt = _date_bounds(start_date, end_date)
    date_suffix = f"{start.isoformat()}_{end.isoformat()}"

    if report_type == "orders":
        rows = _order_rows(db, organization_id, start_dt, end_dt, direction)
        return _csv_response(f"orders_{date_suffix}.csv", ["record_id", "direction", "reference", "partner", "status", "currency", "order_total", "created_at"], (
            (row.record_id, row.direction, row.reference, row.partner_name, row.status, row.currency, row.order_total, row.created_at.isoformat()) for row in rows
        ))
    if report_type == "inventory":
        rows = _inventory_rows(db, organization_id)
        return _csv_response("inventory_stock.csv", ["product_id", "sku", "product_name", "location_code", "location_name", "on_hand", "reserved", "available", "reorder_threshold", "low_stock"], (
            (row.product_id, row.sku, row.product_name, row.location_code, row.location_name, row.quantity_on_hand, row.reserved_quantity, row.available_quantity, row.reorder_threshold, row.is_low_stock) for row in rows
        ))
    if report_type == "inventory_movements":
        rows = _movement_rows(db, organization_id, start_dt, end_dt)
        return _csv_response(f"inventory_movements_{date_suffix}.csv", ["movement_id", "sku", "product_name", "location_code", "movement_type", "quantity_delta", "reserved_delta", "on_hand_after", "reserved_after", "source_type", "source_reference", "created_at"], (
            (row.id, row.sku, row.product_name, row.location_code, row.movement_type, row.quantity_delta, row.reserved_delta, row.quantity_on_hand_after, row.reserved_quantity_after, row.source_type, row.source_reference, row.created_at.isoformat()) for row in rows
        ))

    if report_type == "import_costs":
        rows = _import_cost_rows(db, organization_id, start_dt, end_dt)
        return _csv_response(f"import_costs_{date_suffix}.csv", ["record_id", "reference", "supplier", "status", "currency", "estimated_goods_total", "estimated_costs", "estimated_total", "actual_costs", "actual_total", "variance"], (
            (row.record_id, row.reference, row.supplier_name, row.status, row.currency, row.estimated_goods_total, row.estimated_costs, row.estimated_total, row.actual_costs, row.actual_total, row.variance) for row in rows
        ))
    if report_type == "partners":
        rows = _partner_rows(db, organization_id, start_dt, end_dt)
        return _csv_response(f"partners_{date_suffix}.csv", ["direction", "partner", "currency", "order_count", "order_value"], (
            (row.direction, row.partner_name, row.currency, row.order_count, row.order_value) for row in rows
        ))
    if report_type == "shipment_performance":
        rows = _shipment_performance_rows(db, organization_id, start_dt, end_dt)
        return _csv_response(f"shipment_performance_{date_suffix}.csv", ["shipment_id", "direction", "shipment_reference", "order_reference", "partner", "status", "transport_mode", "estimated_arrival", "actual_arrival", "days_late", "delay_reason"], (
            (row.shipment_id, row.direction, row.shipment_reference, row.order_reference, row.partner_name, row.status, row.transport_mode, row.estimated_arrival.isoformat() if row.estimated_arrival else "", row.actual_arrival.isoformat() if row.actual_arrival else "", row.days_late, row.delay_reason or "") for row in rows
        ))
    if report_type == "missing_documents":
        rows = _missing_document_rows(db, organization_id)
        return _csv_response("missing_documents.csv", ["requirement_id", "entity_type", "record_reference", "partner", "document_type", "label", "created_at"], (
            (row.requirement_id, row.related_entity_type, row.record_reference, row.partner_name, row.document_type, row.label, row.created_at.isoformat()) for row in rows
        ))

    require_org_permission(db, user.id, organization_id, "reports.finance.read")
    if report_type == "invoices":
        invoices = db.query(Invoice).filter(Invoice.organization_id == organization_id, Invoice.issue_date >= start, Invoice.issue_date <= end).order_by(Invoice.issue_date.desc()).all()
        return _csv_response(f"invoices_{date_suffix}.csv", ["invoice_id", "invoice_number", "type", "status", "currency", "issue_date", "due_date", "total_amount"], (
            (row.id, row.invoice_number, row.invoice_type, row.status, row.currency, row.issue_date.isoformat(), row.due_date.isoformat(), row.total_amount) for row in invoices
        ))
    payments = db.query(Payment).filter(Payment.organization_id == organization_id, Payment.payment_date >= start, Payment.payment_date <= end).order_by(Payment.payment_date.desc()).all()
    return _csv_response(f"payments_{date_suffix}.csv", ["payment_id", "payment_reference", "type", "status", "currency", "payment_date", "amount", "payment_method", "external_reference"], (
        (row.id, row.payment_reference, row.payment_type, row.status, row.currency, row.payment_date.isoformat(), row.amount, row.payment_method, row.external_reference) for row in payments
    ))
