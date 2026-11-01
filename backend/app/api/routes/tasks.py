"""Organization-scoped task management, assignment, comments, and completion history."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.db.session import get_db
from app.models import Task, TaskComment, TaskStatusHistory, User
from app.models.session import UserSession
from app.schemas.workflow import (
    TaskCommentCreate, TaskCommentOut, TaskCreate, TaskOut, TaskPage,
    TaskStatusHistoryOut, TaskStatusUpdate, TaskUpdate,
)
from app.services.workflow import create_notification, validate_assignee, validate_related_entity, verify_mutation

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _scoped_task(db: Session, user_id: UUID, organization_id: UUID, task_id: UUID, permission: str = "tasks.read", *, lock: bool = False) -> Task:
    require_org_permission(db, user_id, organization_id, permission)
    query = db.query(Task).filter(Task.id == task_id, Task.organization_id == organization_id)
    if lock:
        query = query.with_for_update()
    task = query.one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


def _task_payload(db: Session, task: Task, include_details: bool = True) -> dict:
    assignee = db.get(User, task.assigned_to_user_id) if task.assigned_to_user_id else None
    creator = db.get(User, task.created_by_user_id)
    comments = []
    history = []
    if include_details:
        for row in db.query(TaskComment).filter(TaskComment.task_id == task.id, TaskComment.organization_id == task.organization_id).order_by(TaskComment.created_at.asc()).all():
            author = db.get(User, row.author_user_id)
            comments.append({**row.__dict__, "author_name": author.full_name if author else "Former user"})
        for row in db.query(TaskStatusHistory).filter(TaskStatusHistory.task_id == task.id, TaskStatusHistory.organization_id == task.organization_id).order_by(TaskStatusHistory.created_at.asc()).all():
            actor = db.get(User, row.actor_user_id)
            history.append({**row.__dict__, "actor_name": actor.full_name if actor else "Former user"})
    return {
        "id": task.id,
        "organization_id": task.organization_id,
        "title": task.title,
        "description": task.description,
        "assigned_to_user_id": task.assigned_to_user_id,
        "assigned_to_name": assignee.full_name if assignee else None,
        "related_entity_type": task.related_entity_type,
        "related_entity_id": task.related_entity_id,
        "priority": task.priority,
        "status": task.status,
        "due_at": task.due_at,
        "completed_at": task.completed_at,
        "created_by_user_id": task.created_by_user_id,
        "created_by_name": creator.full_name if creator else "Former user",
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "comments": comments,
        "history": history,
    }


@router.get("", response_model=TaskPage, summary="List organization tasks")
def list_tasks(
    organization_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status_filter: Literal["open", "in_progress", "blocked", "completed", "cancelled"] | None = Query(default=None, alias="status"),
    priority: Literal["low", "normal", "high", "urgent"] | None = None,
    assigned_to_me: bool = False,
    search: str | None = Query(default=None, max_length=120),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "tasks.read")
    query = db.query(Task).filter(Task.organization_id == organization_id)
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority:
        query = query.filter(Task.priority == priority)
    if assigned_to_me:
        query = query.filter(Task.assigned_to_user_id == user.id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    total = query.count()
    rows = query.order_by(Task.due_at.asc().nullslast(), Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_task_payload(db, row, include_details=False) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED, summary="Create a task")
def create_task(
    organization_id: UUID,
    payload: TaskCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "tasks.create")
    validate_assignee(db, organization_id, payload.assigned_to_user_id)
    validate_related_entity(db, organization_id, payload.related_entity_type, payload.related_entity_id)
    task = Task(
        organization_id=organization_id,
        title=payload.title.strip(),
        description=payload.description,
        assigned_to_user_id=payload.assigned_to_user_id,
        related_entity_type=payload.related_entity_type,
        related_entity_id=payload.related_entity_id,
        priority=payload.priority,
        status="open",
        due_at=payload.due_at,
        created_by_user_id=user.id,
    )
    db.add(task)
    db.flush()
    db.add(TaskStatusHistory(organization_id=organization_id, task_id=task.id, from_status=None, to_status="open", note="Task created", actor_user_id=user.id))
    if task.assigned_to_user_id:
        create_notification(
            db, organization_id=organization_id, user_id=task.assigned_to_user_id,
            category="task", title="New task assigned", message=task.title,
            dedupe_key=f"task:{task.id}:assigned:{task.assigned_to_user_id}",
            link_path="/app/tasks", payload={"task_id": str(task.id)},
        )
    db.commit()
    db.refresh(task)
    return _task_payload(db, task)


@router.get("/{task_id}", response_model=TaskOut, summary="Get task details and activity")
def get_task(task_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _scoped_task(db, user.id, organization_id, task_id)
    return _task_payload(db, task)


@router.patch("/{task_id}", response_model=TaskOut, summary="Update task details or assignment")
def update_task(
    task_id: UUID,
    organization_id: UUID,
    payload: TaskUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    task = _scoped_task(db, user.id, organization_id, task_id, "tasks.update", lock=True)
    changes = payload.model_dump(exclude_unset=True)
    if "assigned_to_user_id" in changes:
        require_org_permission(db, user.id, organization_id, "tasks.assign")
        validate_assignee(db, organization_id, changes["assigned_to_user_id"])
    old_assignee = task.assigned_to_user_id
    for key, value in changes.items():
        if key == "title" and value is not None:
            value = value.strip()
        setattr(task, key, value)
    if task.assigned_to_user_id and task.assigned_to_user_id != old_assignee:
        create_notification(
            db, organization_id=organization_id, user_id=task.assigned_to_user_id,
            category="task", title="Task assigned to you", message=task.title,
            dedupe_key=f"task:{task.id}:assigned:{task.assigned_to_user_id}:{datetime.now(timezone.utc).isoformat()}",
            link_path="/app/tasks", payload={"task_id": str(task.id)},
        )
    db.commit()
    db.refresh(task)
    return _task_payload(db, task)


@router.post("/{task_id}/status", response_model=TaskOut, summary="Change task status with history")
def update_task_status(
    task_id: UUID,
    organization_id: UUID,
    payload: TaskStatusUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    task = _scoped_task(db, user.id, organization_id, task_id, "tasks.update", lock=True)
    allowed = {
        "open": {"in_progress", "blocked", "completed", "cancelled"},
        "in_progress": {"open", "blocked", "completed", "cancelled"},
        "blocked": {"open", "in_progress", "completed", "cancelled"},
        "completed": {"open", "in_progress"},
        "cancelled": set(),
    }
    if payload.status not in allowed[task.status]:
        raise HTTPException(status_code=409, detail=f"Task cannot transition from {task.status} to {payload.status}.")
    previous = task.status
    task.status = payload.status
    task.completed_at = datetime.now(timezone.utc) if payload.status == "completed" else None
    db.add(TaskStatusHistory(
        organization_id=organization_id, task_id=task.id, from_status=previous,
        to_status=payload.status, note=payload.note, actor_user_id=user.id,
    ))
    db.commit()
    db.refresh(task)
    return _task_payload(db, task)


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=status.HTTP_201_CREATED, summary="Add a task comment")
def add_task_comment(
    task_id: UUID,
    organization_id: UUID,
    payload: TaskCommentCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_mutation(request, x_csrf_token, session)
    task = _scoped_task(db, user.id, organization_id, task_id, "tasks.comment")
    comment = TaskComment(organization_id=organization_id, task_id=task.id, author_user_id=user.id, body=payload.body.strip())
    db.add(comment)
    db.flush()
    recipients = {task.created_by_user_id, task.assigned_to_user_id}
    recipients.discard(None)
    recipients.discard(user.id)
    for recipient in recipients:
        create_notification(
            db, organization_id=organization_id, user_id=recipient, category="task",
            title="New task comment", message=f"{user.full_name} commented on: {task.title}",
            dedupe_key=f"task-comment:{comment.id}:{recipient}", link_path="/app/tasks",
            payload={"task_id": str(task.id), "comment_id": str(comment.id)},
        )
    db.commit()
    db.refresh(comment)
    return {**comment.__dict__, "author_name": user.full_name}
