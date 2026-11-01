"""Transactional inventory balances and append-only movement ledger."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.core.security import verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import InventoryBalance, InventoryLocation, InventoryMovement, Product, User, UserSession
from app.schemas.inventory import (
    InventoryBalanceOut, InventoryMovementCreate, InventoryMovementOut, InventoryMovementType,
)
from app.schemas.master_data import Page

router = APIRouter(prefix="/inventory", tags=["inventory"])
ZERO = Decimal("0")

MOVEMENT_PERMISSIONS = {
    InventoryMovementType.GOODS_RECEIVED: "inventory.receive",
    InventoryMovementType.GOODS_DISPATCHED: "inventory.dispatch",
    InventoryMovementType.RESERVATION: "inventory.reserve",
    InventoryMovementType.RESERVATION_RELEASE: "inventory.release_reservation",
    InventoryMovementType.ADJUSTMENT_INCREASE: "inventory.adjust",
    InventoryMovementType.ADJUSTMENT_DECREASE: "inventory.adjust",
    InventoryMovementType.RETURN: "inventory.receive",
}


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _movement_deltas(movement_type: InventoryMovementType, quantity: Decimal) -> tuple[Decimal, Decimal]:
    if movement_type in {InventoryMovementType.GOODS_RECEIVED, InventoryMovementType.RETURN, InventoryMovementType.ADJUSTMENT_INCREASE}:
        return quantity, ZERO
    if movement_type in {InventoryMovementType.GOODS_DISPATCHED, InventoryMovementType.ADJUSTMENT_DECREASE}:
        return -quantity, ZERO
    if movement_type == InventoryMovementType.RESERVATION:
        return ZERO, quantity
    if movement_type == InventoryMovementType.RESERVATION_RELEASE:
        return ZERO, -quantity
    raise HTTPException(status_code=422, detail="Unsupported inventory movement type.")


def _same_request(existing: InventoryMovement, payload: InventoryMovementCreate) -> bool:
    q_delta, r_delta = _movement_deltas(payload.movement_type, payload.quantity)
    return (
        existing.product_id == payload.product_id
        and existing.location_id == payload.location_id
        and existing.movement_type == payload.movement_type.value
        and existing.quantity_delta == q_delta
        and existing.reserved_delta == r_delta
        and existing.source_type == payload.source_type
        and existing.source_reference == payload.source_reference
        and existing.notes == payload.notes
    )


@router.get("/balances", response_model=Page[InventoryBalanceOut], summary="List inventory balances")
def list_inventory_balances(
    organization_id: UUID,
    search: str | None = None,
    location_id: UUID | None = None,
    product_id: UUID | None = None,
    low_stock: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "inventory.read")
    query = (
        db.query(InventoryBalance, Product, InventoryLocation)
        .join(Product, (Product.id == InventoryBalance.product_id) & (Product.organization_id == organization_id))
        .join(InventoryLocation, (InventoryLocation.id == InventoryBalance.location_id) & (InventoryLocation.organization_id == organization_id))
        .filter(InventoryBalance.organization_id == organization_id)
    )
    if product_id:
        query = query.filter(InventoryBalance.product_id == product_id)
    if location_id:
        query = query.filter(InventoryBalance.location_id == location_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Product.sku.ilike(pattern), Product.name.ilike(pattern), InventoryLocation.code.ilike(pattern), InventoryLocation.name.ilike(pattern)))
    if low_stock is not None:
        low_stock_expression = (InventoryBalance.quantity_on_hand - InventoryBalance.reserved_quantity) <= Product.reorder_threshold
        query = query.filter(low_stock_expression if low_stock else ~low_stock_expression)
    total = query.count()
    rows = query.order_by(Product.name.asc(), InventoryLocation.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for balance, product, location in rows:
        available = balance.quantity_on_hand - balance.reserved_quantity
        items.append({
            "id": balance.id,
            "organization_id": balance.organization_id,
            "product_id": product.id,
            "product_sku": product.sku,
            "product_name": product.name,
            "location_id": location.id,
            "location_code": location.code,
            "location_name": location.name,
            "quantity_on_hand": balance.quantity_on_hand,
            "reserved_quantity": balance.reserved_quantity,
            "available_quantity": available,
            "reorder_threshold": product.reorder_threshold,
            "is_low_stock": available <= product.reorder_threshold,
            "updated_at": balance.updated_at,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/movements", response_model=Page[InventoryMovementOut], summary="List the inventory movement ledger")
def list_inventory_movements(
    organization_id: UUID,
    product_id: UUID | None = None,
    location_id: UUID | None = None,
    movement_type: InventoryMovementType | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "inventory.read")
    query = db.query(InventoryMovement).filter(InventoryMovement.organization_id == organization_id)
    if product_id:
        query = query.filter(InventoryMovement.product_id == product_id)
    if location_id:
        query = query.filter(InventoryMovement.location_id == location_id)
    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type.value)
    total = query.count()
    rows = query.order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.post("/movements", response_model=InventoryMovementOut, summary="Post a duplicate-safe inventory movement")
def create_inventory_movement(
    payload: InventoryMovementCreate,
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    permission = MOVEMENT_PERMISSIONS[payload.movement_type]
    require_org_permission(db, user.id, payload.organization_id, permission)
    q_delta, r_delta = _movement_deltas(payload.movement_type, payload.quantity)

    existing = db.query(InventoryMovement).filter(
        InventoryMovement.organization_id == payload.organization_id,
        InventoryMovement.idempotency_key == payload.idempotency_key,
    ).one_or_none()
    if existing is not None:
        if not _same_request(existing, payload):
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different inventory movement.")
        response.status_code = status.HTTP_200_OK
        return existing

    # Lock the product row on PostgreSQL. This serializes stock operations for one SKU and
    # prevents two requests from creating/reading the first balance at the same time.
    product = db.query(Product).filter(
        Product.id == payload.product_id,
        Product.organization_id == payload.organization_id,
        Product.is_active.is_(True),
    ).with_for_update().one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found or inactive.")
    location = db.query(InventoryLocation).filter(
        InventoryLocation.id == payload.location_id,
        InventoryLocation.organization_id == payload.organization_id,
        InventoryLocation.is_active.is_(True),
    ).one_or_none()
    if location is None:
        raise HTTPException(status_code=404, detail="Inventory location not found or inactive.")

    balance = db.query(InventoryBalance).filter(
        InventoryBalance.organization_id == payload.organization_id,
        InventoryBalance.product_id == product.id,
        InventoryBalance.location_id == location.id,
    ).with_for_update().one_or_none()

    current_on_hand = balance.quantity_on_hand if balance is not None else ZERO
    current_reserved = balance.reserved_quantity if balance is not None else ZERO
    available_before = current_on_hand - current_reserved
    next_on_hand = current_on_hand + q_delta
    next_reserved = current_reserved + r_delta

    if payload.movement_type in {InventoryMovementType.GOODS_DISPATCHED, InventoryMovementType.RESERVATION} and available_before < payload.quantity:
        raise HTTPException(status_code=409, detail="Insufficient available stock for this operation.")
    if payload.movement_type == InventoryMovementType.RESERVATION_RELEASE and current_reserved < payload.quantity:
        raise HTTPException(status_code=409, detail="Cannot release more stock than is currently reserved.")
    if next_on_hand < ZERO:
        raise HTTPException(status_code=409, detail="This movement would make on-hand stock negative.")
    if next_reserved < ZERO:
        raise HTTPException(status_code=409, detail="Reserved stock cannot become negative.")
    if next_reserved > next_on_hand:
        raise HTTPException(status_code=409, detail="On-hand stock cannot be adjusted below the reserved quantity.")

    if balance is None:
        balance = InventoryBalance(
            organization_id=payload.organization_id,
            product_id=product.id,
            location_id=location.id,
            quantity_on_hand=next_on_hand,
            reserved_quantity=next_reserved,
        )
        db.add(balance)
    else:
        balance.quantity_on_hand = next_on_hand
        balance.reserved_quantity = next_reserved
    movement = InventoryMovement(
        organization_id=payload.organization_id,
        product_id=product.id,
        location_id=location.id,
        movement_type=payload.movement_type.value,
        quantity_delta=q_delta,
        reserved_delta=r_delta,
        quantity_on_hand_after=next_on_hand,
        reserved_quantity_after=next_reserved,
        idempotency_key=payload.idempotency_key,
        source_type=payload.source_type,
        source_reference=payload.source_reference,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    db.add(movement)
    try:
        db.commit()
        db.refresh(movement)
    except IntegrityError as exc:
        db.rollback()
        # If a simultaneous retry won the unique-key race, return the committed record only
        # when its payload matches exactly. Never report success for a conflicting retry.
        existing_after_race = db.query(InventoryMovement).filter(
            InventoryMovement.organization_id == payload.organization_id,
            InventoryMovement.idempotency_key == payload.idempotency_key,
        ).one_or_none()
        if existing_after_race is not None and _same_request(existing_after_race, payload):
            response.status_code = status.HTTP_200_OK
            return existing_after_race
        if existing_after_race is not None:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different inventory movement.") from exc
        raise HTTPException(status_code=409, detail="Inventory movement conflicted with another update. Reload stock and retry with a new idempotency key.") from exc
    return movement
