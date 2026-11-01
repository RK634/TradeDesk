"""Phase 6 import workflow, shipment, document, and inventory integration tests."""

from types import SimpleNamespace
from uuid import UUID

from app.models import OrganizationMembership
from tests.conftest import csrf_headers, register_account
from tests.test_master_data_inventory import _create_basics


def _order(client, organization_id, supplier, product, *, quantity="10"):
    response = client.post(
        f"/api/v1/imports?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "supplier_id": supplier["id"],
            "currency": "EUR",
            "estimated_freight_cost": "20.00",
            "estimated_insurance_cost": "4.00",
            "estimated_duties": "2.00",
            "items": [{"product_id": product["id"], "quantity_ordered": quantity, "unit_price": "5.2500"}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve(client, organization_id, order_id):
    submit = client.post(
        f"/api/v1/imports/{order_id}/submit?organization_id={organization_id}",
        headers=csrf_headers(client),
    )
    assert submit.status_code == 200, submit.text
    approve = client.post(
        f"/api/v1/imports/{order_id}/approve?organization_id={organization_id}",
        headers=csrf_headers(client),
    )
    assert approve.status_code == 200, approve.text
    return approve.json()


def test_import_order_approval_partial_receipts_and_inventory_idempotency(client):
    auth = register_account(client, email="import-flow-owner@example.com", organization="Import Flow Trade")
    org_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, location = _create_basics(client, organization_id=org_id)

    empty_order = _order(client, org_id, supplier, product, quantity="1")
    # Remove the only line then confirm that an empty order cannot be submitted.
    line_id = empty_order["items"][0]["id"]
    deleted = client.delete(
        f"/api/v1/imports/{empty_order['id']}/items/{line_id}?organization_id={org_id}",
        headers=csrf_headers(client),
    )
    assert deleted.status_code == 204
    empty_submit = client.post(
        f"/api/v1/imports/{empty_order['id']}/submit?organization_id={org_id}",
        headers=csrf_headers(client),
    )
    assert empty_submit.status_code == 409

    order = _order(client, org_id, supplier, product)
    assert order["status"] == "draft"
    assert order["estimated_goods_total"] == "52.50000000"
    assert order["estimated_total_cost"] == "78.50000000"
    approved = _approve(client, org_id, order["id"])
    assert approved["status"] == "approved"

    receipt_payload = {
        "location_id": location["id"],
        "receipt_reference": "GRN-001",
        "idempotency_key": "import-receipt-001",
        "items": [{"order_item_id": order["items"][0]["id"], "quantity_received": "4"}],
    }
    partial = client.post(
        f"/api/v1/imports/{order['id']}/receipts?organization_id={org_id}",
        headers=csrf_headers(client), json=receipt_payload,
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["items"][0]["quantity_received"] == "4.0000"
    assert client.get(f"/api/v1/imports/{order['id']}?organization_id={org_id}").json()["status"] == "partially_received"

    replay = client.post(
        f"/api/v1/imports/{order['id']}/receipts?organization_id={org_id}",
        headers=csrf_headers(client), json=receipt_payload,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == partial.json()["id"]

    balances = client.get(f"/api/v1/inventory/balances?organization_id={org_id}&product_id={product['id']}")
    assert balances.status_code == 200, balances.text
    assert balances.json()["items"][0]["quantity_on_hand"] == "4.0000"

    over_receipt = client.post(
        f"/api/v1/imports/{order['id']}/receipts?organization_id={org_id}",
        headers=csrf_headers(client),
        json={**receipt_payload, "receipt_reference": "GRN-OVER", "idempotency_key": "import-receipt-over", "items": [{"order_item_id": order["items"][0]["id"], "quantity_received": "7"}]},
    )
    assert over_receipt.status_code == 409

    final_payload = {
        "location_id": location["id"],
        "receipt_reference": "GRN-002",
        "idempotency_key": "import-receipt-002",
        "items": [{"order_item_id": order["items"][0]["id"], "quantity_received": "6"}],
    }
    final_receipt = client.post(
        f"/api/v1/imports/{order['id']}/receipts?organization_id={org_id}",
        headers=csrf_headers(client), json=final_payload,
    )
    assert final_receipt.status_code == 200, final_receipt.text
    details = client.get(f"/api/v1/imports/{order['id']}?organization_id={org_id}").json()
    assert details["status"] == "received"
    assert details["items"][0]["quantity_received"] == "10.0000"
    balances = client.get(f"/api/v1/inventory/balances?organization_id={org_id}&product_id={product['id']}")
    assert balances.json()["items"][0]["quantity_on_hand"] == "10.0000"
    movements = client.get(f"/api/v1/inventory/movements?organization_id={org_id}&product_id={product['id']}")
    assert movements.json()["total"] == 2


def test_import_shipment_milestones_and_actual_dates(client):
    auth = register_account(client, email="import-shipment-owner@example.com", organization="Shipment Trade")
    org_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=org_id)
    order = _order(client, org_id, supplier, product)
    _approve(client, org_id, order["id"])

    shipment_response = client.post(
        f"/api/v1/imports/{order['id']}/shipments?organization_id={org_id}",
        headers=csrf_headers(client),
        json={"shipment_reference": "SHP-001", "carrier": "Ocean Carrier", "transport_mode": "sea", "estimated_departure": "2026-10-20", "estimated_arrival": "2026-11-01"},
    )
    assert shipment_response.status_code == 201, shipment_response.text
    shipment = shipment_response.json()
    update = client.patch(
        f"/api/v1/imports/shipments/{shipment['id']}?organization_id={org_id}",
        headers=csrf_headers(client),
        json={"status": "in_transit", "actual_departure": "2026-10-21"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["status"] == "in_transit"
    assert client.get(f"/api/v1/imports/{order['id']}?organization_id={org_id}").json()["actual_departure_date"] == "2026-10-21"

    milestone = client.post(
        f"/api/v1/imports/shipments/{shipment['id']}/milestones?organization_id={org_id}",
        headers=csrf_headers(client),
        json={"name": "Departed port", "description": "Loaded and departed", "occurred_at": "2026-10-21T12:00:00Z"},
    )
    assert milestone.status_code == 201, milestone.text
    rows = client.get(f"/api/v1/imports/shipments/{shipment['id']}/milestones?organization_id={org_id}")
    assert rows.status_code == 200
    assert rows.json()[0]["name"] == "Departed port"

    invalid_transition = client.patch(
        f"/api/v1/imports/shipments/{shipment['id']}?organization_id={org_id}",
        headers=csrf_headers(client), json={"status": "planned"},
    )
    assert invalid_transition.status_code == 409


def test_import_documents_are_private_verified_and_deleted(client, monkeypatch, tmp_path):
    from app.api.routes import imports as imports_routes

    auth = register_account(client, email="import-doc-owner@example.com", organization="Document Trade")
    org_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=org_id)
    order = _order(client, org_id, supplier, product)
    monkeypatch.setattr(imports_routes, "get_settings", lambda: SimpleNamespace(private_storage_dir=str(tmp_path), max_upload_bytes=1024 * 1024))

    upload = client.post(
        f"/api/v1/imports/{order['id']}/documents?organization_id={org_id}",
        headers=csrf_headers(client),
        data={"document_type": "commercial_invoice"},
        files={"file": ("commercial-invoice.pdf", b"%PDF-1.7\nphase6 test document", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    assert document["verification_status"] == "pending"

    download = client.get(f"/api/v1/imports/{order['id']}/documents/{document['id']}/download?organization_id={org_id}")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")

    verified = client.patch(
        f"/api/v1/imports/{order['id']}/documents/{document['id']}?organization_id={org_id}",
        headers=csrf_headers(client), json={"verification_status": "verified", "verification_notes": "Checked by finance"},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verification_status"] == "verified"
    assert verified.json()["verified_by_user_id"] is not None

    deleted = client.delete(
        f"/api/v1/imports/{order['id']}/documents/{document['id']}?organization_id={org_id}",
        headers=csrf_headers(client),
    )
    assert deleted.status_code == 204
    not_found = client.get(f"/api/v1/imports/{order['id']}/documents/{document['id']}/download?organization_id={org_id}")
    assert not_found.status_code == 404


def test_import_order_and_document_access_is_scoped_to_organization(client):
    auth = register_account(client, email="import-private-owner@example.com", organization="Private Import Trade")
    original_org = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=original_org)
    order = _order(client, original_org, supplier, product)

    second_auth = register_account(client, email="other-import-owner@example.com", organization="Other Import Trade")
    second_org = second_auth["organizations"][0]["organization_id"]
    assert second_org != original_org
    forbidden_order = client.get(f"/api/v1/imports/{order['id']}?organization_id={original_org}")
    assert forbidden_order.status_code == 404
    empty_list = client.get(f"/api/v1/imports?organization_id={second_org}")
    assert empty_list.status_code == 200
    assert empty_list.json()["total"] == 0


def test_import_manager_cannot_approve_submitted_order(client, db_session):
    auth = register_account(client, email="import-approval-owner@example.com", organization="Import Approval Trade")
    org_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=org_id)
    order = _order(client, org_id, supplier, product)
    submitted = client.post(
        f"/api/v1/imports/{order['id']}/submit?organization_id={org_id}",
        headers=csrf_headers(client),
    )
    assert submitted.status_code == 200, submitted.text

    membership = db_session.query(OrganizationMembership).filter_by(organization_id=UUID(org_id)).one()
    membership.role = "import_manager"
    db_session.commit()
    response = client.post(
        f"/api/v1/imports/{order['id']}/approve?organization_id={org_id}",
        headers=csrf_headers(client),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to perform this action."
