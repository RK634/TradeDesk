"""Dashboard tests prove that counts are organization-scoped and database-derived."""

from datetime import date
from uuid import uuid4


def test_dashboard_summary_uses_real_membership_data(client):
    from tests.conftest import register_account

    auth = register_account(client, email="dashboard-owner@example.com", organization="Dashboard Trade")
    organization_id = auth["organizations"][0]["organization_id"]

    response = client.get(f"/api/v1/dashboard/summary?organization_id={organization_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["organization_id"] == organization_id
    assert payload["organization_name"] == "Dashboard Trade"
    assert payload["workspace"]["total_members"] == 1
    assert payload["workspace"]["active_members"] == 1
    assert payload["workspace"]["inactive_members"] == 0
    assert payload["workspace"]["new_members"] == 1
    assert payload["workspace"]["pending_invitations"] == 0
    assert sum(item["count"] for item in payload["member_join_trend"]) == 1
    assert payload["members_by_role"] == [
        {"role": "organization_owner", "label": "Organization owner", "count": 1}
    ]
    # Phase 5 master data/inventory and Phase 6 import operations are available.
    modules = {item["key"]: item for item in payload["operational_modules"]}
    assert modules["inventory"]["available"] is True
    assert modules["imports"]["available"] is True
    assert modules["shipments"]["available"] is True
    assert modules["documents"]["available"] is True
    assert modules["exports"]["available"] is True
    assert modules["invoices_payments"]["available"] is True
    assert payload["financial_metrics"] == []
    assert payload["export_metrics"] == {"active_orders": 0, "awaiting_approval": 0, "partially_dispatched": 0, "dispatched": 0, "partially_delivered": 0, "delivered": 0, "delayed_shipments": 0}
    assert payload["import_metrics"] == {
        "active_orders": 0,
        "awaiting_approval": 0,
        "partially_received": 0,
        "received": 0,
        "delayed_shipments": 0,
    }


def test_dashboard_does_not_allow_cross_organization_access(client):
    from tests.conftest import register_account

    register_account(client, email="another-owner@example.com", organization="Another Trade")
    private_organization_id = str(uuid4())
    response = client.get(f"/api/v1/dashboard/summary?organization_id={private_organization_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found."


def test_dashboard_requires_a_session(client):
    response = client.get(f"/api/v1/dashboard/summary?organization_id={uuid4()}")
    assert response.status_code == 401


def test_dashboard_rejects_invalid_date_range(client):
    from tests.conftest import register_account

    auth = register_account(client, email="date-owner@example.com", organization="Date Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    response = client.get(
        f"/api/v1/dashboard/summary?organization_id={organization_id}"
        "&start_date=2026-10-20&end_date=2026-10-01"
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "start_date must be on or before end_date."


def test_dashboard_rejects_ranges_longer_than_one_year(client):
    from tests.conftest import register_account

    auth = register_account(client, email="long-range-owner@example.com", organization="Date Range Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    response = client.get(
        f"/api/v1/dashboard/summary?organization_id={organization_id}"
        "&start_date=2024-01-01&end_date=2026-10-01"
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Date range cannot exceed 366 days."
