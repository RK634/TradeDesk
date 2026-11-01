"""Role-configurable approvals with immutable decision history."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.db.session import get_db
from app.models import (
    ApprovalEvent, ApprovalRequest, ApprovalRule, ExportOrder, ImportOrder, Invoice,
    OrganizationMembership, Payment, Task, User,
)
from app.models.session import UserSession
from app.schemas.workflow import (
    ApprovalCancel, ApprovalDecision, ApprovalEventOut, ApprovalRequestOut,
    ApprovalRuleOut, ApprovalRuleUpsert, ApprovalSubmit,
)
from app.services.workflow import DEFAULT_APPROVAL_ROLES, assert_approval_role, create_notification, get_approval_roles, notify_user_roles, verify_mutation

router = APIRouter(tags=["approvals"])


def _rule_payload(row: ApprovalRule) -> dict:
    return {
        "id": row.id, "organization_id": row.organization_id, "business_action": row.business_action,
        "is_enabled": row.is_enabled, "required_roles": row.required_roles or [],
        "minimum_amount": row.minimum_amount, "allow_self_approval": row.allow_self_approval,
        "updated_at": row.updated_at,
    }


def _approval_payload(db: Session, row: ApprovalRequest) -> dict:
    requester = db.get(User, row.requested_by_user_id)
    decider = db.get(User, row.decided_by_user_id) if row.decided_by_user_id else None
    events = db.query(ApprovalEvent).filter(
        ApprovalEvent.approval_request_id == row.id,
        ApprovalEvent.organization_id == row.organization_id,
    ).order_by(ApprovalEvent.created_at.asc()).all()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "business_action": row.business_action,
        "related_entity_type": row.related_entity_type,
        "related_entity_id": row.related_entity_id,
        "title": row.title,
        "requested_by_user_id": row.requested_by_user_id,
        "requested_by_name": requester.full_name if requester else "Former user",
        "decided_by_user_id": row.decided_by_user_id,
        "decided_by_name": decider.full_name if decider else None,
        "status": row.status,
        "request_note": row.request_note,
        "decision_note": row.decision_note,
        "requested_amount": row.requested_amount,
        "currency": row.currency,
        "submitted_at": row.submitted_at,
        "decided_at": row.decided_at,
        "events": [{
            "id": event.id, "from_status": event.from_status, "to_status": event.to_status,
            "note": event.note, "actor_user_id": event.actor_user_id,
            "actor_name": (db.get(User, event.actor_user_id).full_name if db.get(User, event.actor_user_id) else "Former user"),
            "created_at": event.created_at,
        } for event in events],
    }


def _validate_target(db: Session, organization_id: UUID, payload: ApprovalSubmit) -> None:
    if payload.related_entity_type in {"import_order", "export_order"}:
        raise HTTPException(status_code=409, detail="Import and export order approvals are submitted and decided through their order workflow endpoints.")
    mapping = {"invoice": Invoice, "payment": Payment, "task": Task}
    if payload.related_entity_type == "custom":
        return
    model = mapping.get(payload.related_entity_type)
    if model is None or db.query(model.id).filter(model.id == payload.related_entity_id, model.organization_id == organization_id).first() is None:
        raise HTTPException(status_code=422, detail="The approval target was not found in this organization.")


@router.get("/approval-rules", response_model=list[ApprovalRuleOut], summary="List approval rules")
def list_approval_rules(organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_permission(db, user.id, organization_id, "approvals.read")
    rows = db.query(ApprovalRule).filter(ApprovalRule.organization_id == organization_id).order_by(ApprovalRule.business_action.asc()).all()
    configured = {row.business_action: row for row in rows}
    result = []
    for action, roles in DEFAULT_APPROVAL_ROLES.items():
        if action in configured:
            result.append(_rule_payload(configured[action]))
        else:
            result.append({
                "id": None, "organization_id": organization_id, "business_action": action,
                "is_enabled": True, "required_roles": roles, "minimum_amount": None,
                "allow_self_approval": action in {"import_order", "export_order"}, "updated_at": datetime.now(timezone.utc),
            })
    return result


@router.put("/approval-rules/{business_action}", response_model=ApprovalRuleOut, summary="Configure required approval roles for an action")
def upsert_approval_rule(
    business_action: str,
    organization_id: UUID,
    payload: ApprovalRuleUpsert,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "approvals.rules.manage")
    if business_action not in DEFAULT_APPROVAL_ROLES:
        raise HTTPException(status_code=422, detail="Unsupported approval business action.")
    row = db.query(ApprovalRule).filter(
        ApprovalRule.organization_id == organization_id,
        ApprovalRule.business_action == business_action,
    ).one_or_none()
    if row is None:
        row = ApprovalRule(
            organization_id=organization_id, business_action=business_action,
            created_by_user_id=user.id, updated_by_user_id=user.id,
        )
        db.add(row)
    row.is_enabled = payload.is_enabled
    row.required_roles = list(dict.fromkeys(payload.required_roles))
    row.minimum_amount = payload.minimum_amount
    row.allow_self_approval = payload.allow_self_approval
    row.updated_by_user_id = user.id
    db.commit()
    db.refresh(row)
    return _rule_payload(row)


@router.get("/approvals", response_model=list[ApprovalRequestOut], summary="List pending and historical approvals")
def list_approvals(
    organization_id: UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    business_action: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "approvals.read")
    query = db.query(ApprovalRequest).filter(ApprovalRequest.organization_id == organization_id)
    if status_filter:
        if status_filter not in {"submitted", "approved", "rejected", "returned", "cancelled"}:
            raise HTTPException(status_code=422, detail="Unsupported approval status.")
        query = query.filter(ApprovalRequest.status == status_filter)
    if business_action:
        query = query.filter(ApprovalRequest.business_action == business_action)
    rows = query.order_by(ApprovalRequest.submitted_at.desc()).limit(200).all()
    return [_approval_payload(db, row) for row in rows]


@router.post("/approvals", response_model=ApprovalRequestOut, status_code=status.HTTP_201_CREATED, summary="Submit an action for approval")
def submit_approval(
    organization_id: UUID,
    payload: ApprovalSubmit,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "approvals.submit")
    _validate_target(db, organization_id, payload)
    roles, enabled, _ = get_approval_roles(db, organization_id, payload.business_action)
    if not enabled:
        raise HTTPException(status_code=409, detail="Approval is disabled for this business action.")
    rule = db.query(ApprovalRule).filter(ApprovalRule.organization_id == organization_id, ApprovalRule.business_action == payload.business_action).one_or_none()
    if rule and rule.minimum_amount is not None:
        if payload.requested_amount is None:
            raise HTTPException(status_code=422, detail="requested_amount is required by the configured approval threshold.")
        if payload.requested_amount < Decimal(rule.minimum_amount):
            raise HTTPException(status_code=409, detail="This transaction is below the configured approval threshold.")
    active = db.query(ApprovalRequest).filter(
        ApprovalRequest.organization_id == organization_id,
        ApprovalRequest.related_entity_type == payload.related_entity_type,
        ApprovalRequest.related_entity_id == payload.related_entity_id,
        ApprovalRequest.status == "submitted",
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="An approval request for this record is already pending.")
    row = ApprovalRequest(
        organization_id=organization_id,
        business_action=payload.business_action,
        related_entity_type=payload.related_entity_type,
        related_entity_id=payload.related_entity_id,
        title=payload.title.strip(),
        requested_by_user_id=user.id,
        status="submitted",
        request_note=payload.request_note,
        requested_amount=payload.requested_amount,
        currency=payload.currency,
    )
    db.add(row)
    db.flush()
    db.add(ApprovalEvent(organization_id=organization_id, approval_request_id=row.id, from_status=None, to_status="submitted", note=payload.request_note, actor_user_id=user.id))
    notify_user_roles(
        db, organization_id=organization_id, roles=roles, category="approval", title="Approval requested",
        message=payload.title, dedupe_key=f"approval:{row.id}:submitted", link_path="/app/approvals",
        payload={"approval_request_id": str(row.id)}, exclude_user_id=user.id,
    )
    db.commit()
    db.refresh(row)
    return _approval_payload(db, row)


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalRequestOut, summary="Approve, reject, or return an approval")
def decide_approval(
    approval_id: UUID,
    organization_id: UUID,
    payload: ApprovalDecision,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    membership = require_org_permission(db, user.id, organization_id, "approvals.decide")
    row = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id, ApprovalRequest.organization_id == organization_id).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    if row.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted approval requests can be decided.")
    roles, enabled, allow_self = get_approval_roles(db, organization_id, row.business_action)
    if not enabled:
        raise HTTPException(status_code=409, detail="Approval is disabled for this business action.")
    if membership.role not in roles:
        raise HTTPException(status_code=403, detail="Your role is not configured to approve this business action.")
    if row.requested_by_user_id == user.id and not allow_self:
        raise HTTPException(status_code=403, detail="Self-approval is disabled for this business action.")
    # Import/export order approvals must use their domain endpoints because export approval
    # also reserves stock transactionally. Their decisions are mirrored into this inbox.
    if row.related_entity_type in {"import_order", "export_order"}:
        raise HTTPException(status_code=409, detail="Use the related import/export order workflow to decide this approval; inventory and order state are updated there.")
    previous = row.status
    row.status = payload.status
    row.decided_by_user_id = user.id
    row.decision_note = payload.decision_note
    row.decided_at = datetime.now(timezone.utc)
    db.add(ApprovalEvent(organization_id=organization_id, approval_request_id=row.id, from_status=previous, to_status=payload.status, note=payload.decision_note, actor_user_id=user.id))
    create_notification(
        db, organization_id=organization_id, user_id=row.requested_by_user_id, category="approval",
        title=f"Approval {payload.status}", message=f"{row.title}: {payload.decision_note or payload.status.title()}.",
        dedupe_key=f"approval:{row.id}:{payload.status}", link_path="/app/approvals",
        payload={"approval_request_id": str(row.id)},
    )
    db.commit()
    db.refresh(row)
    return _approval_payload(db, row)


@router.post("/approvals/{approval_id}/cancel", response_model=ApprovalRequestOut, summary="Cancel a pending approval request")
def cancel_approval(
    approval_id: UUID,
    organization_id: UUID,
    payload: ApprovalCancel,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "approvals.submit")
    row = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id, ApprovalRequest.organization_id == organization_id).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    if row.status != "submitted":
        raise HTTPException(status_code=409, detail="Only pending approvals can be cancelled.")
    if row.related_entity_type in {"import_order", "export_order"}:
        raise HTTPException(status_code=409, detail="Use the related import/export order workflow to cancel this approval; order status and reservations must remain synchronized.")
    if row.requested_by_user_id != user.id:
        assert_approval_role(db, organization_id, user.id, row.business_action, requester_id=row.requested_by_user_id)
    previous = row.status
    row.status = "cancelled"
    row.decision_note = payload.reason
    row.decided_by_user_id = user.id
    row.decided_at = datetime.now(timezone.utc)
    db.add(ApprovalEvent(organization_id=organization_id, approval_request_id=row.id, from_status=previous, to_status="cancelled", note=payload.reason, actor_user_id=user.id))
    db.commit()
    db.refresh(row)
    return _approval_payload(db, row)
