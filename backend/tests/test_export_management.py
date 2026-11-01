"""Phase 7 export workflow integration tests."""
from uuid import uuid4

from tests.conftest import csrf_headers, register_account
from tests.test_master_data_inventory import _create_basics


def _create_export_order(client, organization_id, customer, product, location, *, quantity="8"):
    response = client.post(
        f"/api/v1/exports?organization_id={organization_id}",
        headers=csrf_headers(client),
        json={
            "customer_id": customer["id"],
            "inventory_location_id": location["id"],
            "currency": "eur",
            "destination_country": "de",
            "delivery_address": "Buyer receiving dock, Berlin",
            "shipping_terms": "DAP",
            "payment_terms_days": 30,
            "items": [{"product_id": product["id"], "quantity_ordered": quantity, "unit_price": "12.5000"}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _receive_stock(client, organization_id, product, location, quantity="10"):
    response = client.post(
        "/api/v1/inventory/movements",
        headers=csrf_headers(client),
        json={"organization_id": organization_id, "product_id": product["id"], "location_id": location["id"],
              "movement_type": "goods_received", "quantity": quantity, "idempotency_key": "phase7-stock-receipt-01",
              "source_type": "manual_receipt", "source_reference": "GRN-PHASE7"},
    )
    assert response.status_code in (200, 201), response.text


def _approve(client, organization_id, order):
    submit = client.post(f"/api/v1/exports/{order['id']}/submit?organization_id={organization_id}", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text
    approve = client.post(f"/api/v1/exports/{order['id']}/approve?organization_id={organization_id}", headers=csrf_headers(client))
    assert approve.status_code == 200, approve.text
    return approve.json()


def test_export_order_reservation_partial_dispatch_delivery_and_idempotency(client):
    auth = register_account(client, email="export-owner@example.com", organization="Export Workflow Trade")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, product, location = _create_basics(client, organization_id=organization_id)
    _receive_stock(client, organization_id, product, location)

    order = _create_export_order(client, organization_id, customer, product, location)
    assert order["status"] == "draft"
    assert order["goods_total"] == "100.00000000"
    approved = _approve(client, organization_id, order)
    assert approved["status"] == "approved"
    balances = client.get(f"/api/v1/inventory/balances?organization_id={organization_id}&product_id={product['id']}").json()
    assert balances["items"][0]["quantity_on_hand"] == "10.0000"
    assert balances["items"][0]["reserved_quantity"] == "8.0000"

    item_id = order["items"][0]["id"]
    shipment_payload = {
        "shipment_reference": "EXP-SHP-001", "idempotency_key": "export-shipment-key-001", "carrier": "Road Cargo",
        "transport_mode": "road", "destination": "Berlin", "items": [{"order_item_id": item_id, "quantity_dispatched": "5"}],
    }
    shipment_response = client.post(f"/api/v1/exports/{order['id']}/shipments?organization_id={organization_id}", headers=csrf_headers(client), json=shipment_payload)
    assert shipment_response.status_code == 201, shipment_response.text
    shipment = shipment_response.json()
    assert shipment["items"][0]["quantity_dispatched"] == "5.0000"

    replay = client.post(f"/api/v1/exports/{order['id']}/shipments?organization_id={organization_id}", headers=csrf_headers(client), json=shipment_payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == shipment["id"]
    balances = client.get(f"/api/v1/inventory/balances?organization_id={organization_id}&product_id={product['id']}").json()
    assert balances["items"][0]["quantity_on_hand"] == "5.0000"
    assert balances["items"][0]["reserved_quantity"] == "3.0000"

    delivery_payload = {"delivery_reference": "EXP-DEL-001", "idempotency_key": "export-delivery-key-001",
                        "items": [{"shipment_item_id": shipment["items"][0]["id"], "quantity_delivered": "2"}]}
    delivery_response = client.post(f"/api/v1/exports/{order['id']}/shipments/{shipment['id']}/deliveries?organization_id={organization_id}", headers=csrf_headers(client), json=delivery_payload)
    assert delivery_response.status_code == 201, delivery_response.text
    delivery_replay = client.post(f"/api/v1/exports/{order['id']}/shipments/{shipment['id']}/deliveries?organization_id={organization_id}", headers=csrf_headers(client), json=delivery_payload)
    assert delivery_replay.status_code == 200, delivery_replay.text
    assert delivery_replay.json()["id"] == delivery_response.json()["id"]

    over_delivery = client.post(f"/api/v1/exports/{order['id']}/shipments/{shipment['id']}/deliveries?organization_id={organization_id}", headers=csrf_headers(client), json={
        "delivery_reference": "EXP-DEL-OVER", "idempotency_key": "export-delivery-key-over", "items": [{"shipment_item_id": shipment["items"][0]["id"], "quantity_delivered": "4"}],
    })
    assert over_delivery.status_code == 409

    last_delivery = client.post(f"/api/v1/exports/{order['id']}/shipments/{shipment['id']}/deliveries?organization_id={organization_id}", headers=csrf_headers(client), json={
        "delivery_reference": "EXP-DEL-002", "idempotency_key": "export-delivery-key-002", "items": [{"shipment_item_id": shipment["items"][0]["id"], "quantity_delivered": "3"}],
    })
    assert last_delivery.status_code == 201, last_delivery.text
    current = client.get(f"/api/v1/exports/{order['id']}?organization_id={organization_id}").json()
    assert current["status"] == "partially_delivered"

    second_shipment_payload = {"shipment_reference": "EXP-SHP-002", "idempotency_key": "export-shipment-key-002",
                               "items": [{"order_item_id": item_id, "quantity_dispatched": "3"}]}
    second_shipment = client.post(f"/api/v1/exports/{order['id']}/shipments?organization_id={organization_id}", headers=csrf_headers(client), json=second_shipment_payload)
    assert second_shipment.status_code == 201, second_shipment.text
    final_delivery = client.post(f"/api/v1/exports/{order['id']}/shipments/{second_shipment.json()['id']}/deliveries?organization_id={organization_id}", headers=csrf_headers(client), json={
        "delivery_reference": "EXP-DEL-003", "idempotency_key": "export-delivery-key-003",
        "items": [{"shipment_item_id": second_shipment.json()["items"][0]["id"], "quantity_delivered": "3"}],
    })
    assert final_delivery.status_code == 201, final_delivery.text
    current = client.get(f"/api/v1/exports/{order['id']}?organization_id={organization_id}").json()
    assert current["status"] == "delivered"
    assert current["quantity_delivered"] == "8.0000"
    balances = client.get(f"/api/v1/inventory/balances?organization_id={organization_id}&product_id={product['id']}").json()
    assert balances["items"][0]["quantity_on_hand"] == "2.0000"
    assert balances["items"][0]["reserved_quantity"] == "0.0000"


def test_export_approval_rejects_insufficient_stock_and_org_leakage(client):
    auth = register_account(client, email="export-low-stock@example.com", organization="Export Low Stock")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, product, location = _create_basics(client, organization_id=organization_id)
    order = _create_export_order(client, organization_id, customer, product, location, quantity="1")
    submitted = client.post(f"/api/v1/exports/{order['id']}/submit?organization_id={organization_id}", headers=csrf_headers(client))
    assert submitted.status_code == 200, submitted.text
    approve = client.post(f"/api/v1/exports/{order['id']}/approve?organization_id={organization_id}", headers=csrf_headers(client))
    assert approve.status_code == 409

    other = register_account(client, email="export-other-org@example.com", organization="Another Export Org")
    other_org_id = other["organizations"][0]["organization_id"]
    leaked = client.get(f"/api/v1/exports/{order['id']}?organization_id={other_org_id}")
    assert leaked.status_code == 404


def test_export_idempotency_key_cannot_be_reused_with_different_payload(client):
    auth = register_account(client, email="export-idempotency@example.com", organization="Export Idempotency")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, product, location = _create_basics(client, organization_id=organization_id)
    _receive_stock(client, organization_id, product, location, quantity="10")
    order = _create_export_order(client, organization_id, customer, product, location)
    _approve(client, organization_id, order)
    item_id = order["items"][0]["id"]
    first = {"shipment_reference": "EXP-SHP-IDEM-1", "idempotency_key": "export-idem-key-001", "items": [{"order_item_id": item_id, "quantity_dispatched": "2"}]}
    response = client.post(f"/api/v1/exports/{order['id']}/shipments?organization_id={organization_id}", headers=csrf_headers(client), json=first)
    assert response.status_code == 201, response.text
    conflict = client.post(f"/api/v1/exports/{order['id']}/shipments?organization_id={organization_id}", headers=csrf_headers(client), json={**first, "items": [{"order_item_id": item_id, "quantity_dispatched": "3"}]})
    assert conflict.status_code == 409


def test_cancelling_approved_export_releases_reservation(client):
    auth = register_account(client, email="export-cancel@example.com", organization="Export Cancellation")
    organization_id = auth["organizations"][0]["organization_id"]
    customer, _, product, location = _create_basics(client, organization_id=organization_id)
    _receive_stock(client, organization_id, product, location, quantity="10")
    order = _create_export_order(client, organization_id, customer, product, location, quantity="4")
    _approve(client, organization_id, order)

    reserved = client.get(f"/api/v1/inventory/balances?organization_id={organization_id}&product_id={product['id']}").json()
    assert reserved["items"][0]["reserved_quantity"] == "4.0000"

    cancelled = client.post(f"/api/v1/exports/{order['id']}/cancel?organization_id={organization_id}", headers=csrf_headers(client))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    balances = client.get(f"/api/v1/inventory/balances?organization_id={organization_id}&product_id={product['id']}").json()
    assert balances["items"][0]["quantity_on_hand"] == "10.0000"
    assert balances["items"][0]["reserved_quantity"] == "0.0000"
