"""Phase 8 document versioning, verification, requirements, and shipment tracking tests."""
from datetime import datetime, timezone

from app.storage import LocalPrivateStorage
from tests.conftest import csrf_headers, register_account
from tests.test_export_management import _approve as approve_export, _create_export_order, _receive_stock
from tests.test_import_management import _approve as approve_import, _order as create_import_order
from tests.test_master_data_inventory import _create_basics


def _upload(client, organization_id, entity_type, entity_id, *, name="invoice.pdf", body=b"%PDF-1.7\nphase8 document", document_type="commercial_invoice"):
    return client.post(
        f"/api/v1/documents?organization_id={organization_id}",
        headers=csrf_headers(client),
        data={
            "related_entity_type": entity_type,
            "related_entity_id": entity_id,
            "document_type": document_type,
            "title": "Trade invoice",
            "description": "Uploaded for Phase 8 verification.",
        },
        files={"file": (name, body, "application/pdf")},
    )


def test_document_versioning_verification_and_explicit_compliance(client, monkeypatch, tmp_path):
    from app.api.routes import documents as documents_routes

    monkeypatch.setattr(documents_routes, "get_storage", lambda: LocalPrivateStorage(tmp_path))
    auth = register_account(client, email="phase8-docs@example.com", organization="Phase Eight Documents")
    organization_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=organization_id)
    order = create_import_order(client, organization_id, supplier, product)

    requirement = client.post(
        f"/api/v1/documents/requirements?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "related_entity_type": "import_order",
            "related_entity_id": order["id"],
            "document_type": "commercial_invoice",
            "label": "Supplier commercial invoice",
            "is_required": True,
        },
    )
    assert requirement.status_code == 201, requirement.text
    assert requirement.json()["label"] == "Supplier commercial invoice"

    compliance = client.get(
        f"/api/v1/documents/compliance?organization_id={organization_id}&related_entity_type=import_order&related_entity_id={order['id']}"
    )
    assert compliance.status_code == 200
    assert compliance.json()["is_compliant"] is False
    assert compliance.json()["missing_count"] == 1

    created = _upload(client, organization_id, "import_order", order["id"])
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["current_version"] == 1
    assert document["verification_status"] == "pending"
    assert document["versions"][0]["file_size"] > 0

    download = client.get(f"/api/v1/documents/{document['id']}/download?organization_id={organization_id}")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")
    assert "no-store" in download.headers["cache-control"]

    verified = client.patch(
        f"/api/v1/documents/{document['id']}/verification?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"verification_status": "verified", "verification_notes": "Invoice details checked."},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified_by_user_id"] is not None

    compliance = client.get(
        f"/api/v1/documents/compliance?organization_id={organization_id}&related_entity_type=import_order&related_entity_id={order['id']}"
    )
    assert compliance.json()["is_compliant"] is True

    version = client.post(
        f"/api/v1/documents/{document['id']}/versions?organization_id={organization_id}",
        headers=csrf_headers(client),
        files={"file": ("invoice-v2.pdf", b"%PDF-1.7\nnew version", "application/pdf")},
    )
    assert version.status_code == 200, version.text
    assert version.json()["current_version"] == 2
    assert version.json()["verification_status"] == "pending"
    assert len(version.json()["versions"]) == 2

    old_download = client.get(f"/api/v1/documents/{document['id']}/download?organization_id={organization_id}&version_number=1")
    assert old_download.status_code == 200
    assert old_download.content == b"%PDF-1.7\nphase8 document"

    history = client.get(f"/api/v1/documents/{document['id']}/verification-history?organization_id={organization_id}")
    assert history.status_code == 200
    assert any(event["to_status"] == "verified" for event in history.json())
    assert any(event["to_status"] == "pending" and event["version_number"] == 2 for event in history.json())

    compliance_after_new_version = client.get(
        f"/api/v1/documents/compliance?organization_id={organization_id}&related_entity_type=import_order&related_entity_id={order['id']}"
    )
    assert compliance_after_new_version.json()["is_compliant"] is False

    delete = client.delete(f"/api/v1/documents/{document['id']}?organization_id={organization_id}", headers=csrf_headers(client))
    assert delete.status_code == 204
    assert client.get(f"/api/v1/documents/{document['id']}/versions?organization_id={organization_id}").status_code == 404


def test_export_order_private_documents_and_organization_isolation(client, monkeypatch, tmp_path):
    from app.api.routes import documents as documents_routes

    monkeypatch.setattr(documents_routes, "get_storage", lambda: LocalPrivateStorage(tmp_path))
    auth = register_account(client, email="phase8-export-docs@example.com", organization="Phase Eight Export Docs")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, product, location = _create_basics(client, organization_id=organization_id)
    _receive_stock(client, organization_id, product, location)
    order = _create_export_order(client, organization_id, customer, product, location)
    approve_export(client, organization_id, order)
    shipment = client.post(
        f"/api/v1/exports/{order['id']}/shipments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "shipment_reference": "PH8-EXPORT-DOC-SHIP",
            "idempotency_key": "phase8-export-doc-shipment-key",
            "items": [{"order_item_id": order["items"][0]["id"], "quantity_dispatched": "1"}],
        },
    )
    assert shipment.status_code == 201, shipment.text

    uploaded = _upload(client, organization_id, "export_shipment", shipment.json()["id"], name="packing-list.pdf", document_type="packing_list")
    assert uploaded.status_code == 201, uploaded.text
    listed = client.get(f"/api/v1/documents?organization_id={organization_id}&related_entity_type=export_shipment&related_entity_id={shipment.json()['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    second = register_account(client, email="phase8-other-docs@example.com", organization="Phase Eight Other Org")
    other_org = second["organizations"][0]["organization_id"]
    leaked = client.get(f"/api/v1/documents/{uploaded.json()['id']}/versions?organization_id={other_org}")
    assert leaked.status_code == 404


def test_unified_shipments_timeline_status_updates_and_milestones(client):
    auth = register_account(client, email="phase8-shipments@example.com", organization="Phase Eight Shipment Timeline")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, supplier, product, location = _create_basics(client, organization_id=organization_id)

    import_order = create_import_order(client, organization_id, supplier, product)
    approve_import(client, organization_id, import_order["id"])
    import_shipment = client.post(
        f"/api/v1/imports/{import_order['id']}/shipments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"shipment_reference": "PH8-IMP-TIMELINE", "carrier": "Ocean Carrier", "transport_mode": "sea"},
    )
    assert import_shipment.status_code == 201, import_shipment.text

    _receive_stock(client, organization_id, product, location)
    export_order = _create_export_order(client, organization_id, customer, product, location, quantity="2")
    approve_export(client, organization_id, export_order)
    export_shipment = client.post(
        f"/api/v1/exports/{export_order['id']}/shipments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "shipment_reference": "PH8-EXP-TIMELINE",
            "idempotency_key": "phase8-export-timeline-shipment",
            "items": [{"order_item_id": export_order["items"][0]["id"], "quantity_dispatched": "1"}],
        },
    )
    assert export_shipment.status_code == 201, export_shipment.text

    timeline = client.get(f"/api/v1/shipments?organization_id={organization_id}")
    assert timeline.status_code == 200, timeline.text
    assert {row["shipment_type"] for row in timeline.json()} == {"import", "export"}

    # Both workflows seed their timeline with a system-recorded creation/dispatch event.
    import_timeline = client.get(
        f"/api/v1/shipments/import/{import_shipment.json()['id']}/milestones?organization_id={organization_id}"
    )
    export_timeline = client.get(
        f"/api/v1/shipments/export/{export_shipment.json()['id']}/milestones?organization_id={organization_id}"
    )
    assert import_timeline.status_code == 200
    assert any(row["name"] == "Shipment planned" for row in import_timeline.json())
    assert export_timeline.status_code == 200
    assert any(row["name"] == "Shipment dispatched" for row in export_timeline.json())

    export_id = export_shipment.json()["id"]
    mark_delayed = client.patch(
        f"/api/v1/shipments/export/{export_id}?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"status": "delayed", "delay_reason": "Port congestion"},
    )
    assert mark_delayed.status_code == 200, mark_delayed.text
    assert mark_delayed.json()["status"] == "delayed"
    assert mark_delayed.json()["delay_reason"] == "Port congestion"

    milestone = client.post(
        f"/api/v1/shipments/export/{export_id}/milestones?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"name": "Customs inspection", "description": "Manual update from operations", "occurred_at": datetime.now(timezone.utc).isoformat()},
    )
    assert milestone.status_code == 201, milestone.text
    milestones = client.get(f"/api/v1/shipments/export/{export_id}/milestones?organization_id={organization_id}")
    assert milestones.status_code == 200
    assert any(row["name"] == "Customs inspection" for row in milestones.json())
    assert any(row["name"] == "Status changed to delayed" for row in milestones.json())

    resume = client.patch(
        f"/api/v1/shipments/export/{export_id}?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"status": "in_transit"},
    )
    assert resume.status_code == 200, resume.text
    assert resume.json()["delay_reason"] is None

    manual_delivery = client.patch(
        f"/api/v1/shipments/export/{export_id}?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"status": "delivered"},
    )
    assert manual_delivery.status_code == 409

    filtered = client.get(f"/api/v1/shipments?organization_id={organization_id}&shipment_type=import")
    assert filtered.status_code == 200
    assert all(row["shipment_type"] == "import" for row in filtered.json())


def test_unified_shipment_api_prevents_cross_organization_access(client):
    auth = register_account(client, email="phase8-shipment-owner@example.com", organization="Phase Eight Shipment Private")
    org_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=org_id)
    order = create_import_order(client, org_id, supplier, product)
    approve_import(client, org_id, order["id"])
    shipment = client.post(
        f"/api/v1/imports/{order['id']}/shipments?organization_id={org_id}",
        headers=csrf_headers(client),
        json={"shipment_reference": "PH8-PRIVATE-SHIP", "transport_mode": "road"},
    )
    assert shipment.status_code == 201

    other = register_account(client, email="phase8-shipment-other@example.com", organization="Phase Eight Other Shipment Org")
    other_org = other["organizations"][0]["organization_id"]
    leak = client.get(f"/api/v1/shipments/import/{shipment.json()['id']}/milestones?organization_id={other_org}")
    assert leak.status_code == 404


def test_export_manager_can_update_shipment_timeline():
    from app.core.permissions import ROLE_PERMISSIONS

    assert "shipments.read" in ROLE_PERMISSIONS["export_manager"]
    assert "shipments.update" in ROLE_PERMISSIONS["export_manager"]
    assert "shipments.update" not in ROLE_PERMISSIONS["read_only"]
