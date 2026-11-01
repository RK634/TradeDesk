"""Phase 9 tests for invoices, payment allocation, currency conversion, and reversals."""
from tests.conftest import csrf_headers, register_account
from tests.test_master_data_inventory import _create_basics


def _create_customer_invoice(client, organization_id, customer, *, number="INV-C-001", currency="EUR", total_lines=None):
    lines = total_lines or [{"description": "Consulting service", "quantity": "2", "unit_price": "10.00", "tax_rate": "19"}]
    response = client.post(
        f"/api/v1/invoices?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "invoice_number": number,
            "invoice_type": "customer",
            "customer_id": customer["id"],
            "issue_date": "2026-10-01",
            "due_date": "2026-11-01",
            "currency": currency,
            "discount_amount": "0.00",
            "items": lines,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _issue_invoice(client, organization_id, invoice):
    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/issue?organization_id={organization_id}",
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _record_payment(client, organization_id, invoice, *, reference="PAY-001", idempotency="payment-idem-0001", amount="10.00", currency="EUR", rate=None, rate_date=None):
    allocation = {"invoice_id": invoice["id"], "allocated_payment_amount": amount}
    if rate is not None:
        allocation["exchange_rate"] = rate
    if rate_date is not None:
        allocation["exchange_rate_date"] = rate_date
    return client.post(
        f"/api/v1/payments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "payment_reference": reference,
            "payment_type": "incoming",
            "payment_date": "2026-10-15",
            "currency": currency,
            "amount": amount,
            "payment_method": "bank_transfer",
            "external_reference": "BANK-REF-100",
            "idempotency_key": idempotency,
            "allocations": [allocation],
        },
    )


def test_customer_invoice_tax_rounding_issue_and_partial_payment_idempotency(client):
    auth = register_account(client, email="finance-owner@example.com", organization="Finance Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)

    invoice = _create_customer_invoice(
        client, organization_id, customer,
        total_lines=[
            {"description": "Freight handling", "quantity": "2", "unit_price": "10.00", "tax_rate": "19"},
            {"description": "Documentation", "quantity": "1", "unit_price": "5.00", "tax_rate": "0"},
        ],
    )
    assert invoice["status"] == "draft"
    assert invoice["subtotal"] == "25.00"
    assert invoice["tax_amount"] == "3.80"
    assert invoice["total_amount"] == "28.80"
    assert invoice["outstanding_balance"] == "28.80"

    issued = _issue_invoice(client, organization_id, invoice)
    assert issued["status"] == "issued"

    payment_response = _record_payment(client, organization_id, issued, amount="10.00")
    assert payment_response.status_code == 201, payment_response.text
    payment = payment_response.json()
    assert payment["allocated_amount"] == "10.00"
    assert payment["unallocated_amount"] == "0.00"

    replay = _record_payment(client, organization_id, issued, amount="10.00")
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == payment["id"]

    current = client.get(f"/api/v1/invoices/{invoice['id']}?organization_id={organization_id}")
    assert current.status_code == 200, current.text
    assert current.json()["status"] == "partially_paid"
    assert current.json()["amount_paid"] == "10.00"
    assert current.json()["outstanding_balance"] == "18.80"

    conflict = _record_payment(client, organization_id, issued, amount="11.00")
    assert conflict.status_code == 409


def test_supplier_invoice_outgoing_payment_and_payment_reversal_audit(client):
    auth = register_account(client, email="finance-reversal@example.com", organization="Finance Reversal Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    _, supplier, _, _ = _create_basics(client, organization_id=organization_id)
    create = client.post(
        f"/api/v1/invoices?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "invoice_number": "SUP-INV-001", "invoice_type": "supplier", "supplier_id": supplier["id"],
            "issue_date": "2026-10-01", "due_date": "2026-10-31", "currency": "EUR",
            "items": [{"description": "Raw materials", "quantity": "3", "unit_price": "20", "tax_rate": "0"}],
        },
    )
    assert create.status_code == 201, create.text
    invoice = _issue_invoice(client, organization_id, create.json())
    payment = client.post(
        f"/api/v1/payments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "payment_reference": "PAY-OUT-001", "payment_type": "outgoing", "payment_date": "2026-10-15",
            "currency": "EUR", "amount": "60.00", "payment_method": "bank_transfer",
            "idempotency_key": "payment-outgoing-key-001",
            "allocations": [{"invoice_id": invoice["id"], "allocated_payment_amount": "60.00"}],
        },
    )
    assert payment.status_code == 201, payment.text
    assert client.get(f"/api/v1/invoices/{invoice['id']}?organization_id={organization_id}").json()["status"] == "paid"

    reverse = client.post(
        f"/api/v1/payments/{payment.json()['id']}/reverse?organization_id={organization_id}",
        headers=csrf_headers(client), json={"reason": "Bank transfer was duplicated by the bank."},
    )
    assert reverse.status_code == 200, reverse.text
    assert reverse.json()["status"] == "reversed"
    restored = client.get(f"/api/v1/invoices/{invoice['id']}?organization_id={organization_id}").json()
    assert restored["status"] == "issued"
    assert restored["amount_paid"] == "0.00"
    assert restored["outstanding_balance"] == "60.00"

    audit = client.get(f"/api/v1/payments/{payment.json()['id']}/audit?organization_id={organization_id}")
    assert audit.status_code == 200
    assert [event["action"] for event in audit.json()] == ["posted", "reversed"]
    second_reverse = client.post(
        f"/api/v1/payments/{payment.json()['id']}/reverse?organization_id={organization_id}",
        headers=csrf_headers(client), json={"reason": "Duplicate reversal request."},
    )
    assert second_reverse.status_code == 409


def test_currency_conversion_is_explicit_and_snapshot_is_preserved(client):
    auth = register_account(client, email="finance-fx@example.com", organization="FX Finance Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)
    invoice = _create_customer_invoice(
        client, organization_id, customer, number="INV-USD-001", currency="USD",
        total_lines=[{"description": "Equipment", "quantity": "1", "unit_price": "110", "tax_rate": "0"}],
    )
    issued = _issue_invoice(client, organization_id, invoice)
    missing_rate = _record_payment(client, organization_id, issued, reference="PAY-FX-MISSING", idempotency="payment-fx-missing-001", amount="50", currency="EUR")
    assert missing_rate.status_code == 422

    payment = _record_payment(client, organization_id, issued, reference="PAY-FX-001", idempotency="payment-fx-key-0001", amount="50", currency="EUR", rate="1.10000000", rate_date="2026-10-15")
    assert payment.status_code == 201, payment.text
    allocation = payment.json()["allocations"][0]
    assert allocation["allocated_payment_amount"] == "50.00"
    assert allocation["allocated_invoice_amount"] == "55.00"
    assert allocation["exchange_rate"] == "1.10000000"
    assert allocation["exchange_rate_date"] == "2026-10-15"
    current = client.get(f"/api/v1/invoices/{invoice['id']}?organization_id={organization_id}").json()
    assert current["outstanding_balance"] == "55.00"


def test_financial_overpayment_duplicate_invoice_number_and_cross_org_isolation(client):
    first = register_account(client, email="finance-first@example.com", organization="Finance First Org")
    org_a = first["organizations"][0]["organization_id"]
    customer_a, _, _, _ = _create_basics(client, organization_id=org_a)
    invoice = _issue_invoice(client, org_a, _create_customer_invoice(
        client, org_a, customer_a,
        total_lines=[{"description": "Service", "quantity": "1", "unit_price": "20", "tax_rate": "0"}],
    ))
    overpayment = _record_payment(client, org_a, invoice, reference="PAY-OVER-001", idempotency="payment-over-key-001", amount="21")
    assert overpayment.status_code == 409

    duplicate = client.post(
        f"/api/v1/invoices?organization_id={org_a}", headers=csrf_headers(client),
        json={"invoice_number": invoice["invoice_number"], "invoice_type": "customer", "customer_id": customer_a["id"],
              "issue_date": "2026-10-01", "due_date": "2026-11-01", "currency": "EUR",
              "items": [{"description": "Duplicate", "quantity": "1", "unit_price": "5"}]},
    )
    assert duplicate.status_code == 409

    second = register_account(client, email="finance-second@example.com", organization="Finance Second Org")
    org_b = second["organizations"][0]["organization_id"]
    hidden = client.get(f"/api/v1/invoices/{invoice['id']}?organization_id={org_b}")
    assert hidden.status_code == 404

    foreign_payment = client.post(
        f"/api/v1/payments?organization_id={org_b}", headers=csrf_headers(client),
        json={"payment_reference": "PAY-FOREIGN", "payment_type": "incoming", "payment_date": "2026-10-15", "currency": "EUR",
              "amount": "1", "payment_method": "cash", "idempotency_key": "payment-foreign-key-01",
              "allocations": [{"invoice_id": invoice["id"], "allocated_payment_amount": "1"}]},
    )
    assert foreign_payment.status_code == 404


def test_invoice_discount_and_due_date_validation(client):
    auth = register_account(client, email="finance-validation@example.com", organization="Finance Validation")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)
    over_discount = client.post(
        f"/api/v1/invoices?organization_id={organization_id}", headers=csrf_headers(client),
        json={"invoice_number": "INV-DISC-001", "invoice_type": "customer", "customer_id": customer["id"],
              "issue_date": "2026-10-10", "due_date": "2026-10-20", "currency": "EUR", "discount_amount": "101",
              "items": [{"description": "Service", "quantity": "1", "unit_price": "100", "tax_rate": "0"}]},
    )
    assert over_discount.status_code == 422
    invalid_due = client.post(
        f"/api/v1/invoices?organization_id={organization_id}", headers=csrf_headers(client),
        json={"invoice_number": "INV-DATE-001", "invoice_type": "customer", "customer_id": customer["id"],
              "issue_date": "2026-10-20", "due_date": "2026-10-10", "currency": "EUR",
              "items": [{"description": "Service", "quantity": "1", "unit_price": "100", "tax_rate": "0"}]},
    )
    assert invalid_due.status_code == 422


def test_unallocated_payment_balance_can_be_reconciled_to_another_invoice(client):
    auth = register_account(client, email="finance-reconcile@example.com", organization="Finance Reconcile Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)

    first_invoice = _issue_invoice(client, organization_id, _create_customer_invoice(
        client, organization_id, customer, number="INV-RECON-001",
        total_lines=[{"description": "First service", "quantity": "1", "unit_price": "20", "tax_rate": "0"}],
    ))
    second_invoice = _issue_invoice(client, organization_id, _create_customer_invoice(
        client, organization_id, customer, number="INV-RECON-002",
        total_lines=[{"description": "Second service", "quantity": "1", "unit_price": "20", "tax_rate": "0"}],
    ))

    created = client.post(
        f"/api/v1/payments?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "payment_reference": "PAY-RECON-001", "payment_type": "incoming", "payment_date": "2026-10-15",
            "currency": "EUR", "amount": "30.00", "payment_method": "bank_transfer",
            "idempotency_key": "payment-reconcile-key-001",
            "allocations": [{"invoice_id": first_invoice["id"], "allocated_payment_amount": "10.00"}],
        },
    )
    assert created.status_code == 201, created.text
    payment = created.json()
    assert payment["allocated_amount"] == "10.00"
    assert payment["unallocated_amount"] == "20.00"

    allocation_payload = {"invoice_id": second_invoice["id"], "allocated_payment_amount": "20.00"}
    reconciled = client.post(
        f"/api/v1/payments/{payment['id']}/allocations?organization_id={organization_id}",
        headers=csrf_headers(client), json=allocation_payload,
    )
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["allocated_amount"] == "30.00"
    assert reconciled.json()["unallocated_amount"] == "0.00"
    assert len(reconciled.json()["allocations"]) == 2

    replay = client.post(
        f"/api/v1/payments/{payment['id']}/allocations?organization_id={organization_id}",
        headers=csrf_headers(client), json=allocation_payload,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["allocated_amount"] == "30.00"
    changed = client.post(
        f"/api/v1/payments/{payment['id']}/allocations?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"invoice_id": second_invoice["id"], "allocated_payment_amount": "19.00"},
    )
    assert changed.status_code == 409

    first_current = client.get(f"/api/v1/invoices/{first_invoice['id']}?organization_id={organization_id}").json()
    second_current = client.get(f"/api/v1/invoices/{second_invoice['id']}?organization_id={organization_id}").json()
    assert first_current["amount_paid"] == "10.00"
    assert second_current["amount_paid"] == "20.00"
    assert second_current["status"] == "paid"

    audit = client.get(f"/api/v1/payments/{payment['id']}/audit?organization_id={organization_id}")
    assert audit.status_code == 200
    assert [event["action"] for event in audit.json()] == ["posted", "allocation_added"]


def test_dashboard_financial_exposure_is_grouped_by_currency_and_net_of_payments(client):
    auth = register_account(client, email="finance-dashboard@example.com", organization="Finance Dashboard Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)

    eur_invoice = _issue_invoice(client, organization_id, _create_customer_invoice(
        client, organization_id, customer, number="INV-DASH-EUR", currency="EUR",
        total_lines=[{"description": "EUR service", "quantity": "1", "unit_price": "100", "tax_rate": "0"}],
    ))
    usd_invoice = _issue_invoice(client, organization_id, _create_customer_invoice(
        client, organization_id, customer, number="INV-DASH-USD", currency="USD",
        total_lines=[{"description": "USD service", "quantity": "1", "unit_price": "200", "tax_rate": "0"}],
    ))
    eur_payment = _record_payment(
        client, organization_id, eur_invoice, reference="PAY-DASH-EUR", idempotency="payment-dashboard-eur-001", amount="25.00",
    )
    usd_payment = _record_payment(
        client, organization_id, usd_invoice, reference="PAY-DASH-USD", idempotency="payment-dashboard-usd-001", amount="50.00", currency="USD",
    )
    assert eur_payment.status_code == 201, eur_payment.text
    assert usd_payment.status_code == 201, usd_payment.text

    response = client.get(f"/api/v1/dashboard/summary?organization_id={organization_id}")
    assert response.status_code == 200, response.text
    metrics = {row["currency"]: row for row in response.json()["financial_metrics"]}
    assert metrics["EUR"]["customer_receivables"] == "75.00"
    assert metrics["EUR"]["open_invoice_count"] == 1
    assert metrics["USD"]["customer_receivables"] == "150.00"
    assert metrics["USD"]["open_invoice_count"] == 1


def test_draft_invoice_can_be_updated_then_issued_and_voided_with_a_reason(client):
    auth = register_account(client, email="finance-lifecycle@example.com", organization="Finance Lifecycle Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)
    draft = _create_customer_invoice(
        client, organization_id, customer, number="INV-LIFECYCLE-001",
        total_lines=[{"description": "Initial service", "quantity": "1", "unit_price": "50", "tax_rate": "0"}],
    )
    updated = client.patch(
        f"/api/v1/invoices/{draft['id']}?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={"notes": "Updated before issue", "items": [{"description": "Revised service", "quantity": "2", "unit_price": "40", "tax_rate": "0"}]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["total_amount"] == "80.00"
    assert updated.json()["notes"] == "Updated before issue"

    issued = _issue_invoice(client, organization_id, updated.json())
    blocked_edit = client.patch(
        f"/api/v1/invoices/{draft['id']}?organization_id={organization_id}",
        headers=csrf_headers(client), json={"notes": "Attempt to change an issued invoice"},
    )
    assert blocked_edit.status_code == 409

    voided = client.post(
        f"/api/v1/invoices/{draft['id']}/void?organization_id={organization_id}",
        headers=csrf_headers(client), json={"reason": "The customer cancelled before fulfillment."},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["status"] == "void"
    audit = client.get(f"/api/v1/invoices/{draft['id']}/audit?organization_id={organization_id}")
    assert audit.status_code == 200
    assert [event["action"] for event in audit.json()] == ["created_draft", "draft_updated", "issued", "voided"]



def test_dashboard_hides_financial_aggregates_from_roles_without_invoice_read(client, db_session):
    from uuid import UUID
    from app.models import OrganizationMembership

    auth = register_account(client, email="finance-visibility@example.com", organization="Finance Visibility Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, _, _ = _create_basics(client, organization_id=organization_id)
    _issue_invoice(client, organization_id, _create_customer_invoice(
        client, organization_id, customer, number="INV-HIDDEN-FINANCE",
        total_lines=[{"description": "Restricted service", "quantity": "1", "unit_price": "999", "tax_rate": "0"}],
    ))

    membership = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == UUID(organization_id),
    ).one()
    membership.role = "import_manager"
    db_session.commit()

    response = client.get(f"/api/v1/dashboard/summary?organization_id={organization_id}")
    assert response.status_code == 200, response.text
    assert response.json()["import_metrics"] is not None
    assert response.json()["financial_metrics"] is None


def test_finance_staff_has_partner_and_order_read_access_without_trade_mutation_permissions():
    from app.core.permissions import ROLE_PERMISSIONS

    finance_permissions = ROLE_PERMISSIONS["finance_staff"]
    assert {"customers.read", "suppliers.read", "imports.read", "exports.read"} <= finance_permissions
    assert {"invoices.read", "invoices.create", "payments.read", "payments.create"} <= finance_permissions
    assert "imports.approve" not in finance_permissions
    assert "exports.approve" not in finance_permissions
    assert "inventory.adjust" not in finance_permissions
