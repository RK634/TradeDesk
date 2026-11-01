"""Duplicate-safe scheduled notification generation for trade operations."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ApprovalRequest, AutomationLog, DocumentRequirement, ExportOrder, ExportShipment, ImportOrder, ImportShipment,
    Invoice, InventoryBalance, NotificationPreference, Organization, OrganizationMembership,
    Payment, PaymentAllocation, Product, Task, TradeDocument,
)
from app.services.workflow import create_notification, get_approval_roles

MAX_ATTEMPTS = 5
FINANCE_ROLES = {"organization_owner", "administrator", "finance_staff"}
OPERATIONS_ROLES = {"organization_owner", "administrator", "operations_staff"}
IMPORT_ROLES = {"organization_owner", "administrator", "import_manager", "operations_staff"}
EXPORT_ROLES = {"organization_owner", "administrator", "export_manager", "operations_staff"}
INVENTORY_ROLES = {"organization_owner", "administrator", "import_manager", "export_manager", "operations_staff"}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _recipients(db: Session, organization_id: UUID, roles: set[str], assignee_id: UUID | None = None) -> list[UUID]:
    query = db.query(OrganizationMembership.user_id).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.is_active.is_(True),
    )
    if assignee_id is not None:
        query = query.filter(OrganizationMembership.user_id == assignee_id)
    else:
        query = query.filter(OrganizationMembership.role.in_(sorted(roles)))
    return [row[0] for row in query.all()]


def _emit(
    db: Session,
    *, organization_id: UUID,
    event_type: str,
    subject_type: str,
    subject_id: UUID,
    dedupe_key: str,
    category: str,
    title: str,
    message: str,
    recipients: list[UUID],
    link_path: str | None,
    now: datetime,
) -> bool:
    log = db.query(AutomationLog).filter(
        AutomationLog.organization_id == organization_id,
        AutomationLog.dedupe_key == dedupe_key,
    ).with_for_update().one_or_none()
    if log is not None and log.status in {"sent", "skipped"}:
        return False
    if log is not None and log.attempt_count >= MAX_ATTEMPTS:
        return False
    if log is None:
        log = AutomationLog(
            organization_id=organization_id,
            event_type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            dedupe_key=dedupe_key,
            status="failed",
            attempt_count=0,
        )
        db.add(log)
        db.flush()
    next_attempt = log.attempt_count + 1
    log.attempt_count = next_attempt
    log.last_error = None
    try:
        created = 0
        for user_id in sorted(set(recipients), key=str):
            preference = db.query(NotificationPreference).filter(
                NotificationPreference.organization_id == organization_id,
                NotificationPreference.user_id == user_id,
                NotificationPreference.category == category,
            ).one_or_none()
            if preference is not None and not preference.in_app_enabled:
                continue
            notification = create_notification(
                db,
                organization_id=organization_id,
                user_id=user_id,
                category=category,
                title=title,
                message=message,
                dedupe_key=f"{dedupe_key}:{user_id}",
                link_path=link_path,
                payload={"automation_event": event_type, "subject_id": str(subject_id)},
            )
            if notification:
                created += 1
        log.status = "sent" if created else "skipped"
        log.recipient_count = created
        log.processed_at = now
        db.commit()
        return bool(created)
    except Exception as exc:  # retry on the next cycle, bounded by MAX_ATTEMPTS
        db.rollback()
        retry_log = db.query(AutomationLog).filter(
            AutomationLog.organization_id == organization_id,
            AutomationLog.dedupe_key == dedupe_key,
        ).one_or_none()
        if retry_log is None:
            retry_log = AutomationLog(
                organization_id=organization_id, event_type=event_type, subject_type=subject_type,
                subject_id=subject_id, dedupe_key=dedupe_key, status="failed", attempt_count=next_attempt,
            )
            db.add(retry_log)
        else:
            retry_log.status = "failed"
            retry_log.last_error = str(exc)[:1900]
            retry_log.attempt_count = next_attempt
            retry_log.processed_at = now
        db.commit()
        return False


def _related_trade_record_is_active(db: Session, organization_id: UUID, entity_type: str | None, entity_id: UUID | None) -> bool:
    """Stop operational reminders once their import/export order is archived."""
    if not entity_type or entity_id is None:
        return True
    if entity_type == "import_order":
        return db.query(ImportOrder.id).filter(
            ImportOrder.id == entity_id, ImportOrder.organization_id == organization_id,
            ImportOrder.archived_at.is_(None),
        ).first() is not None
    if entity_type == "export_order":
        return db.query(ExportOrder.id).filter(
            ExportOrder.id == entity_id, ExportOrder.organization_id == organization_id,
            ExportOrder.archived_at.is_(None),
        ).first() is not None
    if entity_type == "shipment":
        import_match = db.query(ImportShipment.id).join(
            ImportOrder, (ImportOrder.id == ImportShipment.order_id) & (ImportOrder.organization_id == ImportShipment.organization_id),
        ).filter(
            ImportShipment.id == entity_id, ImportShipment.organization_id == organization_id,
            ImportOrder.archived_at.is_(None),
        ).first()
        export_match = db.query(ExportShipment.id).join(
            ExportOrder, (ExportOrder.id == ExportShipment.order_id) & (ExportOrder.organization_id == ExportShipment.organization_id),
        ).filter(
            ExportShipment.id == entity_id, ExportShipment.organization_id == organization_id,
            ExportOrder.archived_at.is_(None),
        ).first()
        return import_match is not None or export_match is not None
    return True


def _run_task_reminders(db: Session, organization_id: UUID, now: datetime) -> int:
    sent = 0
    window = now + timedelta(hours=24)
    tasks = db.query(Task).filter(
        Task.organization_id == organization_id,
        Task.status.in_(["open", "in_progress", "blocked"]),
        Task.assigned_to_user_id.isnot(None),
        Task.due_at.isnot(None),
        Task.due_at <= window,
    ).all()
    for task in tasks:
        if not _related_trade_record_is_active(db, organization_id, task.related_entity_type, task.related_entity_id):
            continue
        due_at = _utc(task.due_at)
        overdue = due_at < now
        state = "overdue" if overdue else "due-soon"
        day_key = now.date().isoformat() if overdue else due_at.date().isoformat()
        sent += _emit(
            db, organization_id=organization_id, event_type=f"task-{state}", subject_type="task", subject_id=task.id,
            dedupe_key=f"task-{state}:{task.id}:{task.due_at.isoformat()}", category="task",
            title="Task overdue" if overdue else "Task due soon",
            message=f"{task.title} is {'overdue' if overdue else 'due within 24 hours'}.",
            recipients=[task.assigned_to_user_id], link_path="/app/tasks", now=now,
        )
    return sent


def _run_invoice_reminders(db: Session, organization_id: UUID, today: date, now: datetime) -> int:
    sent = 0
    invoices = db.query(Invoice).filter(
        Invoice.organization_id == organization_id,
        Invoice.status.in_(["issued", "partially_paid"]),
        Invoice.due_date <= today + timedelta(days=7),
    ).all()
    for invoice in invoices:
        paid = db.query(func.coalesce(func.sum(PaymentAllocation.allocated_invoice_amount), 0)).join(
            Payment, (Payment.id == PaymentAllocation.payment_id) & (Payment.organization_id == PaymentAllocation.organization_id),
        ).filter(
            PaymentAllocation.organization_id == organization_id,
            PaymentAllocation.invoice_id == invoice.id,
            Payment.status == "posted",
        ).scalar()
        outstanding = max(Decimal(invoice.total_amount) - Decimal(str(paid or 0)), Decimal("0"))
        if outstanding <= 0:
            continue
        overdue = invoice.due_date < today
        state = "overdue" if overdue else "due-soon"
        day_key = today.isoformat() if overdue else invoice.due_date.isoformat()
        sent += _emit(
            db, organization_id=organization_id, event_type=f"invoice-{state}", subject_type="invoice", subject_id=invoice.id,
            dedupe_key=f"invoice-{state}:{invoice.id}:{invoice.due_date.isoformat()}", category="invoice",
            title="Invoice payment overdue" if overdue else "Invoice due soon",
            message=f"Invoice {invoice.invoice_number} has {outstanding:.2f} {invoice.currency} outstanding and is {'overdue' if overdue else 'due within 7 days'}.",
            recipients=_recipients(db, organization_id, FINANCE_ROLES), link_path="/app/invoices", now=now,
        )
    return sent


def _run_delayed_shipments(db: Session, organization_id: UUID, today: date, now: datetime) -> int:
    """Alert on delayed/past-ETA shipments and ETAs due within the next 72 hours."""
    sent = 0
    cutoff = today + timedelta(days=3)
    shipment_sources = (
        (ImportShipment, ImportOrder, "import", IMPORT_ROLES, {"arrived", "cancelled", "delivered"}),
        (ExportShipment, ExportOrder, "export", EXPORT_ROLES, {"delivered", "cancelled"}),
    )
    for model, order_model, prefix, roles, terminal_statuses in shipment_sources:
        shipments = db.query(model).join(
            order_model, (order_model.id == model.order_id) & (order_model.organization_id == model.organization_id),
        ).filter(model.organization_id == organization_id, order_model.archived_at.is_(None)).all()
        for shipment in shipments:
            eta = shipment.estimated_arrival
            status_value = shipment.status
            if status_value in terminal_statuses:
                continue
            if status_value == "delayed":
                state = "delayed"
            elif eta is not None and eta < today:
                state = "overdue"
            elif eta is not None and today <= eta <= cutoff:
                state = "due-soon"
            else:
                continue

            if state == "due-soon":
                title = "Shipment arrival approaching"
                message = f"Shipment {shipment.shipment_reference} is expected to arrive on {eta.isoformat()}."
            else:
                title = "Shipment needs attention"
                reason = "marked delayed" if state == "delayed" else "past its estimated arrival date"
                message = f"Shipment {shipment.shipment_reference} is {reason}."
            eta_key = eta.isoformat() if eta else "no-eta"
            sent += _emit(
                db, organization_id=organization_id, event_type=f"{prefix}-shipment-{state}",
                subject_type=f"{prefix}_shipment", subject_id=shipment.id,
                dedupe_key=f"{prefix}-shipment-{state}:{shipment.id}:{eta_key}", category="shipment",
                title=title, message=message,
                recipients=_recipients(db, organization_id, roles), link_path="/app/shipments", now=now,
            )
    return sent


def _run_pending_approval_reminders(db: Session, organization_id: UUID, now: datetime) -> int:
    """Send one reminder for requests that have remained pending for at least 24 hours."""
    sent = 0
    reminder_before = now - timedelta(hours=24)
    requests = db.query(ApprovalRequest).filter(
        ApprovalRequest.organization_id == organization_id,
        ApprovalRequest.status == "submitted",
        ApprovalRequest.submitted_at <= reminder_before,
    ).all()
    for approval in requests:
        if not _related_trade_record_is_active(db, organization_id, approval.related_entity_type, approval.related_entity_id):
            continue
        roles, enabled, _ = get_approval_roles(db, organization_id, approval.business_action)
        if not enabled:
            continue
        recipients = _recipients(db, organization_id, set(roles))
        recipients = [recipient for recipient in recipients if recipient != approval.requested_by_user_id]
        if approval.related_entity_type == "import_order":
            link_path = "/app/imports"
        elif approval.related_entity_type == "export_order":
            link_path = "/app/exports"
        else:
            link_path = "/app/approvals"
        sent += _emit(
            db, organization_id=organization_id, event_type="pending-approval-reminder",
            subject_type="approval_request", subject_id=approval.id,
            dedupe_key=f"pending-approval:{approval.id}:{_utc(approval.submitted_at).isoformat()}",
            category="approval", title="Approval request is still pending",
            message=f"{approval.title} has been awaiting a decision for at least 24 hours.",
            recipients=recipients, link_path=link_path, now=now,
        )
    return sent


def _run_low_stock(db: Session, organization_id: UUID, today: date, now: datetime) -> int:
    sent = 0
    rows = db.query(InventoryBalance, Product).join(
        Product, (Product.id == InventoryBalance.product_id) & (Product.organization_id == InventoryBalance.organization_id),
    ).filter(InventoryBalance.organization_id == organization_id, Product.is_active.is_(True)).all()
    for balance, product in rows:
        available = Decimal(balance.quantity_on_hand) - Decimal(balance.reserved_quantity)
        if available > Decimal(product.reorder_threshold):
            continue
        sent += _emit(
            db, organization_id=organization_id, event_type="low-stock", subject_type="inventory_balance", subject_id=balance.id,
            dedupe_key=f"low-stock:{balance.id}:{_utc(balance.updated_at).isoformat()}", category="inventory",
            title="Low inventory alert", message=f"{product.name} ({product.sku}) has {available} available; reorder threshold is {product.reorder_threshold}.",
            recipients=_recipients(db, organization_id, INVENTORY_ROLES), link_path="/app/inventory", now=now,
        )
    return sent


def _run_expiring_documents(db: Session, organization_id: UUID, today: date, now: datetime) -> int:
    sent = 0
    cutoff = today + timedelta(days=30)
    documents = db.query(TradeDocument).filter(
        TradeDocument.organization_id == organization_id,
        TradeDocument.expiry_date.isnot(None),
        TradeDocument.expiry_date <= cutoff,
    ).all()
    for document in documents:
        if document.related_entity_type == "import_order":
            active_record = db.query(ImportOrder.id).filter(ImportOrder.id == document.related_entity_id, ImportOrder.organization_id == organization_id, ImportOrder.archived_at.is_(None)).first()
            if not active_record:
                continue
        elif document.related_entity_type == "export_order":
            active_record = db.query(ExportOrder.id).filter(ExportOrder.id == document.related_entity_id, ExportOrder.organization_id == organization_id, ExportOrder.archived_at.is_(None)).first()
            if not active_record:
                continue
        elif document.related_entity_type == "import_shipment":
            active_record = db.query(ImportShipment.id).join(ImportOrder, (ImportOrder.id == ImportShipment.order_id) & (ImportOrder.organization_id == ImportShipment.organization_id)).filter(ImportShipment.id == document.related_entity_id, ImportShipment.organization_id == organization_id, ImportOrder.archived_at.is_(None)).first()
            if not active_record:
                continue
        elif document.related_entity_type == "export_shipment":
            active_record = db.query(ExportShipment.id).join(ExportOrder, (ExportOrder.id == ExportShipment.order_id) & (ExportOrder.organization_id == ExportShipment.organization_id)).filter(ExportShipment.id == document.related_entity_id, ExportShipment.organization_id == organization_id, ExportOrder.archived_at.is_(None)).first()
            if not active_record:
                continue
        roles = IMPORT_ROLES if document.related_entity_type.startswith("import") else EXPORT_ROLES
        expiry_state = "expired" if document.expiry_date < today else "expiring"
        sent += _emit(
            db, organization_id=organization_id, event_type=f"document-{expiry_state}", subject_type="document", subject_id=document.id,
            dedupe_key=f"document-{expiry_state}:{document.id}:{document.expiry_date.isoformat()}:{document.updated_at.isoformat()}", category="document",
            title="Trade document expired" if expiry_state == "expired" else "Trade document expiring",
            message=f"{document.title} ({document.document_reference}) {'expired' if expiry_state == 'expired' else f'expires on {document.expiry_date.isoformat()}' }.",
            recipients=_recipients(db, organization_id, roles), link_path="/app/documents", now=now,
        )
    return sent


def _run_missing_documents(db: Session, organization_id: UUID, today: date, now: datetime) -> int:
    sent = 0
    requirements = db.query(DocumentRequirement).filter(
        DocumentRequirement.organization_id == organization_id,
        DocumentRequirement.is_required.is_(True),
    ).all()
    for requirement in requirements:
        if requirement.related_entity_type == "import_order":
            active_record = db.query(ImportOrder.id).filter(ImportOrder.id == requirement.related_entity_id, ImportOrder.organization_id == organization_id, ImportOrder.archived_at.is_(None)).first()
            if not active_record:
                continue
        elif requirement.related_entity_type == "export_order":
            active_record = db.query(ExportOrder.id).filter(ExportOrder.id == requirement.related_entity_id, ExportOrder.organization_id == organization_id, ExportOrder.archived_at.is_(None)).first()
            if not active_record:
                continue
        elif requirement.related_entity_type == "import_shipment":
            active_record = db.query(ImportShipment.id).join(ImportOrder, (ImportOrder.id == ImportShipment.order_id) & (ImportOrder.organization_id == ImportShipment.organization_id)).filter(ImportShipment.id == requirement.related_entity_id, ImportShipment.organization_id == organization_id, ImportOrder.archived_at.is_(None)).first()
            if not active_record:
                continue
        elif requirement.related_entity_type == "export_shipment":
            active_record = db.query(ExportShipment.id).join(ExportOrder, (ExportOrder.id == ExportShipment.order_id) & (ExportOrder.organization_id == ExportShipment.organization_id)).filter(ExportShipment.id == requirement.related_entity_id, ExportShipment.organization_id == organization_id, ExportOrder.archived_at.is_(None)).first()
            if not active_record:
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
        roles = IMPORT_ROLES if requirement.related_entity_type.startswith("import") else EXPORT_ROLES
        sent += _emit(
            db, organization_id=organization_id, event_type="missing-required-document", subject_type="document_requirement", subject_id=requirement.id,
            dedupe_key=f"missing-document:{requirement.id}", category="document",
            title="Required document missing", message=f"{requirement.label} is required but no verified document is attached.",
            recipients=_recipients(db, organization_id, roles), link_path="/app/documents", now=now,
        )
    return sent


def run_automation_cycle(db: Session, now: datetime | None = None, organization_id: UUID | None = None) -> dict[str, int]:
    """Run all configured in-app reminder checks. Safe to call repeatedly."""
    resolved_now = _utc(now or datetime.now(timezone.utc))
    today = resolved_now.date()
    totals = {"task_reminders": 0, "pending_approval_reminders": 0, "invoice_reminders": 0, "shipment_alerts": 0, "low_stock_alerts": 0, "document_expiry_alerts": 0, "missing_document_alerts": 0}
    organization_query = db.query(Organization.id)
    if organization_id is not None:
        organization_query = organization_query.filter(Organization.id == organization_id)
    organization_ids = [row[0] for row in organization_query.all()]
    for organization_id in organization_ids:
        totals["task_reminders"] += _run_task_reminders(db, organization_id, resolved_now)
        totals["pending_approval_reminders"] += _run_pending_approval_reminders(db, organization_id, resolved_now)
        totals["invoice_reminders"] += _run_invoice_reminders(db, organization_id, today, resolved_now)
        totals["shipment_alerts"] += _run_delayed_shipments(db, organization_id, today, resolved_now)
        totals["low_stock_alerts"] += _run_low_stock(db, organization_id, today, resolved_now)
        totals["document_expiry_alerts"] += _run_expiring_documents(db, organization_id, today, resolved_now)
        totals["missing_document_alerts"] += _run_missing_documents(db, organization_id, today, resolved_now)
    return totals
