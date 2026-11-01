"""Export orders, approval, stock reservation, dispatch, and partial delivery workflows."""
import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.core.security import utc_now, verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import (
    Customer, ExportDelivery, ExportDeliveryItem, ExportOrder, ExportOrderItem,
    ExportOrderStatusHistory, ExportShipment, ExportShipmentItem, ExportShipmentMilestone, InventoryBalance,
    InventoryLocation, InventoryMovement, OrganizationMembership, Product, User, UserSession,
)
from app.schemas.exports import (
    ExportDeliveryCreate, ExportDeliveryOut, ExportOrderCreate, ExportOrderOut,
    ExportOrderPage, ExportOrderUpdate, ExportRejectRequest, ExportShipmentCreate,
    ExportShipmentOut,
)

from app.services.workflow import assert_order_approval_role, sync_order_approval

router = APIRouter(prefix="/exports", tags=["exports"])
ZERO = Decimal("0")
QUANTITY_SCALE = Decimal("0.0001")

def _quantity(value: Decimal) -> Decimal:
    return Decimal(value).quantize(QUANTITY_SCALE)


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _scoped_order(db: Session, user_id: UUID, organization_id: UUID, order_id: UUID, permission: str = "exports.read", *, lock: bool = False) -> ExportOrder:
    require_org_permission(db, user_id, organization_id, permission)
    query = db.query(ExportOrder).filter(ExportOrder.id == order_id, ExportOrder.organization_id == organization_id)
    if lock:
        query = query.with_for_update()
    order = query.one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Export order not found.")
    return order


def _validate_customer(db: Session, organization_id: UUID, customer_id: UUID) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.organization_id == organization_id, Customer.is_active.is_(True)).one_or_none()
    if customer is None:
        raise HTTPException(status_code=422, detail="Select an active customer in this organization.")
    return customer


def _validate_location(db: Session, organization_id: UUID, location_id: UUID) -> InventoryLocation:
    location = db.query(InventoryLocation).filter(InventoryLocation.id == location_id, InventoryLocation.organization_id == organization_id, InventoryLocation.is_active.is_(True)).one_or_none()
    if location is None:
        raise HTTPException(status_code=422, detail="Select an active inventory location in this organization.")
    return location


def _validate_assignee(db: Session, organization_id: UUID, user_id: UUID | None) -> None:
    if user_id is None:
        return
    member = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == organization_id, OrganizationMembership.user_id == user_id, OrganizationMembership.is_active.is_(True)).one_or_none()
    if member is None:
        raise HTTPException(status_code=422, detail="Assigned user must be an active member of this organization.")


def _active_product(db: Session, organization_id: UUID, product_id: UUID) -> Product:
    product = db.query(Product).filter(Product.id == product_id, Product.organization_id == organization_id, Product.is_active.is_(True)).one_or_none()
    if product is None:
        raise HTTPException(status_code=422, detail="Every export line must reference an active product in this organization.")
    return product


def _history(db: Session, order: ExportOrder, actor_id: UUID, next_status: str, reason: str | None = None) -> None:
    if order.status == next_status:
        return
    db.add(ExportOrderStatusHistory(organization_id=order.organization_id, order_id=order.id, from_status=order.status, to_status=next_status, reason=reason, actor_user_id=actor_id))
    order.status = next_status


def _item_payload(item: ExportOrderItem) -> dict:
    return {
        "id": item.id, "organization_id": item.organization_id, "order_id": item.order_id,
        "line_number": item.line_number, "product_id": item.product_id,
        "product_sku_snapshot": item.product_sku_snapshot, "product_name_snapshot": item.product_name_snapshot,
        "description": item.description, "quantity_ordered": item.quantity_ordered,
        "quantity_reserved": item.quantity_reserved, "quantity_dispatched": item.quantity_dispatched,
        "quantity_delivered": item.quantity_delivered,
        "quantity_not_dispatched": max(item.quantity_ordered - item.quantity_dispatched - item.quantity_reserved, ZERO),
        "quantity_not_delivered": max(item.quantity_ordered - item.quantity_delivered, ZERO),
        "unit_price": item.unit_price, "line_total": item.quantity_ordered * item.unit_price,
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


def _shipment_payload(db: Session, shipment: ExportShipment) -> dict:
    shipment_items = db.query(ExportShipmentItem).filter(ExportShipmentItem.shipment_id == shipment.id, ExportShipmentItem.organization_id == shipment.organization_id).all()
    items = []
    for line in shipment_items:
        delivered = db.query(ExportDeliveryItem).filter(ExportDeliveryItem.shipment_item_id == line.id, ExportDeliveryItem.organization_id == shipment.organization_id).with_entities(ExportDeliveryItem.quantity_delivered).all()
        quantity_delivered = sum((row[0] for row in delivered), ZERO)
        items.append({"id": line.id, "organization_id": line.organization_id, "shipment_id": line.shipment_id, "order_id": line.order_id, "order_item_id": line.order_item_id, "quantity_dispatched": _quantity(line.quantity_dispatched), "quantity_delivered": _quantity(quantity_delivered), "quantity_remaining": _quantity(max(line.quantity_dispatched - quantity_delivered, ZERO))})
    return {"id": shipment.id, "organization_id": shipment.organization_id, "order_id": shipment.order_id, "shipment_reference": shipment.shipment_reference,
            "carrier": shipment.carrier, "tracking_reference": shipment.tracking_reference, "transport_mode": shipment.transport_mode,
            "origin": shipment.origin, "destination": shipment.destination, "status": shipment.status,
            "estimated_departure": shipment.estimated_departure, "actual_departure": shipment.actual_departure,
            "estimated_arrival": shipment.estimated_arrival, "actual_arrival": shipment.actual_arrival, "notes": shipment.notes,
            "created_by_user_id": shipment.created_by_user_id, "created_at": shipment.created_at, "items": items}


def _order_payload(db: Session, order: ExportOrder) -> dict:
    customer = db.query(Customer).filter(Customer.id == order.customer_id, Customer.organization_id == order.organization_id).one()
    location = db.query(InventoryLocation).filter(InventoryLocation.id == order.inventory_location_id, InventoryLocation.organization_id == order.organization_id).one()
    items = db.query(ExportOrderItem).filter(ExportOrderItem.order_id == order.id, ExportOrderItem.organization_id == order.organization_id).order_by(ExportOrderItem.line_number.asc()).all()
    history = db.query(ExportOrderStatusHistory).filter(ExportOrderStatusHistory.order_id == order.id, ExportOrderStatusHistory.organization_id == order.organization_id).order_by(ExportOrderStatusHistory.created_at.asc()).all()
    shipments = db.query(ExportShipment).filter(ExportShipment.order_id == order.id, ExportShipment.organization_id == order.organization_id).order_by(ExportShipment.created_at.asc()).all()
    payload_items = [_item_payload(item) for item in items]
    return {
        "id": order.id, "organization_id": order.organization_id, "reference": order.reference,
        "customer_id": order.customer_id, "customer_name": customer.name,
        "inventory_location_id": order.inventory_location_id, "inventory_location_name": location.name,
        "status": order.status, "currency": order.currency, "destination_country": order.destination_country,
        "delivery_address": order.delivery_address, "shipping_terms": order.shipping_terms,
        "payment_terms_days": order.payment_terms_days, "requested_ship_date": order.requested_ship_date,
        "requested_delivery_date": order.requested_delivery_date, "notes": order.notes,
        "assigned_user_id": order.assigned_user_id, "created_by_user_id": order.created_by_user_id,
        "submitted_at": order.submitted_at, "approved_by_user_id": order.approved_by_user_id,
        "approved_at": order.approved_at, "rejection_reason": order.rejection_reason,
        "archived_at": order.archived_at, "archived_by_user_id": order.archived_by_user_id,
        "archive_reason": order.archive_reason,
        "goods_total": sum((item.quantity_ordered * item.unit_price for item in items), ZERO),
        "quantity_ordered": sum((item.quantity_ordered for item in items), ZERO),
        "quantity_reserved": sum((item.quantity_reserved for item in items), ZERO),
        "quantity_dispatched": sum((item.quantity_dispatched for item in items), ZERO),
        "quantity_delivered": sum((item.quantity_delivered for item in items), ZERO),
        "created_at": order.created_at, "updated_at": order.updated_at,
        "items": payload_items, "status_history": history,
        "shipments": [_shipment_payload(db, shipment) for shipment in shipments],
    }


def _out(db: Session, order: ExportOrder) -> ExportOrderOut:
    return ExportOrderOut.model_validate(_order_payload(db, order))


def _hash_payload(payload) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _movement_key(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:40]}"


def _apply_movement(db: Session, *, order: ExportOrder, item: ExportOrderItem, balance: InventoryBalance, movement_type: str,
                    quantity_delta: Decimal, reserved_delta: Decimal, idempotency_key: str, actor_id: UUID, source_reference: str) -> None:
    balance.quantity_on_hand += quantity_delta
    balance.reserved_quantity += reserved_delta
    if balance.quantity_on_hand < ZERO or balance.reserved_quantity < ZERO or balance.reserved_quantity > balance.quantity_on_hand:
        raise HTTPException(status_code=409, detail="Inventory movement would violate stock balance constraints.")
    db.add(InventoryMovement(
        organization_id=order.organization_id, product_id=item.product_id, location_id=order.inventory_location_id,
        movement_type=movement_type, quantity_delta=quantity_delta, reserved_delta=reserved_delta,
        quantity_on_hand_after=balance.quantity_on_hand, reserved_quantity_after=balance.reserved_quantity,
        idempotency_key=idempotency_key, source_type="export_order", source_reference=source_reference,
        notes=f"{order.reference}: {movement_type}", created_by_user_id=actor_id,
    ))


def _release_reservations(db: Session, order: ExportOrder, actor_id: UUID) -> None:
    items = db.query(ExportOrderItem).filter(ExportOrderItem.order_id == order.id, ExportOrderItem.organization_id == order.organization_id).with_for_update().all()
    for item in items:
        qty = item.quantity_reserved
        if qty <= ZERO:
            continue
        balance = db.query(InventoryBalance).filter(
            InventoryBalance.organization_id == order.organization_id,
            InventoryBalance.product_id == item.product_id,
            InventoryBalance.location_id == order.inventory_location_id,
        ).with_for_update().one_or_none()
        if balance is None or balance.reserved_quantity < qty:
            raise HTTPException(status_code=409, detail="Reserved stock no longer matches the export order. Contact an administrator.")
        _apply_movement(db, order=order, item=item, balance=balance, movement_type="reservation_release",
                        quantity_delta=ZERO, reserved_delta=-qty,
                        idempotency_key=_movement_key("expcan", f"{order.id}:{item.id}"), actor_id=actor_id,
                        source_reference=order.reference)
        item.quantity_reserved = ZERO


def _recalculate_status(db: Session, order: ExportOrder, actor_id: UUID) -> None:
    items = db.query(ExportOrderItem).filter(ExportOrderItem.order_id == order.id, ExportOrderItem.organization_id == order.organization_id).all()
    if not items:
        return
    if all(item.quantity_delivered >= item.quantity_ordered for item in items):
        next_status = "delivered"
    elif any(item.quantity_delivered > ZERO for item in items):
        next_status = "partially_delivered"
    elif all(item.quantity_dispatched >= item.quantity_ordered for item in items):
        next_status = "dispatched"
    elif any(item.quantity_dispatched > ZERO for item in items):
        next_status = "partially_dispatched"
    else:
        next_status = "approved"
    _history(db, order, actor_id, next_status)


@router.get("", response_model=ExportOrderPage, summary="List export orders")
def list_export_orders(
    organization_id: UUID,
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "exports.read")
    query = db.query(ExportOrder).join(Customer, (Customer.id == ExportOrder.customer_id) & (Customer.organization_id == organization_id)).filter(ExportOrder.organization_id == organization_id, ExportOrder.archived_at.is_(None))
    if status_filter and status_filter != "all":
        query = query.filter(ExportOrder.status == status_filter)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(ExportOrder.reference.ilike(pattern), Customer.name.ilike(pattern)))
    total = query.count()
    rows = query.order_by(ExportOrder.updated_at.desc(), ExportOrder.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_order_payload(db, row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ExportOrderOut, status_code=status.HTTP_201_CREATED, summary="Create a draft export order")
def create_export_order(
    organization_id: UUID, payload: ExportOrderCreate, request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "exports.create")
    _validate_customer(db, organization_id, payload.customer_id)
    _validate_location(db, organization_id, payload.inventory_location_id)
    _validate_assignee(db, organization_id, payload.assigned_user_id)
    order = ExportOrder(
        organization_id=organization_id, reference=f"EXP-{utc_now():%Y%m%d}-{uuid4().hex[:8].upper()}",
        customer_id=payload.customer_id, inventory_location_id=payload.inventory_location_id,
        currency=payload.currency, destination_country=payload.destination_country,
        delivery_address=payload.delivery_address, shipping_terms=payload.shipping_terms,
        payment_terms_days=payload.payment_terms_days, requested_ship_date=payload.requested_ship_date,
        requested_delivery_date=payload.requested_delivery_date, notes=payload.notes,
        assigned_user_id=payload.assigned_user_id, created_by_user_id=user.id, status="draft",
    )
    db.add(order)
    try:
        db.flush()
        for idx, line in enumerate(payload.items, start=1):
            product = _active_product(db, organization_id, line.product_id)
            db.add(ExportOrderItem(organization_id=organization_id, order_id=order.id, line_number=idx,
                product_id=product.id, product_sku_snapshot=product.sku, product_name_snapshot=product.name,
                description=line.description, quantity_ordered=line.quantity_ordered, unit_price=line.unit_price))
        db.add(ExportOrderStatusHistory(organization_id=organization_id, order_id=order.id, from_status=None, to_status="draft", reason="Order created", actor_user_id=user.id))
        db.commit()
        db.refresh(order)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Export order could not be created due to a conflicting record.") from exc
    return _out(db, order)


@router.get("/{order_id}", response_model=ExportOrderOut, summary="Get export order details")
def get_export_order(order_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(db, _scoped_order(db, user.id, organization_id, order_id))


@router.patch("/{order_id}", response_model=ExportOrderOut, summary="Update a draft or rejected export order")
def update_export_order(
    order_id: UUID, organization_id: UUID, payload: ExportOrderUpdate, request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "exports.update", lock=True)
    if order.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="Only draft or rejected export orders can be edited.")
    values = payload.model_dump(exclude_unset=True)
    if "customer_id" in values:
        _validate_customer(db, organization_id, values["customer_id"])
    if "inventory_location_id" in values:
        _validate_location(db, organization_id, values["inventory_location_id"])
    if "assigned_user_id" in values:
        _validate_assignee(db, organization_id, values["assigned_user_id"])
    for key, value in values.items():
        setattr(order, key, value)
    try:
        db.commit()
        db.refresh(order)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Export order update conflicts with existing data.") from exc
    return _out(db, order)


@router.post("/{order_id}/submit", response_model=ExportOrderOut, summary="Submit an export order for approval")
def submit_export_order(
    order_id: UUID, organization_id: UUID, request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "exports.submit", lock=True)
    if order.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="Only draft or rejected orders can be submitted.")
    item_count = db.query(ExportOrderItem).filter(ExportOrderItem.order_id == order.id, ExportOrderItem.organization_id == organization_id).count()
    if item_count == 0:
        raise HTTPException(status_code=409, detail="An export order needs at least one product line before submission.")
    order.submitted_at = utc_now()
    order.rejection_reason = None
    _history(db, order, user.id, "submitted")
    sync_order_approval(db, organization_id=organization_id, action="export_order", order_id=order.id, actor_id=user.id, transition="submitted", title=f"Export order {order.reference}")
    db.commit()
    db.refresh(order)
    return _out(db, order)


@router.post("/{order_id}/approve", response_model=ExportOrderOut, summary="Approve an export order and reserve inventory")
def approve_export_order(
    order_id: UUID, organization_id: UUID, request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "exports.approve", lock=True)
    if order.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted export orders can be approved.")
    assert_order_approval_role(db, organization_id, user.id, "export_order", order.id)
    lines = db.query(ExportOrderItem).filter(ExportOrderItem.order_id == order.id, ExportOrderItem.organization_id == organization_id).order_by(ExportOrderItem.product_id.asc()).with_for_update().all()
    by_product: dict[UUID, Decimal] = {}
    for line in lines:
        by_product[line.product_id] = by_product.get(line.product_id, ZERO) + line.quantity_ordered
    balances: dict[UUID, InventoryBalance] = {}
    for product_id, needed in by_product.items():
        balance = db.query(InventoryBalance).filter(InventoryBalance.organization_id == organization_id, InventoryBalance.product_id == product_id, InventoryBalance.location_id == order.inventory_location_id).with_for_update().one_or_none()
        available = (balance.quantity_on_hand - balance.reserved_quantity) if balance else ZERO
        if available < needed:
            raise HTTPException(status_code=409, detail=f"Insufficient available stock for one or more products. Product {product_id} needs {needed}, available {available}.")
        balances[product_id] = balance
    try:
        for line in lines:
            balance = balances[line.product_id]
            _apply_movement(db, order=order, item=line, balance=balance, movement_type="reservation", quantity_delta=ZERO,
                reserved_delta=line.quantity_ordered, idempotency_key=_movement_key("exprsv", str(line.id)), actor_id=user.id, source_reference=order.reference)
            line.quantity_reserved = line.quantity_ordered
        order.approved_by_user_id = user.id
        order.approved_at = utc_now()
        _history(db, order, user.id, "approved")
        sync_order_approval(db, organization_id=organization_id, action="export_order", order_id=order.id, actor_id=user.id, transition="approved")
        db.commit()
        db.refresh(order)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Inventory changed during approval; retry after refreshing the order.") from exc
    return _out(db, order)


@router.post("/{order_id}/reject", response_model=ExportOrderOut, summary="Reject a submitted export order")
def reject_export_order(
    order_id: UUID, organization_id: UUID, payload: ExportRejectRequest, request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "exports.approve", lock=True)
    if order.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted export orders can be rejected.")
    assert_order_approval_role(db, organization_id, user.id, "export_order", order.id)
    order.rejection_reason = payload.reason
    _history(db, order, user.id, "rejected", payload.reason)
    sync_order_approval(db, organization_id=organization_id, action="export_order", order_id=order.id, actor_id=user.id, transition="rejected", note=payload.reason)
    db.commit()
    db.refresh(order)
    return _out(db, order)


@router.post("/{order_id}/cancel", response_model=ExportOrderOut, summary="Cancel an export order and release outstanding reservations")
def cancel_export_order(
    order_id: UUID, organization_id: UUID, request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "exports.cancel", lock=True)
    if order.status not in {"draft", "submitted", "rejected", "approved"}:
        raise HTTPException(status_code=409, detail="An export order cannot be cancelled after dispatch has started.")
    try:
        if order.status == "approved":
            _release_reservations(db, order, user.id)
        _history(db, order, user.id, "cancelled")
        sync_order_approval(db, organization_id=organization_id, action="export_order", order_id=order.id, actor_id=user.id, transition="cancelled", note="Cancelled by an authorized user")
        db.commit()
        db.refresh(order)
    except HTTPException:
        db.rollback()
        raise
    return _out(db, order)


@router.get("/{order_id}/shipments", response_model=list[ExportShipmentOut], summary="List export shipments")
def list_export_shipments(order_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _scoped_order(db, user.id, organization_id, order_id)
    shipments = db.query(ExportShipment).filter(ExportShipment.order_id == order.id, ExportShipment.organization_id == organization_id).order_by(ExportShipment.created_at.asc()).all()
    return [_shipment_payload(db, shipment) for shipment in shipments]


@router.post("/{order_id}/shipments", response_model=ExportShipmentOut, status_code=status.HTTP_201_CREATED, summary="Dispatch a shipment and deduct reserved stock exactly once")
def create_export_shipment(
    order_id: UUID, organization_id: UUID, payload: ExportShipmentCreate, request: Request, response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "exports.dispatch", lock=True)
    request_hash = _hash_payload(payload)
    existing = db.query(ExportShipment).filter(ExportShipment.organization_id == organization_id, ExportShipment.idempotency_key == payload.idempotency_key).one_or_none()
    if existing:
        if existing.order_id != order.id or existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different shipment.")
        response.status_code = status.HTTP_200_OK
        return _shipment_payload(db, existing)
    if order.status not in {"approved", "partially_dispatched", "partially_delivered"}:
        raise HTTPException(status_code=409, detail="Only approved export orders with reserved stock can be dispatched.")
    if len({line.order_item_id for line in payload.items}) != len(payload.items):
        raise HTTPException(status_code=422, detail="Each order line may appear only once per shipment.")
    shipment = ExportShipment(organization_id=organization_id, order_id=order.id, shipment_reference=payload.shipment_reference,
        idempotency_key=payload.idempotency_key, request_hash=request_hash, carrier=payload.carrier,
        tracking_reference=payload.tracking_reference, transport_mode=payload.transport_mode,
        origin=payload.origin, destination=payload.destination or order.delivery_address, status="in_transit",
        estimated_departure=payload.estimated_departure, actual_departure=utc_now().date(),
        estimated_arrival=payload.estimated_arrival, notes=payload.notes, created_by_user_id=user.id)
    db.add(shipment)
    try:
        db.flush()
        db.add(ExportShipmentMilestone(
            organization_id=organization_id,
            order_id=order.id,
            shipment_id=shipment.id,
            name="Shipment dispatched",
            description="Shipment dispatch was recorded and reserved inventory was posted.",
            occurred_at=utc_now(),
            created_by_user_id=user.id,
        ))
        for requested_line in payload.items:
            line = db.query(ExportOrderItem).filter(ExportOrderItem.id == requested_line.order_item_id,
                ExportOrderItem.order_id == order.id, ExportOrderItem.organization_id == organization_id).with_for_update().one_or_none()
            if line is None:
                raise HTTPException(status_code=422, detail="Shipment lines must belong to the selected export order.")
            qty = requested_line.quantity_dispatched
            if qty > line.quantity_reserved:
                raise HTTPException(status_code=409, detail="Dispatch quantity exceeds the remaining reservation for an order line.")
            balance = db.query(InventoryBalance).filter(InventoryBalance.organization_id == organization_id,
                InventoryBalance.product_id == line.product_id, InventoryBalance.location_id == order.inventory_location_id).with_for_update().one_or_none()
            if balance is None or balance.quantity_on_hand < qty or balance.reserved_quantity < qty:
                raise HTTPException(status_code=409, detail="Reserved stock balance is insufficient to dispatch this order line.")
            shipment_item = ExportShipmentItem(organization_id=organization_id, shipment_id=shipment.id, order_id=order.id,
                order_item_id=line.id, quantity_dispatched=qty)
            db.add(shipment_item)
            db.flush()
            # Release first, then deduct on-hand. Both postings commit atomically with the shipment.
            _apply_movement(db, order=order, item=line, balance=balance, movement_type="reservation_release", quantity_delta=ZERO,
                reserved_delta=-qty, idempotency_key=_movement_key("expsrel", f"{shipment.id}:{line.id}"), actor_id=user.id, source_reference=shipment.shipment_reference)
            _apply_movement(db, order=order, item=line, balance=balance, movement_type="goods_dispatched", quantity_delta=-qty,
                reserved_delta=ZERO, idempotency_key=_movement_key("expdisp", f"{shipment.id}:{line.id}"), actor_id=user.id, source_reference=shipment.shipment_reference)
            line.quantity_reserved -= qty
            line.quantity_dispatched += qty
        _recalculate_status(db, order, user.id)
        db.commit()
        db.refresh(shipment)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Shipment conflicts with an existing reference or stock movement.") from exc
    return _shipment_payload(db, shipment)


@router.post("/{order_id}/shipments/{shipment_id}/deliveries", response_model=ExportDeliveryOut, status_code=status.HTTP_201_CREATED, summary="Record a partial or complete delivery")
def create_export_delivery(
    order_id: UUID, shipment_id: UUID, organization_id: UUID, payload: ExportDeliveryCreate, request: Request, response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    order = _scoped_order(db, user.id, organization_id, order_id, "exports.deliver", lock=True)
    shipment = db.query(ExportShipment).filter(ExportShipment.id == shipment_id, ExportShipment.order_id == order.id, ExportShipment.organization_id == organization_id).with_for_update().one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Export shipment not found.")
    req_hash = _hash_payload(payload)
    existing = db.query(ExportDelivery).filter(ExportDelivery.organization_id == organization_id, ExportDelivery.idempotency_key == payload.idempotency_key).one_or_none()
    if existing:
        if existing.order_id != order.id or existing.shipment_id != shipment.id or existing.request_hash != req_hash:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different delivery.")
        response.status_code = status.HTTP_200_OK
        return {"id": existing.id, "organization_id": existing.organization_id, "order_id": existing.order_id, "shipment_id": existing.shipment_id,
            "delivery_reference": existing.delivery_reference, "idempotency_key": existing.idempotency_key, "delivered_at": existing.delivered_at,
            "notes": existing.notes, "delivered_by_user_id": existing.delivered_by_user_id,
            "items": db.query(ExportDeliveryItem).filter(ExportDeliveryItem.delivery_id == existing.id, ExportDeliveryItem.organization_id == organization_id).all()}
    if shipment.status == "delivered":
        raise HTTPException(status_code=409, detail="This shipment has already been fully delivered.")
    if len({line.shipment_item_id for line in payload.items}) != len(payload.items):
        raise HTTPException(status_code=422, detail="Each shipment line may appear only once per delivery.")
    delivery = ExportDelivery(organization_id=organization_id, order_id=order.id, shipment_id=shipment.id,
        delivery_reference=payload.delivery_reference, idempotency_key=payload.idempotency_key, request_hash=req_hash,
        notes=payload.notes, delivered_by_user_id=user.id)
    db.add(delivery)
    try:
        db.flush()
        for requested_line in payload.items:
            shipment_item = db.query(ExportShipmentItem).filter(ExportShipmentItem.id == requested_line.shipment_item_id,
                ExportShipmentItem.shipment_id == shipment.id, ExportShipmentItem.order_id == order.id,
                ExportShipmentItem.organization_id == organization_id).with_for_update().one_or_none()
            if shipment_item is None:
                raise HTTPException(status_code=422, detail="Delivery lines must belong to the selected shipment.")
            delivered_rows = db.query(ExportDeliveryItem.quantity_delivered).filter(ExportDeliveryItem.shipment_item_id == shipment_item.id,
                ExportDeliveryItem.organization_id == organization_id).all()
            already_delivered = sum((row[0] for row in delivered_rows), ZERO)
            if requested_line.quantity_delivered > shipment_item.quantity_dispatched - already_delivered:
                raise HTTPException(status_code=409, detail="Delivery quantity exceeds the remaining quantity on the shipment line.")
            order_line = db.query(ExportOrderItem).filter(ExportOrderItem.id == shipment_item.order_item_id,
                ExportOrderItem.order_id == order.id, ExportOrderItem.organization_id == organization_id).with_for_update().one()
            if order_line.quantity_delivered + requested_line.quantity_delivered > order_line.quantity_dispatched:
                raise HTTPException(status_code=409, detail="A delivery cannot exceed the order line's dispatched quantity.")
            db.add(ExportDeliveryItem(organization_id=organization_id, delivery_id=delivery.id, order_id=order.id,
                shipment_item_id=shipment_item.id, quantity_delivered=requested_line.quantity_delivered))
            order_line.quantity_delivered += requested_line.quantity_delivered
        db.flush()
        all_shipment_items = db.query(ExportShipmentItem).filter(ExportShipmentItem.shipment_id == shipment.id, ExportShipmentItem.organization_id == organization_id).all()
        all_shipment_complete = True
        for shipment_line in all_shipment_items:
            delivered_rows = db.query(ExportDeliveryItem.quantity_delivered).filter(ExportDeliveryItem.shipment_item_id == shipment_line.id, ExportDeliveryItem.organization_id == organization_id).all()
            if sum((row[0] for row in delivered_rows), ZERO) < shipment_line.quantity_dispatched:
                all_shipment_complete = False
                break
        if all_shipment_complete:
            shipment.status = "delivered"
            shipment.actual_arrival = utc_now().date()
        _recalculate_status(db, order, user.id)
        db.commit()
        db.refresh(delivery)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Delivery conflicts with an existing reference.") from exc
    return {"id": delivery.id, "organization_id": delivery.organization_id, "order_id": delivery.order_id, "shipment_id": delivery.shipment_id,
        "delivery_reference": delivery.delivery_reference, "idempotency_key": delivery.idempotency_key, "delivered_at": delivery.delivered_at,
        "notes": delivery.notes, "delivered_by_user_id": delivery.delivered_by_user_id,
        "items": db.query(ExportDeliveryItem).filter(ExportDeliveryItem.delivery_id == delivery.id, ExportDeliveryItem.organization_id == organization_id).all()}


@router.get("/{order_id}/deliveries", response_model=list[ExportDeliveryOut], summary="List delivery events for an export order")
def list_export_deliveries(order_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _scoped_order(db, user.id, organization_id, order_id)
    deliveries = db.query(ExportDelivery).filter(ExportDelivery.order_id == order.id, ExportDelivery.organization_id == organization_id).order_by(ExportDelivery.delivered_at.asc()).all()
    return [{"id": item.id, "organization_id": item.organization_id, "order_id": item.order_id, "shipment_id": item.shipment_id,
             "delivery_reference": item.delivery_reference, "idempotency_key": item.idempotency_key, "delivered_at": item.delivered_at,
             "notes": item.notes, "delivered_by_user_id": item.delivered_by_user_id,
             "items": db.query(ExportDeliveryItem).filter(ExportDeliveryItem.delivery_id == item.id, ExportDeliveryItem.organization_id == organization_id).all()} for item in deliveries]
