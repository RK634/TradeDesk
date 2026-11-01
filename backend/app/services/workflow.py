"""Shared task, approval, and notification workflow helpers."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import ROLE_PERMISSIONS, require_org_permission
from app.models import (
    ApprovalEvent, ApprovalRequest, ApprovalRule, Customer, ExportOrder, ImportOrder,
    Invoice, InventoryLocation, Notification, NotificationPreference, OrganizationMembership,
    Payment, Product, Supplier, Task, TradeDocument, ImportShipment, ExportShipment,
)

DEFAULT_APPROVAL_ROLES: dict[str, list[str]] = {
    "import_order": ["organization_owner", "administrator"],
    "export_order": ["organization_owner", "administrator"],
    "invoice": ["organization_owner", "administrator", "finance_staff"],
    "payment": ["organization_owner", "administrator", "finance_staff"],
    "task": ["organization_owner", "administrator"],
    "custom": ["organization_owner", "administrator"],
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def verify_mutation(request, csrf_token: str | None, session) -> None:
    from app.core.security import verify_csrf, verify_same_origin_if_present
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def validate_assignee(db: Session, organization_id: UUID, user_id: UUID | None) -> None:
    if user_id is None:
        return
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.is_active.is_(True),
    ).one_or_none()
    if membership is None:
        raise HTTPException(status_code=422, detail="The assignee must be an active member of this organization.")


def validate_related_entity(db: Session, organization_id: UUID, entity_type: str | None, entity_id: UUID | None) -> None:
    if entity_type is None and entity_id is None:
        return
    model = {
        "import_order": ImportOrder,
        "export_order": ExportOrder,
        "invoice": Invoice,
        "document": TradeDocument,
    }.get(entity_type)
    if entity_type == "shipment":
        found = db.query(ImportShipment.id).filter(ImportShipment.id == entity_id, ImportShipment.organization_id == organization_id).first()
        if not found:
            found = db.query(ExportShipment.id).filter(ExportShipment.id == entity_id, ExportShipment.organization_id == organization_id).first()
    else:
        found = db.query(model.id).filter(model.id == entity_id, model.organization_id == organization_id).first() if model else None
    if not found:
        raise HTTPException(status_code=422, detail="The related record was not found in this organization.")


def create_notification(
    db: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    category: str,
    title: str,
    message: str,
    dedupe_key: str,
    link_path: str | None = None,
    payload: dict | None = None,
) -> Notification | None:
    """Create a notification unless preference is disabled or this event already exists."""
    preference = db.query(NotificationPreference).filter(
        NotificationPreference.organization_id == organization_id,
        NotificationPreference.user_id == user_id,
        NotificationPreference.category == category,
    ).one_or_none()
    if preference is not None and not preference.in_app_enabled:
        return None
    existing = db.query(Notification).filter(
        Notification.organization_id == organization_id,
        Notification.user_id == user_id,
        Notification.dedupe_key == dedupe_key,
    ).one_or_none()
    if existing:
        return existing
    record = Notification(
        organization_id=organization_id,
        user_id=user_id,
        category=category,
        title=title,
        message=message,
        link_path=link_path,
        payload=payload or {},
        dedupe_key=dedupe_key,
    )
    db.add(record)
    db.flush()
    return record


def notify_user_roles(
    db: Session,
    *, organization_id: UUID,
    roles: list[str] | set[str],
    category: str,
    title: str,
    message: str,
    dedupe_key: str,
    link_path: str | None = None,
    payload: dict | None = None,
    exclude_user_id: UUID | None = None,
) -> int:
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.is_active.is_(True),
        OrganizationMembership.role.in_(list(roles)),
    ).all()
    count = 0
    for membership in memberships:
        if exclude_user_id and membership.user_id == exclude_user_id:
            continue
        if create_notification(
            db,
            organization_id=organization_id,
            user_id=membership.user_id,
            category=category,
            title=title,
            message=message,
            dedupe_key=dedupe_key,
            link_path=link_path,
            payload=payload,
        ):
            count += 1
    return count


def get_approval_roles(db: Session, organization_id: UUID, action: str) -> tuple[list[str], bool, bool]:
    rule = db.query(ApprovalRule).filter(
        ApprovalRule.organization_id == organization_id,
        ApprovalRule.business_action == action,
    ).one_or_none()
    if rule is None:
        # Existing import/export workflows historically allowed the organization owner
        # to submit and approve the same order. Organizations can explicitly disable
        # this behavior in their configured rule; other business actions default to no self-approval.
        return DEFAULT_APPROVAL_ROLES[action], True, action in {"import_order", "export_order"}
    return list(rule.required_roles or []), bool(rule.is_enabled), bool(rule.allow_self_approval)


def assert_approval_role(db: Session, organization_id: UUID, user_id: UUID, action: str, requester_id: UUID | None = None) -> None:
    membership = require_org_permission(db, user_id, organization_id, "approvals.decide")
    roles, enabled, allow_self = get_approval_roles(db, organization_id, action)
    if not enabled:
        raise HTTPException(status_code=409, detail="Approval is disabled for this business action.")
    if membership.role not in roles:
        raise HTTPException(status_code=403, detail="Your organization role is not authorized for this approval.")
    if requester_id is not None and requester_id == user_id and not allow_self:
        raise HTTPException(status_code=403, detail="Self-approval is disabled for this business action.")



def ensure_approval_enabled(db: Session, organization_id: UUID, action: str) -> None:
    _, enabled, _ = get_approval_roles(db, organization_id, action)
    if not enabled:
        raise HTTPException(status_code=409, detail="Approval is disabled for this business action.")


def assert_order_approval_role(db: Session, organization_id: UUID, user_id: UUID, action: str, order_id: UUID) -> None:
    pending = db.query(ApprovalRequest).filter(
        ApprovalRequest.organization_id == organization_id,
        ApprovalRequest.related_entity_type == action,
        ApprovalRequest.related_entity_id == order_id,
        ApprovalRequest.status == "submitted",
    ).order_by(ApprovalRequest.submitted_at.desc()).first()
    assert_approval_role(
        db, organization_id, user_id, action,
        requester_id=pending.requested_by_user_id if pending else None,
    )

def sync_order_approval(
    db: Session,
    *, organization_id: UUID,
    action: str,
    order_id: UUID,
    actor_id: UUID,
    transition: str,
    title: str | None = None,
    note: str | None = None,
) -> ApprovalRequest | None:
    """Mirror import/export-specific approvals into the central approval inbox/history."""
    request_record = db.query(ApprovalRequest).filter(
        ApprovalRequest.organization_id == organization_id,
        ApprovalRequest.related_entity_type == action,
        ApprovalRequest.related_entity_id == order_id,
        ApprovalRequest.status == "submitted",
    ).order_by(ApprovalRequest.submitted_at.desc()).first()
    if transition == "submitted":
        _, enabled, _ = get_approval_roles(db, organization_id, action)
        if not enabled:
            raise HTTPException(status_code=409, detail="Approval is disabled for this business action.")
        if request_record is None:
            request_record = ApprovalRequest(
                organization_id=organization_id,
                business_action=action,
                related_entity_type=action,
                related_entity_id=order_id,
                title=title or f"{action.replace('_', ' ').title()} {order_id}",
                requested_by_user_id=actor_id,
                status="submitted",
            )
            db.add(request_record)
            db.flush()
            db.add(ApprovalEvent(
                organization_id=organization_id,
                approval_request_id=request_record.id,
                from_status=None,
                to_status="submitted",
                note=note,
                actor_user_id=actor_id,
            ))
            roles, _, _ = get_approval_roles(db, organization_id, action)
            notify_user_roles(
                db, organization_id=organization_id, roles=roles, category="approval",
                title="Approval requested", message=title or request_record.title, dedupe_key=f"approval:{request_record.id}:submitted",
                link_path=f"/app/{'imports' if action == 'import_order' else 'exports'}",
                payload={"approval_request_id": str(request_record.id), "related_entity_id": str(order_id)},
                exclude_user_id=actor_id,
            )
        return request_record
    if request_record is None:
        return None
    previous = request_record.status
    request_record.status = transition
    request_record.decided_by_user_id = actor_id if transition != "cancelled" else request_record.decided_by_user_id
    request_record.decision_note = note
    request_record.decided_at = utc_now()
    db.add(ApprovalEvent(
        organization_id=organization_id,
        approval_request_id=request_record.id,
        from_status=previous,
        to_status=transition,
        note=note,
        actor_user_id=actor_id,
    ))
    create_notification(
        db, organization_id=organization_id, user_id=request_record.requested_by_user_id,
        category="approval", title=f"Approval {transition}", message=f"{request_record.title}: {note or transition.title()}.",
        dedupe_key=f"approval:{request_record.id}:{transition}",
        link_path=f"/app/{'imports' if action == 'import_order' else 'exports'}",
        payload={"approval_request_id": str(request_record.id)},
    )
    return request_record
