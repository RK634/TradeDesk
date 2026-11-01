"""Organization-scoped import orders, approvals, shipments, goods receipts and documents."""

import hashlib
import json
import logging
import mimetypes
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path, PurePath
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.config import get_settings
from app.core.permissions import require_org_permission
from app.core.security import utc_now, verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import (
    ImportDocument, ImportGoodsReceipt, ImportGoodsReceiptItem, ImportOrder,
    ImportOrderItem, ImportOrderStatusHistory, ImportShipment,
    ImportShipmentMilestone, InventoryBalance, InventoryLocation,
    InventoryMovement, OrganizationMembership, Product, Supplier, User, UserSession,
)
from app.schemas.imports import (
    DocumentVerificationStatus, GoodsReceiptCreate, GoodsReceiptOut,
    ImportCostUpdate, ImportDocumentOut, ImportDocumentUpdate, ImportItemCreate,
    ImportItemOut, ImportItemUpdate, ImportOrderCreate, ImportOrderOut,
    ImportOrderPage, ImportOrderUpdate, ImportShipmentCreate, ImportShipmentOut,
    ImportShipmentUpdate, ImportStatus, RejectImportRequest, ShipmentMilestoneCreate,
    ShipmentMilestoneOut, ShipmentStatus,
)
from app.schemas.inventory import InventoryMovementType
from app.storage import LocalPrivateStorage, StorageError, get_storage
from app.schemas.master_data import Page

from app.services.workflow import assert_order_approval_role, sync_order_approval

router = APIRouter(prefix="/imports", tags=["imports"])
logger = logging.getLogger(__name__)
ZERO = Decimal("0")
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".docx", ".csv", ".txt"}
DOCUMENT_TYPES = {
    "commercial_invoice", "packing_list", "bill_of_lading", "air_waybill",
    "certificate_of_origin", "insurance_certificate", "customs_declaration",
    "inspection_certificate", "product_certificate", "import_permit", "purchase_order", "other",
}
SHIPMENT_TRANSITIONS = {
    "planned": {"planned", "in_transit", "delayed", "cancelled"},
    "in_transit": {"in_transit", "arrived", "delayed", "cancelled"},
    "delayed": {"delayed", "in_transit", "arrived", "cancelled"},
    "arrived": {"arrived", "delivered"},
    "delivered": {"delivered"},
    "cancelled": {"cancelled"},
}


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _utc_now() -> datetime:
    return utc_now()


def _scoped_order(db: Session, user_id: UUID, organization_id: UUID, order_id: UUID, permission: str = "imports.read", *, lock: bool = False) -> ImportOrder:
    require_org_permission(db, user_id, organization_id, permission)
    query = db.query(ImportOrder).filter(
        ImportOrder.id == order_id,
        ImportOrder.organization_id == organization_id,
    )
    if lock:
        query = query.with_for_update()
    order = query.one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Import order not found.")
    return order


def _validate_supplier(db: Session, organization_id: UUID, supplier_id: UUID) -> Supplier:
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.organization_id == organization_id,
        Supplier.is_active.is_(True),
    ).one_or_none()
    if supplier is None:
        raise HTTPException(status_code=422, detail="Select an active supplier in this organization.")
    return supplier


def _validate_assignee(db: Session, organization_id: UUID, user_id: UUID | None) -> None:
    if user_id is None:
        return
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.is_active.is_(True),
    ).one_or_none()
    if membership is None:
        raise HTTPException(status_code=422, detail="Assigned user must be an active member of this organization.")


def _active_product(db: Session, organization_id: UUID, product_id: UUID) -> Product:
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.organization_id == organization_id,
        Product.is_active.is_(True),
    ).one_or_none()
    if product is None:
        raise HTTPException(status_code=422, detail="Every import line must reference an active product in this organization.")
    return product


def _add_history(db: Session, order: ImportOrder, actor_id: UUID, new_status: str, reason: str | None = None) -> None:
    db.add(ImportOrderStatusHistory(
        organization_id=order.organization_id,
        order_id=order.id,
        from_status=order.status,
        to_status=new_status,
        reason=reason,
        actor_user_id=actor_id,
        created_at=_utc_now(),
    ))
    order.status = new_status


def _item_payload(item: ImportOrderItem) -> dict:
    remaining = max(item.quantity_ordered - item.quantity_received, ZERO)
    return {
        "id": item.id,
        "organization_id": item.organization_id,
        "order_id": item.order_id,
        "line_number": item.line_number,
        "product_id": item.product_id,
        "product_sku_snapshot": item.product_sku_snapshot,
        "product_name_snapshot": item.product_name_snapshot,
        "description": item.description,
        "quantity_ordered": item.quantity_ordered,
        "quantity_received": item.quantity_received,
        "quantity_remaining": remaining,
        "unit_price": item.unit_price,
        "line_total": item.quantity_ordered * item.unit_price,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _order_payload(db: Session, order: ImportOrder) -> dict:
    supplier = db.query(Supplier).filter(
        Supplier.id == order.supplier_id,
        Supplier.organization_id == order.organization_id,
    ).one()
    items = db.query(ImportOrderItem).filter(
        ImportOrderItem.order_id == order.id,
        ImportOrderItem.organization_id == order.organization_id,
    ).order_by(ImportOrderItem.line_number.asc()).all()
    history = db.query(ImportOrderStatusHistory).filter(
        ImportOrderStatusHistory.order_id == order.id,
        ImportOrderStatusHistory.organization_id == order.organization_id,
    ).order_by(ImportOrderStatusHistory.created_at.asc()).all()
    goods_total = sum((item.quantity_ordered * item.unit_price for item in items), ZERO)
    estimate_costs = order.estimated_freight_cost + order.estimated_insurance_cost + order.estimated_duties + order.estimated_other_costs
    actual_costs = order.actual_freight_cost + order.actual_insurance_cost + order.actual_duties + order.actual_other_costs
    return {
        "id": order.id,
        "organization_id": order.organization_id,
        "reference": order.reference,
        "supplier_id": order.supplier_id,
        "supplier_name": supplier.name,
        "status": order.status,
        "currency": order.currency,
        "purchase_terms": order.purchase_terms,
        "country_of_origin": order.country_of_origin,
        "destination": order.destination,
        "estimated_departure_date": order.estimated_departure_date,
        "estimated_arrival_date": order.estimated_arrival_date,
        "actual_departure_date": order.actual_departure_date,
        "actual_arrival_date": order.actual_arrival_date,
        "estimated_freight_cost": order.estimated_freight_cost,
        "estimated_insurance_cost": order.estimated_insurance_cost,
        "estimated_duties": order.estimated_duties,
        "estimated_other_costs": order.estimated_other_costs,
        "estimated_goods_total": goods_total,
        "estimated_total_cost": goods_total + estimate_costs,
        "actual_freight_cost": order.actual_freight_cost,
        "actual_insurance_cost": order.actual_insurance_cost,
        "actual_duties": order.actual_duties,
        "actual_other_costs": order.actual_other_costs,
        "actual_total_cost": goods_total + actual_costs,
        "assigned_user_id": order.assigned_user_id,
        "notes": order.notes,
        "created_by_user_id": order.created_by_user_id,
        "submitted_at": order.submitted_at,
        "approved_by_user_id": order.approved_by_user_id,
        "approved_at": order.approved_at,
        "rejection_reason": order.rejection_reason,
        "archived_at": order.archived_at,
        "archived_by_user_id": order.archived_by_user_id,
        "archive_reason": order.archive_reason,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": [_item_payload(item) for item in items],
        "status_history": history,
    }


def _order_out(db: Session, order: ImportOrder) -> ImportOrderOut:
    return ImportOrderOut.model_validate(_order_payload(db, order))


def _find_item(db: Session, order: ImportOrder, item_id: UUID, *, lock: bool = False) -> ImportOrderItem:
    query = db.query(ImportOrderItem).filter(
        ImportOrderItem.id == item_id,
        ImportOrderItem.order_id == order.id,
        ImportOrderItem.organization_id == order.organization_id,
    )
    if lock:
        query = query.with_for_update()
    item = query.one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Import order line not found.")
    return item


def _assert_editable(order: ImportOrder) -> None:
    if order.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="Order lines and planning fields can only be changed while the order is draft or returned for correction.")


def _receipt_payload(db: Session, receipt: ImportGoodsReceipt) -> dict:
    rows = db.query(ImportGoodsReceiptItem, ImportOrderItem).join(
        ImportOrderItem,
        (ImportOrderItem.id == ImportGoodsReceiptItem.order_item_id)
        & (ImportOrderItem.order_id == ImportGoodsReceiptItem.order_id)
        & (ImportOrderItem.organization_id == ImportGoodsReceiptItem.organization_id),
    ).filter(
        ImportGoodsReceiptItem.receipt_id == receipt.id,
        ImportGoodsReceiptItem.organization_id == receipt.organization_id,
    ).all()
    items = []
    for receipt_item, order_item in rows:
        items.append({
            "id": receipt_item.id,
            "order_id": receipt_item.order_id,
            "receipt_id": receipt_item.receipt_id,
            "order_item_id": receipt_item.order_item_id,
            "quantity_received": receipt_item.quantity_received,
            "product_id": order_item.product_id,
            "product_sku": order_item.product_sku_snapshot,
            "product_name": order_item.product_name_snapshot,
        })
    return {
        "id": receipt.id,
        "organization_id": receipt.organization_id,
        "order_id": receipt.order_id,
        "location_id": receipt.location_id,
        "receipt_reference": receipt.receipt_reference,
        "idempotency_key": receipt.idempotency_key,
        "received_at": receipt.received_at,
        "notes": receipt.notes,
        "received_by_user_id": receipt.received_by_user_id,
        "items": items,
    }


def _request_hash(order_id: UUID, payload: GoodsReceiptCreate) -> str:
    material = {
        "order_id": str(order_id),
        "location_id": str(payload.location_id),
        "receipt_reference": payload.receipt_reference,
        "notes": payload.notes,
        "items": sorted(
            [{"order_item_id": str(item.order_item_id), "quantity_received": format(item.quantity_received, "f")} for item in payload.items],
            key=lambda row: row["order_item_id"],
        ),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _scoped_document(db: Session, order: ImportOrder, document_id: UUID) -> ImportDocument:
    document = db.query(ImportDocument).filter(
        ImportDocument.id == document_id,
        ImportDocument.order_id == order.id,
        ImportDocument.organization_id == order.organization_id,
    ).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Import document not found.")
    return document


def _legacy_document_storage():
    """Preserve test/local path overrides while routing production through S3."""
    settings = get_settings()
    if getattr(settings, "storage_backend", "local") == "s3":
        return get_storage()
    return LocalPrivateStorage(settings.private_storage_dir)


@router.get("", response_model=ImportOrderPage, summary="List import orders")
def list_import_orders(
    organization_id: UUID,
    search: str | None = None,
    order_status: ImportStatus | None = Query(default=None, alias="status"),
    supplier_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "imports.read")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    query = db.query(ImportOrder).join(Supplier, Supplier.id == ImportOrder.supplier_id).filter(
        ImportOrder.organization_id == organization_id,
        ImportOrder.archived_at.is_(None),
        Supplier.organization_id == organization_id,
    )
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(ImportOrder.reference.ilike(pattern), Supplier.name.ilike(pattern)))
    if order_status:
        query = query.filter(ImportOrder.status == order_status.value)
    if supplier_id:
        query = query.filter(ImportOrder.supplier_id == supplier_id)
    if start_date:
        query = query.filter(ImportOrder.created_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc))
    if end_date:
        query = query.filter(ImportOrder.created_at < datetime.combine(end_date.fromordinal(end_date.toordinal() + 1), datetime.min.time(), tzinfo=timezone.utc))
    total = query.count()
    orders = query.order_by(ImportOrder.updated_at.desc(), ImportOrder.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_order_out(db, order) for order in orders], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ImportOrderOut, status_code=status.HTTP_201_CREATED, summary="Create a draft import order")
def create_import_order(
    organization_id: UUID,
    payload: ImportOrderCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "imports.create")
    supplier = _validate_supplier(db, organization_id, payload.supplier_id)
    _validate_assignee(db, organization_id, payload.assigned_user_id)
    order_id = uuid4()
    order = ImportOrder(
        id=order_id,
        organization_id=organization_id,
        reference=f"IMP-{date.today():%Y%m%d}-{order_id.hex[:6].upper()}",
        supplier_id=supplier.id,
        status="draft",
        currency=payload.currency or supplier.currency,
        purchase_terms=payload.purchase_terms,
        country_of_origin=payload.country_of_origin,
        destination=payload.destination,
        estimated_departure_date=payload.estimated_departure_date,
        estimated_arrival_date=payload.estimated_arrival_date,
        estimated_freight_cost=payload.estimated_freight_cost,
        estimated_insurance_cost=payload.estimated_insurance_cost,
        estimated_duties=payload.estimated_duties,
        estimated_other_costs=payload.estimated_other_costs,
        assigned_user_id=payload.assigned_user_id,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    db.add(order)
    db.flush()
    db.add(ImportOrderStatusHistory(
        organization_id=organization_id, order_id=order.id, from_status=None,
        to_status="draft", reason="Import order created", actor_user_id=user.id,
    ))
    try:
        for index, item_payload in enumerate(payload.items, start=1):
            product = _active_product(db, organization_id, item_payload.product_id)
            db.add(ImportOrderItem(
                organization_id=organization_id,
                order_id=order.id,
                line_number=index,
                product_id=product.id,
                product_sku_snapshot=product.sku,
                product_name_snapshot=product.name,
                description=item_payload.description,
                quantity_ordered=item_payload.quantity_ordered,
                quantity_received=ZERO,
                unit_price=item_payload.unit_price,
            ))
        db.commit()
        db.refresh(order)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create the import order because a related record changed or the reference conflicted.") from exc
    return _order_out(db, order)


@router.get("/{order_id}", response_model=ImportOrderOut, summary="Get import order details")
def get_import_order(order_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _scoped_order(db, user.id, organization_id, order_id)
    return _order_out(db, order)


@router.patch("/{order_id}", response_model=ImportOrderOut, summary="Update draft import order planning details")
def update_import_order(
    order_id: UUID,
    organization_id: UUID,
    payload: ImportOrderUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.update", lock=True)
    _assert_editable(order)
    values = payload.model_dump(exclude_unset=True)
    if "assigned_user_id" in values:
        _validate_assignee(db, organization_id, values["assigned_user_id"])
    departure = values.get("estimated_departure_date", order.estimated_departure_date)
    arrival = values.get("estimated_arrival_date", order.estimated_arrival_date)
    if departure and arrival and arrival < departure:
        raise HTTPException(status_code=422, detail="Estimated arrival cannot be before estimated departure.")
    for key, value in values.items():
        setattr(order, key, value)
    try:
        db.commit()
        db.refresh(order)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Import order update conflicted with another change.") from exc
    return _order_out(db, order)


@router.post("/{order_id}/items", response_model=ImportItemOut, status_code=status.HTTP_201_CREATED, summary="Add a line to a draft import order")
def add_import_order_item(
    order_id: UUID,
    organization_id: UUID,
    payload: ImportItemCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.update", lock=True)
    _assert_editable(order)
    product = _active_product(db, organization_id, payload.product_id)
    next_line = (db.query(func.max(ImportOrderItem.line_number)).filter(ImportOrderItem.order_id == order.id, ImportOrderItem.organization_id == organization_id).scalar() or 0) + 1
    item = ImportOrderItem(
        organization_id=organization_id, order_id=order.id, line_number=next_line,
        product_id=product.id, product_sku_snapshot=product.sku, product_name_snapshot=product.name,
        description=payload.description, quantity_ordered=payload.quantity_ordered,
        quantity_received=ZERO, unit_price=payload.unit_price,
    )
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not add the import order line.") from exc
    return _item_payload(item)


@router.patch("/{order_id}/items/{item_id}", response_model=ImportItemOut, summary="Update a draft import line")
def update_import_order_item(
    order_id: UUID,
    item_id: UUID,
    organization_id: UUID,
    payload: ImportItemUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.update", lock=True)
    _assert_editable(order)
    item = _find_item(db, order, item_id, lock=True)
    values = payload.model_dump(exclude_unset=True)
    if "quantity_ordered" in values and values["quantity_ordered"] < item.quantity_received:
        raise HTTPException(status_code=422, detail="Ordered quantity cannot be below the quantity already received.")
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return _item_payload(item)


@router.delete("/{order_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a draft import line")
def delete_import_order_item(
    order_id: UUID,
    item_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.update", lock=True)
    _assert_editable(order)
    item = _find_item(db, order, item_id, lock=True)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{order_id}/submit", response_model=ImportOrderOut, summary="Submit an import order for approval")
def submit_import_order(
    order_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.submit", lock=True)
    if order.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="Only draft or rejected import orders can be submitted.")
    count = db.query(func.count(ImportOrderItem.id)).filter(ImportOrderItem.order_id == order.id, ImportOrderItem.organization_id == organization_id).scalar() or 0
    if count < 1:
        raise HTTPException(status_code=409, detail="Add at least one product line before submitting the order.")
    order.submitted_at = _utc_now()
    order.rejection_reason = None
    _add_history(db, order, user.id, "submitted")
    sync_order_approval(db, organization_id=organization_id, action="import_order", order_id=order.id, actor_id=user.id, transition="submitted", title=f"Import order {order.reference}")
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.post("/{order_id}/approve", response_model=ImportOrderOut, summary="Approve a submitted import order")
def approve_import_order(
    order_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.approve", lock=True)
    if order.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted import orders can be approved.")
    assert_order_approval_role(db, organization_id, user.id, "import_order", order.id)
    order.approved_by_user_id = user.id
    order.approved_at = _utc_now()
    order.rejection_reason = None
    _add_history(db, order, user.id, "approved")
    sync_order_approval(db, organization_id=organization_id, action="import_order", order_id=order.id, actor_id=user.id, transition="approved")
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.post("/{order_id}/reject", response_model=ImportOrderOut, summary="Reject an import order with a reason")
def reject_import_order(
    order_id: UUID,
    organization_id: UUID,
    payload: RejectImportRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.approve", lock=True)
    if order.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted import orders can be rejected.")
    assert_order_approval_role(db, organization_id, user.id, "import_order", order.id)
    order.rejection_reason = payload.reason
    _add_history(db, order, user.id, "rejected", payload.reason)
    sync_order_approval(db, organization_id=organization_id, action="import_order", order_id=order.id, actor_id=user.id, transition="rejected", note=payload.reason)
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.post("/{order_id}/cancel", response_model=ImportOrderOut, summary="Cancel an eligible import order")
def cancel_import_order(
    order_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.cancel", lock=True)
    if order.status not in {"draft", "rejected", "approved"}:
        raise HTTPException(status_code=409, detail="This import order cannot be cancelled in its current status.")
    received_count = db.query(func.count(ImportGoodsReceipt.id)).filter(ImportGoodsReceipt.order_id == order.id, ImportGoodsReceipt.organization_id == organization_id).scalar() or 0
    if received_count:
        raise HTTPException(status_code=409, detail="Orders with goods receipts cannot be cancelled; record a transparent corrective workflow instead.")
    _add_history(db, order, user.id, "cancelled", "Cancelled by an authorized user")
    sync_order_approval(db, organization_id=organization_id, action="import_order", order_id=order.id, actor_id=user.id, transition="cancelled", note="Cancelled by an authorized user")
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.patch("/{order_id}/costs", response_model=ImportOrderOut, summary="Record actual import logistics costs")
def update_import_costs(
    order_id: UUID,
    organization_id: UUID,
    payload: ImportCostUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.costs.update", lock=True)
    if order.status in {"draft", "cancelled"}:
        raise HTTPException(status_code=409, detail="Actual costs can be recorded after an import order is approved and before cancellation.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.get("/{order_id}/shipments", response_model=list[ImportShipmentOut], summary="List shipments for an import order")
def list_import_shipments(order_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.read")
    return db.query(ImportShipment).filter(ImportShipment.order_id == order.id, ImportShipment.organization_id == organization_id).order_by(ImportShipment.created_at.desc()).all()


@router.post("/{order_id}/shipments", response_model=ImportShipmentOut, status_code=status.HTTP_201_CREATED, summary="Record a shipment for an approved import")
def create_import_shipment(
    order_id: UUID,
    organization_id: UUID,
    payload: ImportShipmentCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "shipments.create", lock=True)
    if order.status not in {"approved", "partially_received"}:
        raise HTTPException(status_code=409, detail="Shipments can only be recorded for approved or partially received import orders.")
    shipment = ImportShipment(
        organization_id=organization_id, order_id=order.id,
        shipment_reference=payload.shipment_reference, carrier=payload.carrier,
        tracking_reference=payload.tracking_reference, transport_mode=payload.transport_mode.value,
        origin=payload.origin or order.country_of_origin, destination=payload.destination or order.destination,
        estimated_departure=payload.estimated_departure or order.estimated_departure_date,
        estimated_arrival=payload.estimated_arrival or order.estimated_arrival_date,
        status="planned", notes=payload.notes, created_by_user_id=user.id,
    )
    db.add(shipment)
    db.flush()
    db.add(ImportShipmentMilestone(
        organization_id=organization_id,
        order_id=order.id,
        shipment_id=shipment.id,
        name="Shipment planned",
        description="Shipment record created in the trade management system.",
        occurred_at=utc_now(),
        created_by_user_id=user.id,
    ))
    try:
        db.commit()
        db.refresh(shipment)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A shipment with this reference already exists in the organization.") from exc
    return shipment


@router.patch("/shipments/{shipment_id}", response_model=ImportShipmentOut, summary="Update shipment dates and status")
def update_import_shipment(
    shipment_id: UUID,
    organization_id: UUID,
    payload: ImportShipmentUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "shipments.update")
    shipment = db.query(ImportShipment).filter(ImportShipment.id == shipment_id, ImportShipment.organization_id == organization_id).with_for_update().one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    values = payload.model_dump(exclude_unset=True)
    if "status" in values and values["status"] is not None:
        next_status = values["status"].value
        if next_status not in SHIPMENT_TRANSITIONS[shipment.status]:
            raise HTTPException(status_code=409, detail=f"Shipment cannot move from {shipment.status} to {next_status}.")
        values["status"] = next_status
    estimated_departure = values.get("estimated_departure", shipment.estimated_departure)
    estimated_arrival = values.get("estimated_arrival", shipment.estimated_arrival)
    actual_departure = values.get("actual_departure", shipment.actual_departure)
    actual_arrival = values.get("actual_arrival", shipment.actual_arrival)
    if estimated_departure and estimated_arrival and estimated_arrival < estimated_departure:
        raise HTTPException(status_code=422, detail="Estimated arrival cannot be before estimated departure.")
    if actual_departure and actual_arrival and actual_arrival < actual_departure:
        raise HTTPException(status_code=422, detail="Actual arrival cannot be before actual departure.")
    for key, value in values.items():
        setattr(shipment, key, value)
    if "actual_departure" in values or "actual_arrival" in values:
        order = db.query(ImportOrder).filter(ImportOrder.id == shipment.order_id, ImportOrder.organization_id == organization_id).with_for_update().one()
        sibling_shipments = db.query(ImportShipment).filter(ImportShipment.order_id == order.id, ImportShipment.organization_id == organization_id).all()
        departure_dates = [row.actual_departure for row in sibling_shipments if row.actual_departure is not None]
        arrival_dates = [row.actual_arrival for row in sibling_shipments if row.actual_arrival is not None]
        order.actual_departure_date = min(departure_dates) if departure_dates else None
        order.actual_arrival_date = max(arrival_dates) if arrival_dates else None
    db.commit()
    db.refresh(shipment)
    return shipment


@router.get("/shipments/{shipment_id}/milestones", response_model=list[ShipmentMilestoneOut], summary="List manual shipment milestones")
def list_import_shipment_milestones(shipment_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_permission(db, user.id, organization_id, "shipments.read")
    shipment = db.query(ImportShipment).filter(ImportShipment.id == shipment_id, ImportShipment.organization_id == organization_id).one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    return db.query(ImportShipmentMilestone).filter(ImportShipmentMilestone.shipment_id == shipment.id, ImportShipmentMilestone.organization_id == organization_id).order_by(ImportShipmentMilestone.occurred_at.asc()).all()


@router.post("/shipments/{shipment_id}/milestones", response_model=ShipmentMilestoneOut, status_code=status.HTTP_201_CREATED, summary="Add a manual shipment milestone")
def create_import_shipment_milestone(
    shipment_id: UUID,
    organization_id: UUID,
    payload: ShipmentMilestoneCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "shipments.update")
    shipment = db.query(ImportShipment).filter(ImportShipment.id == shipment_id, ImportShipment.organization_id == organization_id).one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    milestone = ImportShipmentMilestone(
        organization_id=organization_id, order_id=shipment.order_id, shipment_id=shipment.id,
        name=payload.name, description=payload.description, occurred_at=payload.occurred_at,
        created_by_user_id=user.id,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.get("/{order_id}/receipts", response_model=list[GoodsReceiptOut], summary="List goods receipts for an import order")
def list_import_receipts(order_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _scoped_order(db, user.id, organization_id, order_id, "imports.read")
    receipts = db.query(ImportGoodsReceipt).filter(
        ImportGoodsReceipt.order_id == order.id,
        ImportGoodsReceipt.organization_id == organization_id,
    ).order_by(ImportGoodsReceipt.received_at.desc()).all()
    return [GoodsReceiptOut.model_validate(_receipt_payload(db, receipt)) for receipt in receipts]


@router.post("/{order_id}/receipts", response_model=GoodsReceiptOut, summary="Record a partial or complete goods receipt and update stock atomically")
def receive_import_goods(
    order_id: UUID,
    organization_id: UUID,
    payload: GoodsReceiptCreate,
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "inventory.receive")
    expected_hash = _request_hash(order_id, payload)
    existing = db.query(ImportGoodsReceipt).filter(
        ImportGoodsReceipt.organization_id == organization_id,
        ImportGoodsReceipt.idempotency_key == payload.idempotency_key,
    ).one_or_none()
    if existing is not None:
        if existing.order_id != order_id or existing.request_hash != expected_hash:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different goods receipt.")
        response.status_code = status.HTTP_200_OK
        return _receipt_payload(db, existing)

    order = _scoped_order(db, user.id, organization_id, order_id, "imports.read", lock=True)
    if order.status not in {"approved", "partially_received"}:
        raise HTTPException(status_code=409, detail="Goods can only be received against approved import orders.")
    location = db.query(InventoryLocation).filter(
        InventoryLocation.id == payload.location_id,
        InventoryLocation.organization_id == organization_id,
        InventoryLocation.is_active.is_(True),
    ).one_or_none()
    if location is None:
        raise HTTPException(status_code=422, detail="Select an active inventory location in this organization.")
    requested_item_ids = [line.order_item_id for line in payload.items]
    order_items = db.query(ImportOrderItem).filter(
        ImportOrderItem.organization_id == organization_id,
        ImportOrderItem.order_id == order.id,
        ImportOrderItem.id.in_(requested_item_ids),
    ).with_for_update().all()
    items_by_id = {item.id: item for item in order_items}
    if len(items_by_id) != len(requested_item_ids):
        raise HTTPException(status_code=422, detail="Every received line must belong to this import order.")
    for line in payload.items:
        item = items_by_id[line.order_item_id]
        remaining = item.quantity_ordered - item.quantity_received
        if line.quantity_received > remaining:
            raise HTTPException(status_code=409, detail=f"Receipt quantity exceeds the remaining quantity for {item.product_sku_snapshot}.")

    product_ids = sorted({items_by_id[line.order_item_id].product_id for line in payload.items}, key=str)
    products = db.query(Product).filter(
        Product.organization_id == organization_id,
        Product.id.in_(product_ids),
    ).order_by(Product.id.asc()).with_for_update().all()
    products_by_id = {product.id: product for product in products}
    if len(products_by_id) != len(product_ids):
        raise HTTPException(status_code=409, detail="A product on this order no longer exists; contact an administrator.")

    receipt = ImportGoodsReceipt(
        organization_id=organization_id, order_id=order.id, location_id=location.id,
        receipt_reference=payload.receipt_reference, idempotency_key=payload.idempotency_key,
        request_hash=expected_hash, received_at=_utc_now(), notes=payload.notes,
        received_by_user_id=user.id,
    )
    db.add(receipt)
    db.flush()

    for line in payload.items:
        item = items_by_id[line.order_item_id]
        product = products_by_id[item.product_id]
        balance = db.query(InventoryBalance).filter(
            InventoryBalance.organization_id == organization_id,
            InventoryBalance.product_id == product.id,
            InventoryBalance.location_id == location.id,
        ).with_for_update().one_or_none()
        if balance is None:
            next_on_hand = line.quantity_received
            balance = InventoryBalance(
                organization_id=organization_id, product_id=product.id, location_id=location.id,
                quantity_on_hand=next_on_hand, reserved_quantity=ZERO,
            )
            db.add(balance)
        else:
            next_on_hand = balance.quantity_on_hand + line.quantity_received
            balance.quantity_on_hand = next_on_hand
        item.quantity_received += line.quantity_received
        db.add(ImportGoodsReceiptItem(
            organization_id=organization_id, receipt_id=receipt.id, order_id=order.id,
            order_item_id=item.id, quantity_received=line.quantity_received,
        ))
        movement_key = f"igr:{receipt.id.hex}:{item.id.hex}"
        db.add(InventoryMovement(
            organization_id=organization_id, product_id=product.id, location_id=location.id,
            movement_type=InventoryMovementType.GOODS_RECEIVED.value,
            quantity_delta=line.quantity_received, reserved_delta=ZERO,
            quantity_on_hand_after=next_on_hand,
            reserved_quantity_after=balance.reserved_quantity,
            idempotency_key=movement_key, source_type="import_goods_receipt",
            source_reference=payload.receipt_reference, notes=payload.notes,
            created_by_user_id=user.id,
        ))

    all_order_items = db.query(ImportOrderItem).filter(
        ImportOrderItem.organization_id == organization_id,
        ImportOrderItem.order_id == order.id,
    ).with_for_update().all()
    is_fully_received = bool(all_order_items) and all(item.quantity_received >= item.quantity_ordered for item in all_order_items)
    next_status = "received" if is_fully_received else "partially_received"
    if order.status != next_status:
        _add_history(db, order, user.id, next_status, f"Goods receipt {payload.receipt_reference} posted")
    try:
        db.commit()
        db.refresh(receipt)
    except IntegrityError as exc:
        db.rollback()
        raced = db.query(ImportGoodsReceipt).filter(
            ImportGoodsReceipt.organization_id == organization_id,
            ImportGoodsReceipt.idempotency_key == payload.idempotency_key,
        ).one_or_none()
        if raced and raced.order_id == order_id and raced.request_hash == expected_hash:
            response.status_code = status.HTTP_200_OK
            return _receipt_payload(db, raced)
        raise HTTPException(status_code=409, detail="Goods receipt conflicted with another update; reload the order and retry with a new idempotency key.") from exc
    return _receipt_payload(db, receipt)


@router.get("/{order_id}/documents", response_model=list[ImportDocumentOut], summary="List private documents attached to an import order")
def list_import_documents(order_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _scoped_order(db, user.id, organization_id, order_id, "documents.read")
    return db.query(ImportDocument).filter(
        ImportDocument.order_id == order.id,
        ImportDocument.organization_id == organization_id,
    ).order_by(ImportDocument.created_at.desc()).all()


@router.post("/{order_id}/documents", response_model=ImportDocumentOut, status_code=status.HTTP_201_CREATED, summary="Upload a private document to an import order")
async def upload_import_document(
    request: Request,
    order_id: UUID,
    organization_id: UUID,
    document_type: str = Form(...),
    expiry_date: date | None = Form(default=None),
    file: UploadFile = File(...),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "documents.upload")
    document_type = document_type.strip().lower()
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"document_type must be one of: {', '.join(sorted(DOCUMENT_TYPES))}.")
    original_name = PurePath(file.filename or "upload").name
    original_name = re.sub(r"[\x00-\x1f\x7f]", "", original_name)[:255]
    suffix = Path(original_name).suffix.lower()
    if not suffix or suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type. Allowed types: PDF, PNG, JPG, XLSX, DOCX, CSV, TXT.")
    settings = get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB upload limit.")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The file contents do not match a PDF document.")
    if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="The file contents do not match a PNG image.")
    if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="The file contents do not match a JPEG image.")
    if suffix in {".xlsx", ".docx"} and not content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=415, detail="The file contents do not match a supported Office document.")
    if suffix in {".csv", ".txt"}:
        try:
            text_content = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="CSV and text documents must be UTF-8 encoded.") from exc
        if "\x00" in text_content:
            raise HTTPException(status_code=415, detail="CSV and text documents cannot contain binary data.")
    document_id = uuid4()
    storage_key = f"imports/{organization_id}/{order.id}/{document_id.hex}{suffix}"
    storage = _legacy_document_storage()
    try:
        storage.put(storage_key, content, mimetypes.guess_type(original_name)[0] or "application/octet-stream")
    except StorageError as exc:
        logger.exception("Private document storage write failed")
        raise HTTPException(status_code=500, detail="The document could not be stored. Please retry.") from exc

    doc = ImportDocument(
        id=document_id, organization_id=organization_id, order_id=order.id,
        document_reference=f"DOC-{document_id.hex[:10].upper()}", document_type=document_type,
        file_name=original_name or f"document{suffix}",
        content_type=mimetypes.guess_type(original_name)[0] or "application/octet-stream",
        file_size=len(content), storage_key=storage_key, verification_status="pending",
        expiry_date=expiry_date, uploaded_by_user_id=user.id,
    )
    db.add(doc)
    try:
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        try:
            storage.delete(storage_key)
        except StorageError:
            logger.exception("Orphan import document cleanup failed")
        logger.exception("Could not save uploaded document metadata")
        raise HTTPException(status_code=500, detail="The document could not be registered. Please retry.")
    return doc


@router.get("/{order_id}/documents/{document_id}/download", summary="Download an authorized private import document")
def download_import_document(order_id: UUID, document_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _scoped_order(db, user.id, organization_id, order_id, "documents.read")
    doc = _scoped_document(db, order, document_id)
    try:
        content = _legacy_document_storage().get(doc.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="The stored file is no longer available.") from exc
    except StorageError as exc:
        logger.exception("Private import document retrieval failed")
        raise HTTPException(status_code=500, detail="The document could not be retrieved. Please retry.") from exc
    from urllib.parse import quote
    return Response(
        content=content,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.file_name, safe='')}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.patch("/{order_id}/documents/{document_id}", response_model=ImportDocumentOut, summary="Verify or update import document metadata")
def update_import_document(
    order_id: UUID,
    document_id: UUID,
    organization_id: UUID,
    payload: ImportDocumentUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "documents.verify")
    order = _scoped_order(db, user.id, organization_id, order_id, "documents.read")
    doc = _scoped_document(db, order, document_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "verification_status":
            doc.verification_status = value.value if value else doc.verification_status
            if doc.verification_status == DocumentVerificationStatus.PENDING.value:
                doc.verified_by_user_id = None
                doc.verified_at = None
            else:
                doc.verified_by_user_id = user.id
                doc.verified_at = _utc_now()
        else:
            setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{order_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a private import document")
def delete_import_document(
    order_id: UUID,
    document_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "documents.delete")
    order = _scoped_order(db, user.id, organization_id, order_id, "documents.read")
    doc = _scoped_document(db, order, document_id)
    storage_key = doc.storage_key
    db.delete(doc)
    db.commit()
    try:
        _legacy_document_storage().delete(storage_key)
    except StorageError:
        logger.exception("Private import document blob cleanup failed")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
