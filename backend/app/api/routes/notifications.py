"""In-app notification inbox, preferences, and automation execution visibility."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.db.session import get_db
from app.models import AutomationLog, Notification, NotificationPreference, User
from app.models.session import UserSession
from app.schemas.workflow import (
    AutomationLogOut, NotificationOut, NotificationPage,
    NotificationPreferenceOut, NotificationPreferenceUpdate,
)
from app.services.automation import run_automation_cycle
from app.services.workflow import verify_mutation

router = APIRouter(prefix="/notifications", tags=["notifications"])
AUTOMATION_CATEGORIES = ["task", "approval", "invoice", "shipment", "inventory", "document", "order", "system"]


@router.get("", response_model=NotificationPage, summary="List the current user's notifications")
def list_notifications(
    organization_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    unread_only: bool = False,
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "notifications.read")
    query = db.query(Notification).filter(
        Notification.organization_id == organization_id,
        Notification.user_id == user.id,
    )
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    if category:
        if category not in AUTOMATION_CATEGORIES:
            raise HTTPException(status_code=422, detail="Unsupported notification category.")
        query = query.filter(Notification.category == category)
    total = query.count()
    unread_count = db.query(Notification).filter(
        Notification.organization_id == organization_id,
        Notification.user_id == user.id,
        Notification.read_at.is_(None),
    ).count()
    items = query.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "unread_count": unread_count, "page": page, "page_size": page_size}


@router.get("/unread-count", summary="Get unread notification count")
def unread_count(organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_permission(db, user.id, organization_id, "notifications.read")
    count = db.query(Notification).filter(
        Notification.organization_id == organization_id,
        Notification.user_id == user.id,
        Notification.read_at.is_(None),
    ).count()
    return {"unread_count": count}


@router.patch("/{notification_id}/read", response_model=NotificationOut, summary="Mark a notification as read")
def mark_notification_read(
    notification_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "notifications.read")
    row = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.organization_id == organization_id,
        Notification.user_id == user.id,
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return row


@router.post("/read-all", summary="Mark all notifications as read")
def mark_all_read(
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "notifications.read")
    updated = db.query(Notification).filter(
        Notification.organization_id == organization_id,
        Notification.user_id == user.id,
        Notification.read_at.is_(None),
    ).update({Notification.read_at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    return {"updated_count": updated}


@router.get("/preferences", response_model=list[NotificationPreferenceOut], summary="Get notification preferences")
def get_preferences(organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_permission(db, user.id, organization_id, "notifications.read")
    rows = db.query(NotificationPreference).filter(
        NotificationPreference.organization_id == organization_id,
        NotificationPreference.user_id == user.id,
    ).all()
    by_category = {row.category: row for row in rows}
    now = datetime.now(timezone.utc)
    return [
        {"category": category, "in_app_enabled": by_category[category].in_app_enabled if category in by_category else True,
         "updated_at": by_category[category].updated_at if category in by_category else now}
        for category in AUTOMATION_CATEGORIES
    ]


@router.put("/preferences", response_model=NotificationPreferenceOut, summary="Update a notification preference")
def update_preference(
    organization_id: UUID,
    payload: NotificationPreferenceUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "notifications.read")
    row = db.query(NotificationPreference).filter(
        NotificationPreference.organization_id == organization_id,
        NotificationPreference.user_id == user.id,
        NotificationPreference.category == payload.category,
    ).one_or_none()
    if row is None:
        row = NotificationPreference(organization_id=organization_id, user_id=user.id, category=payload.category, in_app_enabled=payload.in_app_enabled)
        db.add(row)
    else:
        row.in_app_enabled = payload.in_app_enabled
    db.commit()
    db.refresh(row)
    return row


@router.get("/automation-logs", response_model=list[AutomationLogOut], summary="List recent automation execution logs")
def list_automation_logs(
    organization_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "notifications.manage")
    return db.query(AutomationLog).filter(
        AutomationLog.organization_id == organization_id,
    ).order_by(AutomationLog.created_at.desc()).limit(limit).all()


@router.post("/automation/run", summary="Run reminder checks immediately")
def run_automation_now(
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "notifications.manage")
    # The common scheduler scans all organizations. This manual action remains restricted
    # to organization admins; it returns only counts, never other organizations' data.
    totals = run_automation_cycle(db, organization_id=organization_id)
    return {"organization_id": str(organization_id), "generated": totals}
