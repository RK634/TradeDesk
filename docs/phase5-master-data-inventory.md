# Phase 5 — Master Data and Basic Inventory Ledger

## Scope delivered

Phase 5 builds on the Phase 1–4 project and implements organization-scoped master data and an initial inventory ledger:

- Customers: contact details, billing/delivery address, country, tax ID, payment terms, preferred currency, notes, active status.
- Suppliers: contact details, address, country, tax ID, payment terms, preferred currency, notes, active status.
- Products: organization-unique SKU, name, category, unit of measure, purchase/selling price, currency, reorder threshold, active status.
- Inventory locations: organization-unique location code, name, address/description, active status.
- Inventory balances: one balance per organization/product/location pair, with on-hand and reserved quantity.
- Inventory movements: append-only movement records for receipts, dispatches, reservations, reservation releases, increases/decreases, and returns.

The React workspace now contains active Customers, Suppliers, Products, Inventory Locations, and Inventory pages. Customer/supplier/product/location interfaces have search, status filters, create, edit, and deactivate/reactivate operations. The inventory page displays stock balances, low-stock state, a stock movement form, and recent ledger entries.

## API contract

All routes are under `/api/v1`. All record operations require an authenticated session and an authorized active organization membership.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/customers?organization_id=...` | Search/paginate customers |
| POST | `/customers?organization_id=...` | Create a customer |
| GET | `/customers/{id}?organization_id=...` | Get one customer in the organization |
| PATCH | `/customers/{id}?organization_id=...` | Update a customer / active status |
| GET | `/suppliers?organization_id=...` | Search/paginate suppliers |
| POST | `/suppliers?organization_id=...` | Create a supplier |
| GET | `/suppliers/{id}?organization_id=...` | Get one supplier in the organization |
| PATCH | `/suppliers/{id}?organization_id=...` | Update a supplier / active status |
| GET | `/products?organization_id=...` | Search/paginate products |
| POST | `/products?organization_id=...` | Create a product |
| GET | `/products/{id}?organization_id=...` | Get one product in the organization |
| PATCH | `/products/{id}?organization_id=...` | Update a product / active status |
| GET | `/inventory/locations?organization_id=...` | Search/paginate locations |
| POST | `/inventory/locations?organization_id=...` | Create a location |
| GET | `/inventory/locations/{id}?organization_id=...` | Get one location |
| PATCH | `/inventory/locations/{id}?organization_id=...` | Update a location / active status |
| GET | `/inventory/balances?organization_id=...` | Paginated stock balances; optional product, location, search, and low-stock filters |
| GET | `/inventory/movements?organization_id=...` | Paginated ledger with product/location/type filters |
| POST | `/inventory/movements` | Atomically post an inventory movement; organization ID is in the request body |

Read endpoints support `page` (default 1), `page_size` (default 20, maximum 100), and relevant search/status filters. Responses use `{ items, total, page, page_size }` for collection endpoints.

## Inventory rules

- Quantities use `Decimal` in Python and `NUMERIC(18,4)` in PostgreSQL.
- Product and location references are checked against the request organization in the service layer. Composite foreign keys additionally prevent cross-organization references for inventory balances and movements.
- On PostgreSQL, the product row is locked with `SELECT ... FOR UPDATE` before stock calculations. This serializes concurrent stock operations on the same product and protects initialization of a first product/location balance.
- The balance update and append-only movement insert run in one database transaction.
- Receipt and return movements increase on-hand quantity; dispatches decrease on-hand quantity; reservations affect reserved quantity only; reservation release reduces reserved quantity; adjustments change on-hand quantity.
- Dispatch cannot consume reserved stock; reservations cannot exceed available stock; reservation release cannot release more than currently reserved; stock cannot become negative or be adjusted below the reserved quantity.
- Each movement requires an organization-scoped idempotency key (minimum eight non-space characters). A matching retry returns the original movement without reposting stock; reusing the key with a different payload returns HTTP 409.
- Rejected stock operations do not create an empty balance row.
- The ledger records actor, source type/reference when provided, notes, signed quantity changes, resulting on-hand quantity, and resulting reserved quantity.
- There are no hard-delete endpoints for customers, suppliers, products, or locations. Use active/inactive state so future orders and ledger history can retain their references.

## Authorization

The API uses the central Phase 3 role-to-permission map. Each read/write endpoint requires its specific permission and an active membership in the requested organization. Mutations verify the CSRF token and same-origin policy as configured by the auth layer. UI hiding is not treated as the security boundary.

- Organization Owner / Administrator: full master-data maintenance and stock controls.
- Operations Staff: inventory read, goods received/dispatch movement permissions, and task/shipments permissions already in the central role map.
- Import/Export Managers and Finance Staff: only permissions explicitly granted in the existing central map; unsupported writes return `403`.
- Read-Only User: read permissions only.

## Migration

Alembic revision `0003_master_data_inventory` follows `0002_auth_organizations`. It creates `customers`, `suppliers`, `products`, `inventory_locations`, `inventory_balances`, and `inventory_movements` plus indexes, constraints, and foreign keys.

Apply it with:

```bash
cd backend
alembic upgrade head
```

Do not edit deployed schema manually.

## Tests

`backend/tests/test_master_data_inventory.py` covers master-data creation/search/update, duplicate SKU protection, inventory receipt/dispatch/reservation behavior, idempotent retry and conflict handling, invalid quantities, low-stock aggregation, organization isolation, and ensuring rejected movements do not leave an empty balance. Run all backend tests with:

```bash
cd backend
pytest -q
```

Validation performed in this environment: Python compilation succeeded; **28 backend tests passed**; Alembic upgrade to `0003_master_data_inventory` succeeded against a temporary SQLite database. PostgreSQL runtime/locking behavior must still be tested in the configured Docker/PostgreSQL environment. Frontend production build and Vitest/typecheck were not run successfully because npm package installation timed out and the local `node_modules` directory is incomplete.

## Known boundaries

- Inventory movement `source_type` / `source_reference` are free-form references for now; future receipt/dispatch workflows should reference source records with real foreign keys and idempotency constraints.
- No supplier/product many-to-many preferred-supplier model is introduced in this phase.
- No import/export orders, shipment records, financial postings, document uploads, or order-driven inventory changes are implemented yet.
- The lock strategy serializes movements at the product row on PostgreSQL; high-throughput workloads may later benefit from a carefully designed per-balance lock strategy while preserving first-balance creation safety.
