"""Unified organization-scoped shipment tracking and milestone timeline APIs."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.core.security import utc_now, verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import (
    ExportOrder, ExportShipment, ExportShipmentMilestone, ImportOrder,
    ImportShipment, ImportShipmentMilestone, User, UserSession,
)
from app.schemas.shipments import ShipmentMilestoneCreate, ShipmentMilestoneOut, ShipmentOut, ShipmentType, ShipmentUpdate

router = APIRouter(prefix="/shipments", tags=["shipments"])

IMPORT_TRANSITIONS = {
    "planned": {"planned", "in_transit", "delayed", "cancelled"},
    "in_transit": {"in_transit", "arrived", "delayed", "cancelled"},
    "delayed": {"delayed", "in_transit", "arrived", "cancelled"},
    "arrived": {"arrived", "delivered"},
    "delivered": {"delivered"},
    "cancelled": {"cancelled"},
}
EXPORT_TRANSITIONS = {"in_transit": {"in_transit", "delayed"}, "delayed": {"delayed", "in_transit"}, "delivered": {"delivered"}}


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _shipment_record(db: Session, organization_id: UUID, shipment_type: str, shipment_id: UUID, *, lock: bool = False):
    if shipment_type == "import":
        query = db.query(ImportShipment).filter(ImportShipment.id == shipment_id, ImportShipment.organization_id == organization_id)
        return query.with_for_update().one_or_none() if lock else query.one_or_none()
    if shipment_type == "export":
        query = db.query(ExportShipment).filter(ExportShipment.id == shipment_id, ExportShipment.organization_id == organization_id)
        return query.with_for_update().one_or_none() if lock else query.one_or_none()
    raise HTTPException(status_code=422, detail="shipment_type must be 'import' or 'export'.")


def _shipment_payload(db: Session, shipment_type: str, shipment) -> dict:
    if shipment_type == "import":
        order = db.query(ImportOrder).filter(ImportOrder.id == shipment.order_id, ImportOrder.organization_id == shipment.organization_id).one_or_none()
        updated_at = shipment.updated_at
    else:
        order = db.query(ExportOrder).filter(ExportOrder.id == shipment.order_id, ExportOrder.organization_id == shipment.organization_id).one_or_none()
        updated_at = shipment.updated_at
    if order is None:
        raise HTTPException(status_code=404, detail="Related order not found.")
    return {
        "id": shipment.id,
        "organization_id": shipment.organization_id,
        "shipment_type": shipment_type,
        "order_id": shipment.order_id,
        "order_reference": order.reference,
        "shipment_reference": shipment.shipment_reference,
        "carrier": shipment.carrier,
        "tracking_reference": shipment.tracking_reference,
        "transport_mode": shipment.transport_mode,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "estimated_departure": shipment.estimated_departure,
        "actual_departure": shipment.actual_departure,
        "estimated_arrival": shipment.estimated_arrival,
        "actual_arrival": shipment.actual_arrival,
        "status": shipment.status,
        "delay_reason": shipment.delay_reason,
        "notes": shipment.notes,
        "created_at": shipment.created_at,
        "updated_at": updated_at,
    }


@router.get("", response_model=list[ShipmentOut], summary="List import and export shipments in one timeline")
def list_shipments(
    organization_id: UUID,
    shipment_type: ShipmentType | None = None,
    shipment_status: str | None = Query(default=None, alias="status", max_length=24),
    transport_mode: str | None = Query(default=None, max_length=16),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "shipments.read")
    result: list[dict] = []
    if shipment_type in (None, ShipmentType.IMPORT):
        query = db.query(ImportShipment).filter(ImportShipment.organization_id == organization_id)
        if shipment_status:
            query = query.filter(ImportShipment.status == shipment_status)
        if transport_mode:
            query = query.filter(ImportShipment.transport_mode == transport_mode)
        if search:
            query = query.filter(
                ImportShipment.shipment_reference.ilike(f"%{search.strip()}%")
                | ImportShipment.tracking_reference.ilike(f"%{search.strip()}%")
                | ImportShipment.carrier.ilike(f"%{search.strip()}%")
            )
        result.extend(_shipment_payload(db, "import", row) for row in query.order_by(ImportShipment.created_at.desc()).limit(limit).all())
    if shipment_type in (None, ShipmentType.EXPORT):
        query = db.query(ExportShipment).filter(ExportShipment.organization_id == organization_id)
        if shipment_status:
            query = query.filter(ExportShipment.status == shipment_status)
        if transport_mode:
            query = query.filter(ExportShipment.transport_mode == transport_mode)
        if search:
            query = query.filter(
                ExportShipment.shipment_reference.ilike(f"%{search.strip()}%")
                | ExportShipment.tracking_reference.ilike(f"%{search.strip()}%")
                | ExportShipment.carrier.ilike(f"%{search.strip()}%")
            )
        result.extend(_shipment_payload(db, "export", row) for row in query.order_by(ExportShipment.created_at.desc()).limit(limit).all())
    result.sort(key=lambda row: row["created_at"], reverse=True)
    return result[:limit]


@router.patch("/{shipment_type}/{shipment_id}", response_model=ShipmentOut, summary="Update shipment tracking details and manual status")
def update_shipment(
    shipment_type: ShipmentType,
    shipment_id: UUID,
    organization_id: UUID,
    payload: ShipmentUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "shipments.update")
    shipment = _shipment_record(db, organization_id, shipment_type.value, shipment_id, lock=True)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    if shipment_type == ShipmentType.EXPORT and shipment.status == "delivered":
        raise HTTPException(status_code=409, detail="A delivered export shipment cannot be changed.")
    changes = payload.model_dump(exclude_unset=True)
    next_status = payload.status.value if payload.status else shipment.status
    allowed = IMPORT_TRANSITIONS if shipment_type == ShipmentType.IMPORT else EXPORT_TRANSITIONS
    if next_status not in allowed.get(shipment.status, set()):
        raise HTTPException(status_code=409, detail=f"Shipment status cannot transition from {shipment.status} to {next_status}.")
    if next_status == "delayed" and not (payload.delay_reason or shipment.delay_reason):
        raise HTTPException(status_code=422, detail="A delay reason is required when marking a shipment delayed.")
    if shipment_type == ShipmentType.EXPORT and next_status == "delivered" and shipment.status != "delivered":
        raise HTTPException(status_code=409, detail="Export shipment delivery must be recorded through its delivery workflow.")
    for key, value in changes.items():
        if key == "status":
            continue
        if key == "actual_arrival" and shipment_type == ShipmentType.EXPORT:
            raise HTTPException(status_code=422, detail="Export arrival is determined by the delivery workflow.")
        setattr(shipment, key, value)
    previous_status = shipment.status
    shipment.status = next_status
    if next_status == "in_transit" and previous_status == "delayed" and "delay_reason" not in changes:
        shipment.delay_reason = None
    if shipment_type == ShipmentType.IMPORT:
        order = db.query(ImportOrder).filter(ImportOrder.id == shipment.order_id, ImportOrder.organization_id == organization_id).with_for_update().one()
        if shipment.actual_departure:
            order.actual_departure_date = shipment.actual_departure
        if shipment.actual_arrival:
            order.actual_arrival_date = shipment.actual_arrival
        if previous_status != next_status:
            db.add(ImportShipmentMilestone(
                organization_id=organization_id, order_id=shipment.order_id, shipment_id=shipment.id,
                name=f"Status changed to {next_status.replace('_', ' ')}",
                description=payload.delay_reason if next_status == "delayed" else None,
                occurred_at=utc_now(), created_by_user_id=user.id,
            ))
    else:
        if previous_status != next_status:
            db.add(ExportShipmentMilestone(
                organization_id=organization_id, order_id=shipment.order_id, shipment_id=shipment.id,
                name=f"Status changed to {next_status.replace('_', ' ')}",
                description=payload.delay_reason if next_status == "delayed" else None,
                occurred_at=utc_now(), created_by_user_id=user.id,
            ))
    db.commit()
    db.refresh(shipment)
    return _shipment_payload(db, shipment_type.value, shipment)


@router.get("/{shipment_type}/{shipment_id}/milestones", response_model=list[ShipmentMilestoneOut], summary="List a shipment's chronological milestones")
def list_shipment_milestones(
    shipment_type: ShipmentType,
    shipment_id: UUID,
    organization_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "shipments.read")
    shipment = _shipment_record(db, organization_id, shipment_type.value, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    model = ImportShipmentMilestone if shipment_type == ShipmentType.IMPORT else ExportShipmentMilestone
    return db.query(model).filter(
        model.organization_id == organization_id,
        model.shipment_id == shipment_id,
        model.order_id == shipment.order_id,
    ).order_by(model.occurred_at.asc(), model.created_at.asc()).all()


@router.post("/{shipment_type}/{shipment_id}/milestones", response_model=ShipmentMilestoneOut, status_code=status.HTTP_201_CREATED, summary="Add a manual shipment milestone")
def create_shipment_milestone(
    shipment_type: ShipmentType,
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
    shipment = _shipment_record(db, organization_id, shipment_type.value, shipment_id, lock=True)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    model = ImportShipmentMilestone if shipment_type == ShipmentType.IMPORT else ExportShipmentMilestone
    milestone = model(
        organization_id=organization_id,
        order_id=shipment.order_id,
        shipment_id=shipment.id,
        name=payload.name,
        description=payload.description,
        occurred_at=payload.occurred_at,
        created_by_user_id=user.id,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone
