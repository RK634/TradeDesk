from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ApprovalRequest, AutomationLog, Notification, Task
from conftest import csrf_headers, register_account


def test_task_lifecycle_and_notification_inbox(client: TestClient, db_session: Session) -> None:
    account = register_account(client)
    organization_id = account["organizations"][0]["organization_id"]

    created = client.post(
        f"/api/v1/tasks?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "title": "Review commercial invoice",
            "description": "Check supplier values and totals.",
            "assigned_to_user_id": account["user"]["id"],
            "priority": "high",
            "due_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["status"] == "open"
    assert task["assigned_to_name"] == "Test Owner"

    comment = client.post(
        f"/api/v1/tasks/{task['id']}/comments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"body": "Please include the customs reference."},
    )
    assert comment.status_code == 201, comment.text
    assert comment.json()["body"] == "Please include the customs reference."

    moved = client.post(
        f"/api/v1/tasks/{task['id']}/status?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"status": "in_progress", "note": "Started review."},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["history"][-1]["to_status"] == "in_progress"

    completed = client.post(
        f"/api/v1/tasks/{task['id']}/status?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"status": "completed", "note": "Review finished."},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["completed_at"] is not None

    inbox = client.get(f"/api/v1/notifications?organization_id={organization_id}")
    assert inbox.status_code == 200, inbox.text
    assert inbox.json()["unread_count"] >= 1
    assigned_notice = next(item for item in inbox.json()["items"] if item["title"] == "New task assigned")

    marked = client.patch(
        f"/api/v1/notifications/{assigned_notice['id']}/read?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={},
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["read_at"] is not None
    assert client.get(f"/api/v1/notifications/unread-count?organization_id={organization_id}").json()["unread_count"] < inbox.json()["unread_count"]


def test_task_and_notifications_are_organization_scoped(client: TestClient) -> None:
    first = register_account(client, email="first-owner@example.com", organization="First Workspace")
    first_org = first["organizations"][0]["organization_id"]
    created = client.post(
        f"/api/v1/tasks?organization_id={first_org}",
        headers=csrf_headers(client),
        json={"title": "First workspace task"},
    )
    assert created.status_code == 201, created.text

    other_client = TestClient(client.app)
    second = register_account(other_client, email="second-owner@example.com", organization="Second Workspace")
    second_org = second["organizations"][0]["organization_id"]
    task_id = created.json()["id"]

    assert other_client.get(f"/api/v1/tasks/{task_id}?organization_id={second_org}").status_code == 404
    assert other_client.get(f"/api/v1/notifications?organization_id={first_org}").status_code == 404


def test_approval_rules_notify_eligible_role_and_record_decision_history(client: TestClient) -> None:
    owner = register_account(client, email="approval-owner@example.com", organization="Approvals Workspace")
    organization_id = owner["organizations"][0]["organization_id"]

    rule = client.put(
        f"/api/v1/approval-rules/task?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "is_enabled": True,
            "required_roles": ["operations_staff"],
            "minimum_amount": None,
            "allow_self_approval": False,
        },
    )
    assert rule.status_code == 200, rule.text
    assert rule.json()["required_roles"] == ["operations_staff"]

    invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=csrf_headers(client),
        json={"email": "ops-approver@example.com", "role": "operations_staff"},
    )
    assert invitation.status_code == 201, invitation.text
    approver_client = TestClient(client.app)
    csrf = approver_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    accepted = approver_client.post(
        "/api/v1/auth/accept-invitation",
        headers={"X-CSRF-Token": csrf},
        json={
            "token": invitation.json()["invitation_token"],
            "full_name": "Operations Approver",
            "password": "operations-approver-password-123",
        },
    )
    assert accepted.status_code == 200, accepted.text

    target_id = str(uuid4())
    submitted = client.post(
        f"/api/v1/approvals?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "business_action": "task",
            "related_entity_type": "custom",
            "related_entity_id": target_id,
            "title": "Approve customs broker change",
            "request_note": "Vendor review completed.",
        },
    )
    assert submitted.status_code == 201, submitted.text
    approval_id = submitted.json()["id"]

    pending_inbox = approver_client.get(f"/api/v1/approvals?organization_id={organization_id}")
    assert pending_inbox.status_code == 200, pending_inbox.text
    assert any(item["id"] == approval_id for item in pending_inbox.json())

    decision = approver_client.post(
        f"/api/v1/approvals/{approval_id}/decision?organization_id={organization_id}",
        headers=csrf_headers(approver_client),
        json={"status": "approved", "decision_note": "Approved after review."},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "approved"
    assert decision.json()["decided_by_name"] == "Operations Approver"
    assert [event["to_status"] for event in decision.json()["events"]] == ["submitted", "approved"]


def test_rejection_requires_reason_and_read_only_cannot_create_tasks(client: TestClient) -> None:
    owner = register_account(client, email="rule-owner@example.com", organization="Rules Workspace")
    organization_id = owner["organizations"][0]["organization_id"]
    task = client.post(
        f"/api/v1/tasks?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"title": "Document review task"},
    )
    assert task.status_code == 201, task.text

    submitted = client.post(
        f"/api/v1/approvals?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "business_action": "task", "related_entity_type": "custom", "related_entity_id": str(uuid4()),
            "title": "Approve new procedure",
        },
    )
    assert submitted.status_code == 201, submitted.text
    invalid_decision = client.post(
        f"/api/v1/approvals/{submitted.json()['id']}/decision?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"status": "rejected", "decision_note": "  "},
    )
    assert invalid_decision.status_code == 422

    invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=csrf_headers(client),
        json={"email": "read-only@example.com", "role": "read_only"},
    ).json()
    read_client = TestClient(client.app)
    csrf = read_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    accepted = read_client.post(
        "/api/v1/auth/accept-invitation",
        headers={"X-CSRF-Token": csrf},
        json={"token": invitation["invitation_token"], "full_name": "Read Only", "password": "read-only-password-12345"},
    )
    assert accepted.status_code == 200, accepted.text
    denied = read_client.post(
        f"/api/v1/tasks?organization_id={organization_id}",
        headers=csrf_headers(read_client),
        json={"title": "Unauthorized task"},
    )
    assert denied.status_code == 403
    assert read_client.get(f"/api/v1/notifications/automation-logs?organization_id={organization_id}").status_code == 403
    assert read_client.post(f"/api/v1/notifications/automation/run?organization_id={organization_id}", headers=csrf_headers(read_client), json={}).status_code == 403


def test_automation_cycle_is_idempotent_and_respects_notification_preferences(client: TestClient, db_session: Session) -> None:
    owner = register_account(client, email="automation-owner@example.com", organization="Automation Workspace")
    organization_id = owner["organizations"][0]["organization_id"]
    due_at = datetime.now(timezone.utc) + timedelta(hours=6)

    created = client.post(
        f"/api/v1/tasks?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"title": "Prepare shipment documents", "assigned_to_user_id": owner["user"]["id"], "due_at": due_at.isoformat()},
    )
    assert created.status_code == 201, created.text

    run_once = client.post(
        f"/api/v1/notifications/automation/run?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={},
    )
    assert run_once.status_code == 200, run_once.text
    assert run_once.json()["generated"]["task_reminders"] == 1
    first_log_count = db_session.query(AutomationLog).filter(AutomationLog.organization_id == UUID(organization_id)).count()
    first_notification_count = db_session.query(Notification).filter(Notification.organization_id == UUID(organization_id)).count()

    run_twice = client.post(
        f"/api/v1/notifications/automation/run?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={},
    )
    assert run_twice.status_code == 200, run_twice.text
    assert run_twice.json()["generated"]["task_reminders"] == 0
    assert db_session.query(AutomationLog).filter(AutomationLog.organization_id == UUID(organization_id)).count() == first_log_count
    assert db_session.query(Notification).filter(Notification.organization_id == UUID(organization_id)).count() == first_notification_count

    preference = client.put(
        f"/api/v1/notifications/preferences?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"category": "task", "in_app_enabled": False},
    )
    assert preference.status_code == 200, preference.text
    assert preference.json()["in_app_enabled"] is False

    second_due = datetime.now(timezone.utc) + timedelta(hours=5)
    second_task = client.post(
        f"/api/v1/tasks?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"title": "Prepare follow-up documents", "assigned_to_user_id": owner["user"]["id"], "due_at": second_due.isoformat()},
    )
    assert second_task.status_code == 201, second_task.text
    # Assignment and due reminders both respect this user's task-category preference.
    count_after_create = db_session.query(Notification).filter(Notification.organization_id == UUID(organization_id)).count()
    assert count_after_create == first_notification_count
    run_after_opt_out = client.post(
        f"/api/v1/notifications/automation/run?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={},
    )
    assert run_after_opt_out.status_code == 200, run_after_opt_out.text
    assert run_after_opt_out.json()["generated"]["task_reminders"] == 0
    assert db_session.query(Notification).filter(Notification.organization_id == UUID(organization_id)).count() == first_notification_count
    assert db_session.query(Task).filter(Task.organization_id == UUID(organization_id)).count() == 2


def test_automation_reminds_approvers_after_24_hours_and_is_duplicate_safe(client: TestClient, db_session: Session) -> None:
    owner = register_account(client, email="pending-approval-owner@example.com", organization="Pending Approval Workspace")
    organization_id = owner["organizations"][0]["organization_id"]
    rule = client.put(
        f"/api/v1/approval-rules/task?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"is_enabled": True, "required_roles": ["operations_staff"], "minimum_amount": None, "allow_self_approval": False},
    )
    assert rule.status_code == 200, rule.text
    invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=csrf_headers(client),
        json={"email": "pending-approver@example.com", "role": "operations_staff"},
    )
    assert invitation.status_code == 201, invitation.text
    approver_client = TestClient(client.app)
    csrf = approver_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    accepted = approver_client.post(
        "/api/v1/auth/accept-invitation",
        headers={"X-CSRF-Token": csrf},
        json={"token": invitation.json()["invitation_token"], "full_name": "Pending Approver", "password": "pending-approver-password-123"},
    )
    assert accepted.status_code == 200, accepted.text

    submitted = client.post(
        f"/api/v1/approvals?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"business_action": "task", "related_entity_type": "custom", "related_entity_id": str(uuid4()), "title": "Review customs process"},
    )
    assert submitted.status_code == 201, submitted.text
    approval_id = submitted.json()["id"]
    approval = db_session.query(ApprovalRequest).filter_by(id=UUID(approval_id)).one()
    approval.submitted_at = datetime.now(timezone.utc) - timedelta(hours=25)
    db_session.commit()

    run_once = client.post(
        f"/api/v1/notifications/automation/run?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={},
    )
    assert run_once.status_code == 200, run_once.text
    assert run_once.json()["generated"]["pending_approval_reminders"] == 1
    reminder_inbox = approver_client.get(f"/api/v1/notifications?organization_id={organization_id}&category=approval")
    assert reminder_inbox.status_code == 200, reminder_inbox.text
    assert any(row["title"] == "Approval request is still pending" for row in reminder_inbox.json()["items"])

    run_twice = client.post(
        f"/api/v1/notifications/automation/run?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={},
    )
    assert run_twice.status_code == 200, run_twice.text
    assert run_twice.json()["generated"]["pending_approval_reminders"] == 0


def test_automation_warns_of_upcoming_import_shipment_arrival(client: TestClient) -> None:
    from tests.test_import_management import _approve, _order
    from tests.test_master_data_inventory import _create_basics

    owner = register_account(client, email="shipment-reminder-owner@example.com", organization="Shipment Reminder Workspace")
    organization_id = owner["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=organization_id)
    order = _order(client, organization_id, supplier, product)
    _approve(client, organization_id, order["id"])
    eta = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()
    shipment = client.post(
        f"/api/v1/imports/{order['id']}/shipments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"shipment_reference": "PH10-UPCOMING-ETA", "carrier": "Ocean Carrier", "transport_mode": "sea", "estimated_arrival": eta},
    )
    assert shipment.status_code == 201, shipment.text

    run_once = client.post(
        f"/api/v1/notifications/automation/run?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={},
    )
    assert run_once.status_code == 200, run_once.text
    assert run_once.json()["generated"]["shipment_alerts"] >= 1
    inbox = client.get(f"/api/v1/notifications?organization_id={organization_id}&category=shipment")
    assert inbox.status_code == 200, inbox.text
    assert any(row["title"] == "Shipment arrival approaching" for row in inbox.json()["items"])
