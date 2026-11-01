"""Phase 11 tests for reports, CSV exports, and retention-aware archive operations."""
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ImportOrder
from conftest import csrf_headers, register_account
from tests.test_master_data_inventory import _create_basics


def _receive_stock(client: TestClient, organization_id: str, product_id: str, location_id: str) -> None:
    response = client.post(
        "/api/v1/inventory/movements",
        headers=csrf_headers(client),
        json={
            "organization_id": organization_id,
            "product_id": product_id,
            "location_id": location_id,
            "movement_type": "goods_received",
            "quantity": "8",
            "idempotency_key": f"phase11-stock-{uuid4().hex[:16]}",
            "source_type": "test_receipt",
            "source_reference": "PHASE11-TEST",
        },
    )
    assert response.status_code == 200, response.text


def test_reports_summary_inventory_movements_and_csv_export(client: TestClient) -> None:
    auth = register_account(client, email="phase11-reports@example.com", organization="Phase 11 Reports")
    organization_id = auth["organizations"][0]["organization_id"]
    _, _, product, location = _create_basics(client, organization_id=organization_id)
    _receive_stock(client, organization_id, product["id"], location["id"])

    summary = client.get(f"/api/v1/reports/summary?organization_id={organization_id}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["inventory"] == {"balance_rows": 1, "low_stock_rows": 0}
    assert summary.json()["financial"] == []

    inventory = client.get(f"/api/v1/reports/inventory?organization_id={organization_id}")
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()[0]["available_quantity"] == "8.0000"
    movements = client.get(f"/api/v1/reports/inventory-movements?organization_id={organization_id}")
    assert movements.status_code == 200, movements.text
    assert movements.json()[0]["movement_type"] == "goods_received"

    exported = client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=inventory")
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers["content-type"]
    assert "inventory_stock.csv" in exported.headers["content-disposition"]
    assert "SKU-001" in exported.text


def test_financial_report_requires_finance_permission_and_keeps_currencies_separate(client: TestClient) -> None:
    auth = register_account(client, email="phase11-finance-report@example.com", organization="Phase 11 Finance")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)
    invoice = client.post(
        f"/api/v1/invoices?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "invoice_number": "PH11-INV-001", "invoice_type": "customer", "customer_id": customer["id"],
            "issue_date": "2026-10-01", "due_date": "2026-10-15", "currency": "EUR",
            "items": [{"description": "Trade service", "quantity": "1", "unit_price": "120.00", "tax_rate": "0"}],
        },
    )
    assert invoice.status_code == 201, invoice.text
    issued = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/issue?organization_id={organization_id}",
        headers=csrf_headers(client),
    )
    assert issued.status_code == 200, issued.text

    report = client.get(f"/api/v1/reports/financial?organization_id={organization_id}&start_date=2026-10-01&end_date=2026-10-31")
    assert report.status_code == 200, report.text
    assert len(report.json()["by_currency"]) == 1
    assert report.json()["by_currency"][0]["currency"] == "EUR"
    assert report.json()["by_currency"][0]["receivables_outstanding"] == "120.00"
    csv_response = client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=invoices&start_date=2026-10-01&end_date=2026-10-31")
    assert csv_response.status_code == 200, csv_response.text
    assert "PH11-INV-001" in csv_response.text


def test_archive_only_finalized_orders_and_restore_preserves_record_history(client: TestClient, db_session: Session) -> None:
    auth = register_account(client, email="phase11-archive@example.com", organization="Phase 11 Archive")
    organization_id = auth["organizations"][0]["organization_id"]
    _, supplier, _, _ = _create_basics(client, organization_id=organization_id)
    draft = client.post(
        f"/api/v1/imports?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"supplier_id": supplier["id"], "currency": "EUR", "items": []},
    )
    assert draft.status_code == 201, draft.text
    draft_id = UUID(draft.json()["id"])
    draft_record = db_session.get(ImportOrder, draft_id)
    assert draft_record is not None
    draft_record.status = "received"
    db_session.commit()

    archived = client.post(
        f"/api/v1/archive/import_order/{draft_id}?organization_id={organization_id}",
        headers=csrf_headers(client), json={"reason": "Completed and reconciled."},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"] is not None
    assert archived.json()["archive_reason"] == "Completed and reconciled."

    operational_list = client.get(f"/api/v1/imports?organization_id={organization_id}")
    assert operational_list.status_code == 200, operational_list.text
    assert operational_list.json()["total"] == 0
    archive_list = client.get(f"/api/v1/archive?organization_id={organization_id}")
    assert archive_list.status_code == 200, archive_list.text
    assert archive_list.json()["total"] == 1
    assert archive_list.json()["items"][0]["reference"] == draft.json()["reference"]

    history = client.get(f"/api/v1/archive/import_order/{draft_id}/history?organization_id={organization_id}")
    assert history.status_code == 200, history.text
    assert [row["action"] for row in history.json()] == ["archived"]

    restored = client.post(
        f"/api/v1/archive/import_order/{draft_id}/restore?organization_id={organization_id}",
        headers=csrf_headers(client), json={"reason": "Reopened for an authorized historical correction."},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["archived_at"] is None
    assert restored.json()["archive_reason"] is None
    assert client.get(f"/api/v1/imports?organization_id={organization_id}").json()["total"] == 1
    history = client.get(f"/api/v1/archive/import_order/{draft_id}/history?organization_id={organization_id}")
    assert [row["action"] for row in history.json()] == ["archived", "restored"]


def test_archive_rejects_nonterminal_orders_and_other_organization_access(client: TestClient) -> None:
    first = register_account(client, email="phase11-owner-a@example.com", organization="Phase 11 A")
    org_a = first["organizations"][0]["organization_id"]
    _, supplier, _, _ = _create_basics(client, organization_id=org_a)
    draft = client.post(
        f"/api/v1/imports?organization_id={org_a}", headers=csrf_headers(client),
        json={"supplier_id": supplier["id"], "currency": "EUR"},
    )
    assert draft.status_code == 201, draft.text
    denied_state = client.post(
        f"/api/v1/archive/import_order/{draft.json()['id']}?organization_id={org_a}",
        headers=csrf_headers(client), json={"reason": "Try to archive a draft order."},
    )
    assert denied_state.status_code == 409

    other_client = TestClient(client.app)
    second = register_account(other_client, email="phase11-owner-b@example.com", organization="Phase 11 B")
    org_b = second["organizations"][0]["organization_id"]
    forbidden_tenant = other_client.post(
        f"/api/v1/archive/import_order/{draft.json()['id']}?organization_id={org_b}",
        headers=csrf_headers(other_client), json={"reason": "Cross-organization attempt."},
    )
    assert forbidden_tenant.status_code == 404


def test_reports_and_archive_are_hidden_from_users_without_report_or_archive_read_permissions(client: TestClient) -> None:
    owner = register_account(client, email="phase11-owner-role@example.com", organization="Phase 11 Role")
    organization_id = owner["organizations"][0]["organization_id"]
    invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations", headers=csrf_headers(client),
        json={"email": "phase11-importer@example.com", "role": "import_manager"},
    )
    assert invitation.status_code == 201, invitation.text
    importer_client = TestClient(client.app)
    csrf = importer_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    accepted = importer_client.post(
        "/api/v1/auth/accept-invitation", headers={"X-CSRF-Token": csrf},
        json={"token": invitation.json()["invitation_token"], "full_name": "Import Manager", "password": "import-manager-password-123"},
    )
    assert accepted.status_code == 200, accepted.text
    assert importer_client.get(f"/api/v1/reports/summary?organization_id={organization_id}").status_code == 403
    assert importer_client.get(f"/api/v1/archive?organization_id={organization_id}").status_code == 403

    read_only_invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations", headers=csrf_headers(client),
        json={"email": "phase11-readonly@example.com", "role": "read_only"},
    )
    assert read_only_invitation.status_code == 201, read_only_invitation.text
    read_only_client = TestClient(client.app)
    readonly_csrf = read_only_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    readonly_accept = read_only_client.post(
        "/api/v1/auth/accept-invitation", headers={"X-CSRF-Token": readonly_csrf},
        json={"token": read_only_invitation.json()["invitation_token"], "full_name": "Read Only", "password": "read-only-password-123456"},
    )
    assert readonly_accept.status_code == 200, readonly_accept.text
    readonly_summary = read_only_client.get(f"/api/v1/reports/summary?organization_id={organization_id}")
    assert readonly_summary.status_code == 200, readonly_summary.text
    assert readonly_summary.json()["financial"] is None
    readonly_csv = read_only_client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=orders")
    assert readonly_csv.status_code == 403


def test_import_cost_partner_shipment_and_missing_document_reports(client, db_session: Session) -> None:
    from decimal import Decimal
    from tests.test_import_management import _approve as approve_import, _order as create_import_order

    auth = register_account(client, email="phase11-detail-reports@example.com", organization="Phase 11 Detail Reports")
    organization_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=organization_id)
    order = create_import_order(client, organization_id, supplier, product, quantity="2")
    order_model = db_session.get(ImportOrder, UUID(order["id"]))
    assert order_model is not None
    order_model.actual_freight_cost = Decimal("5.00")
    order_model.actual_insurance_cost = Decimal("2.00")
    order_model.actual_duties = Decimal("1.00")
    order_model.actual_other_costs = Decimal("0.00")
    db_session.commit()

    import_costs = client.get(f"/api/v1/reports/import-costs?organization_id={organization_id}")
    assert import_costs.status_code == 200, import_costs.text
    cost_row = next(row for row in import_costs.json() if row["record_id"] == order["id"])
    assert cost_row["estimated_goods_total"] == "10.50000000"
    assert cost_row["estimated_total"] == "36.50000000"
    assert cost_row["actual_costs"] == "8.00"
    assert cost_row["actual_total"] == "18.50000000"
    assert cost_row["variance"] == "-18.00000000"

    partner_report = client.get(f"/api/v1/reports/partners?organization_id={organization_id}")
    assert partner_report.status_code == 200, partner_report.text
    assert any(row["partner_name"] == "Acme Supplier" and row["currency"] == "EUR" for row in partner_report.json())
    from app.models import Supplier
    supplier_model = db_session.get(Supplier, UUID(supplier["id"]))
    assert supplier_model is not None
    supplier_model.name = "=1+1"
    db_session.commit()
    safe_csv = client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=partners")
    assert safe_csv.status_code == 200 and "'=1+1" in safe_csv.text
    supplier_model.name = "Acme Supplier"
    db_session.commit()

    approve_import(client, organization_id, order["id"])
    shipment = client.post(
        f"/api/v1/imports/{order['id']}/shipments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"shipment_reference": "PH11-REPORT-SHP", "carrier": "Ocean Carrier", "transport_mode": "sea", "estimated_arrival": "2026-10-29"},
    )
    assert shipment.status_code == 201, shipment.text
    shipment_id = shipment.json()["id"]
    requirement = client.post(
        f"/api/v1/documents/requirements?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"related_entity_type": "import_shipment", "related_entity_id": shipment_id, "document_type": "packing_list", "label": "Shipment packing list", "is_required": True},
    )
    assert requirement.status_code == 201, requirement.text

    shipment_report = client.get(f"/api/v1/reports/shipment-performance?organization_id={organization_id}")
    assert shipment_report.status_code == 200, shipment_report.text
    shipment_row = next(row for row in shipment_report.json() if row["shipment_id"] == shipment_id)
    assert shipment_row["days_late"] == 1
    assert shipment_row["partner_name"] == "Acme Supplier"

    missing = client.get(f"/api/v1/reports/missing-documents?organization_id={organization_id}")
    assert missing.status_code == 200, missing.text
    assert any(row["related_entity_type"] == "import_shipment" and row["label"] == "Shipment packing list" for row in missing.json())

    csv_partners = client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=partners")
    assert csv_partners.status_code == 200 and "Acme Supplier" in csv_partners.text
    csv_costs = client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=import_costs")
    assert csv_costs.status_code == 200 and cost_row["reference"] in csv_costs.text
    csv_shipment = client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=shipment_performance")
    assert csv_shipment.status_code == 200 and "PH11-REPORT-SHP" in csv_shipment.text
    csv_missing = client.get(f"/api/v1/reports/csv?organization_id={organization_id}&report_type=missing_documents")
    assert csv_missing.status_code == 200 and "Shipment packing list" in csv_missing.text


def test_archived_orders_are_excluded_from_operational_reminder_context(client, db_session: Session) -> None:
    from datetime import datetime, timezone
    from app.services.automation import _related_trade_record_is_active
    from tests.test_import_management import _order as create_import_order

    auth = register_account(client, email="phase11-archive-reminders@example.com", organization="Phase 11 Reminder Retention")
    organization_id = auth["organizations"][0]["organization_id"]
    _, supplier, product, _ = _create_basics(client, organization_id=organization_id)
    order = create_import_order(client, organization_id, supplier, product)
    order_model = db_session.get(ImportOrder, UUID(order["id"]))
    assert order_model is not None
    assert _related_trade_record_is_active(db_session, UUID(organization_id), "import_order", UUID(order["id"])) is True
    order_model.archived_at = datetime.now(timezone.utc)
    db_session.commit()
    assert _related_trade_record_is_active(db_session, UUID(organization_id), "import_order", UUID(order["id"])) is False
