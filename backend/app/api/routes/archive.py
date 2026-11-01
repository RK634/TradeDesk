"""Retention-aware archive and restore operations for finalized trade orders."""
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.core.security import utc_now, verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import ArchiveEvent, Customer, ExportOrder, ImportOrder, Supplier, User, UserSession
from app.schemas.archive import ArchiveEventOut, ArchivePage, ArchiveRecordOut, ArchiveRequest

router = APIRouter(prefix="/archive", tags=["archive"])


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _get_record(db: Session, organization_id: UUID, record_type: str, record_id: UUID, *, lock: bool = False):
    if record_type == "import_order":
        query = db.query(ImportOrder).filter(ImportOrder.id == record_id, ImportOrder.organization_id == organization_id)
        if lock:
            query = query.with_for_update()
        order = query.one_or_none()
        if order is None:
            raise HTTPException(status_code=404, detail="Import order not found.")
        return order, "received"
    if record_type == "export_order":
        query = db.query(ExportOrder).filter(ExportOrder.id == record_id, ExportOrder.organization_id == organization_id)
        if lock:
            query = query.with_for_update()
        order = query.one_or_none()
        if order is None:
            raise HTTPException(status_code=404, detail="Export order not found.")
        return order, "delivered"
    raise HTTPException(status_code=422, detail="Only import_order and export_order records can be archived.")


def _archive_payload(record_type: str, order, partner_name: str) -> dict:
    return {
        "record_id": order.id,
        "record_type": record_type,
        "reference": order.reference,
        "status": order.status,
        "partner_name": partner_name,
        "currency": order.currency,
        "archived_at": order.archived_at,
        "archived_by_user_id": order.archived_by_user_id,
        "archive_reason": order.archive_reason,
        "created_at": order.created_at,
    }


@router.get("", response_model=ArchivePage, summary="List archived import and export orders")
def list_archived_records(
    organization_id: UUID,
    record_type: str | None = Query(default=None, pattern="^(import_order|export_order)$"),
    search: str | None = Query(default=None, max_length=160),
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ArchivePage:
    require_org_permission(db, user.id, organization_id, "archive.read")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    from_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc) if start_date else None
    to_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc) if end_date else None
    search_pattern = f"%{search.strip()}%" if search and search.strip() else None
    results: list[dict] = []
    total = 0
    take = page * page_size

    if record_type in (None, "import_order"):
        query = db.query(ImportOrder, Supplier.name).join(
            Supplier, (Supplier.id == ImportOrder.supplier_id) & (Supplier.organization_id == organization_id),
        ).filter(ImportOrder.organization_id == organization_id, ImportOrder.archived_at.isnot(None))
        if from_dt:
            query = query.filter(ImportOrder.archived_at >= from_dt)
        if to_dt:
            query = query.filter(ImportOrder.archived_at < to_dt)
        if search_pattern:
            query = query.filter(ImportOrder.reference.ilike(search_pattern) | Supplier.name.ilike(search_pattern))
        total += query.count()
        for order, partner_name in query.order_by(ImportOrder.archived_at.desc()).limit(take).all():
            results.append(_archive_payload("import_order", order, partner_name))

    if record_type in (None, "export_order"):
        query = db.query(ExportOrder, Customer.name).join(
            Customer, (Customer.id == ExportOrder.customer_id) & (Customer.organization_id == organization_id),
        ).filter(ExportOrder.organization_id == organization_id, ExportOrder.archived_at.isnot(None))
        if from_dt:
            query = query.filter(ExportOrder.archived_at >= from_dt)
        if to_dt:
            query = query.filter(ExportOrder.archived_at < to_dt)
        if search_pattern:
            query = query.filter(ExportOrder.reference.ilike(search_pattern) | Customer.name.ilike(search_pattern))
        total += query.count()
        for order, partner_name in query.order_by(ExportOrder.archived_at.desc()).limit(take).all():
            results.append(_archive_payload("export_order", order, partner_name))

    results.sort(key=lambda item: item["archived_at"], reverse=True)
    start = (page - 1) * page_size
    items = [ArchiveRecordOut.model_validate(item) for item in results[start:start + page_size]]
    return ArchivePage(items=items, total=total, page=page, page_size=page_size)


@router.get("/eligible", response_model=ArchivePage, summary="List completed or cancelled orders eligible for archiving")
def list_archive_eligible_records(
    organization_id: UUID,
    record_type: str | None = Query(default=None, pattern="^(import_order|export_order)$"),
    search: str | None = Query(default=None, max_length=160),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ArchivePage:
    require_org_permission(db, user.id, organization_id, "orders.archive")
    search_pattern = f"%{search.strip()}%" if search and search.strip() else None
    take = page * page_size
    total = 0
    results: list[dict] = []
    if record_type in (None, "import_order"):
        query = db.query(ImportOrder, Supplier.name).join(
            Supplier, (Supplier.id == ImportOrder.supplier_id) & (Supplier.organization_id == organization_id),
        ).filter(
            ImportOrder.organization_id == organization_id, ImportOrder.archived_at.is_(None),
            ImportOrder.status.in_(["received", "cancelled"]),
        )
        if search_pattern:
            query = query.filter(ImportOrder.reference.ilike(search_pattern) | Supplier.name.ilike(search_pattern))
        total += query.count()
        for order, partner_name in query.order_by(ImportOrder.updated_at.desc()).limit(take).all():
            results.append(_archive_payload("import_order", order, partner_name))
    if record_type in (None, "export_order"):
        query = db.query(ExportOrder, Customer.name).join(
            Customer, (Customer.id == ExportOrder.customer_id) & (Customer.organization_id == organization_id),
        ).filter(
            ExportOrder.organization_id == organization_id, ExportOrder.archived_at.is_(None),
            ExportOrder.status.in_(["delivered", "cancelled"]),
        )
        if search_pattern:
            query = query.filter(ExportOrder.reference.ilike(search_pattern) | Customer.name.ilike(search_pattern))
        total += query.count()
        for order, partner_name in query.order_by(ExportOrder.updated_at.desc()).limit(take).all():
            results.append(_archive_payload("export_order", order, partner_name))
    results.sort(key=lambda item: item["created_at"], reverse=True)
    start = (page - 1) * page_size
    return ArchivePage(
        items=[ArchiveRecordOut.model_validate(item) for item in results[start:start + page_size]],
        total=total, page=page, page_size=page_size,
    )


@router.post("/{record_type}/{record_id}", response_model=ArchiveRecordOut, summary="Archive a completed or cancelled order")
def archive_record(
    record_type: str,
    record_id: UUID,
    organization_id: UUID,
    payload: ArchiveRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ArchiveRecordOut:
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "orders.archive")
    order, completed_status = _get_record(db, organization_id, record_type, record_id, lock=True)
    if order.archived_at is not None:
        raise HTTPException(status_code=409, detail="This order is already archived.")
    eligible = {completed_status, "cancelled"}
    if order.status not in eligible:
        raise HTTPException(status_code=409, detail=f"Only {completed_status} or cancelled orders can be archived.")

    now = utc_now()
    order.archived_at = now
    order.archived_by_user_id = user.id
    order.archive_reason = payload.reason
    partner_name = (
        db.query(Supplier.name).filter(Supplier.id == order.supplier_id, Supplier.organization_id == organization_id).scalar()
        if record_type == "import_order"
        else db.query(Customer.name).filter(Customer.id == order.customer_id, Customer.organization_id == organization_id).scalar()
    ) or "Unknown partner"
    db.add(ArchiveEvent(
        organization_id=organization_id, record_type=record_type, record_id=order.id,
        record_reference=order.reference, action="archived", reason=payload.reason,
        actor_user_id=user.id, created_at=now,
    ))
    db.commit()
    db.refresh(order)
    return ArchiveRecordOut.model_validate(_archive_payload(record_type, order, partner_name))


@router.post("/{record_type}/{record_id}/restore", response_model=ArchiveRecordOut, summary="Restore an archived order")
def restore_record(
    record_type: str,
    record_id: UUID,
    organization_id: UUID,
    payload: ArchiveRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ArchiveRecordOut:
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "orders.restore")
    order, _ = _get_record(db, organization_id, record_type, record_id, lock=True)
    if order.archived_at is None:
        raise HTTPException(status_code=409, detail="This order is not currently archived.")
    partner_name = (
        db.query(Supplier.name).filter(Supplier.id == order.supplier_id, Supplier.organization_id == organization_id).scalar()
        if record_type == "import_order"
        else db.query(Customer.name).filter(Customer.id == order.customer_id, Customer.organization_id == organization_id).scalar()
    ) or "Unknown partner"
    previous_reason = order.archive_reason or "Archive restored"
    order.archived_at = None
    order.archived_by_user_id = None
    order.archive_reason = None
    now = utc_now()
    db.add(ArchiveEvent(
        organization_id=organization_id, record_type=record_type, record_id=order.id,
        record_reference=order.reference, action="restored", reason=payload.reason or previous_reason,
        actor_user_id=user.id, created_at=now,
    ))
    db.commit()
    db.refresh(order)
    return ArchiveRecordOut.model_validate(_archive_payload(record_type, order, partner_name))


@router.get("/{record_type}/{record_id}/history", response_model=list[ArchiveEventOut], summary="Get archive and restore history")
def archive_history(
    record_type: str,
    record_id: UUID,
    organization_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ArchiveEventOut]:
    require_org_permission(db, user.id, organization_id, "archive.read")
    _get_record(db, organization_id, record_type, record_id)
    rows = db.query(ArchiveEvent).filter(
        ArchiveEvent.organization_id == organization_id,
        ArchiveEvent.record_type == record_type,
        ArchiveEvent.record_id == record_id,
    ).order_by(ArchiveEvent.created_at.asc()).all()
    return [ArchiveEventOut.model_validate(row) for row in rows]
