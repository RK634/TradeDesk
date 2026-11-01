# Phase 11 — Reports and Archive

## Scope

Phase 11 completes the first reporting and historical-record layer on top of Phases 1–10. It adds organization-scoped APIs, typed report schemas, CSV downloads, a reports screen, and an archive/restore screen.

## Reports API

| Endpoint | Purpose | Permission |
|---|---|---|
| `GET /api/v1/reports/summary` | Import/export status, shipment counts, stock health, missing required documents, and optional financial summary | `reports.read` |
| `GET /api/v1/reports/orders` | Import/export order rows with partner, status, currency and order total | `reports.read` |
| `GET /api/v1/reports/partners` | Totals by customer/supplier, direction and currency | `reports.read` |
| `GET /api/v1/reports/import-costs` | Estimated versus actual import goods and landed costs | `reports.read` |
| `GET /api/v1/reports/shipment-performance` | Shipment status, estimated/actual arrival, and days late | `reports.read` |
| `GET /api/v1/reports/missing-documents` | Required documents without a verified version, for active orders and shipments | `reports.read` |
| `GET /api/v1/reports/inventory` | On-hand, reserved, available and low-stock quantities by product/location | `reports.read` |
| `GET /api/v1/reports/inventory-movements` | Inventory ledger report | `reports.read` |
| `GET /api/v1/reports/financial` | Outstanding receivables/payables and overdue values grouped by currency | `reports.read` + `reports.finance.read` |
| `GET /api/v1/reports/csv` | CSV export for supported datasets | `reports.read` + `reports.export`; finance datasets also require `reports.finance.read` |

Report date ranges default to the most recent 30 calendar days and are limited to 367 days. Financial and partner totals remain grouped by currency. Import cost variance is calculated as `actual_total - estimated_total`, with goods value and landed costs visible separately. Shipment days late are based on actual arrival when present, otherwise the elapsed days since ETA for shipments that have not arrived.

CSV text cells beginning with spreadsheet formula prefixes (`=`, `+`, `-`, `@`) are escaped. CSV responses are marked `no-store` and use attachment filenames.

## Archive API

| Endpoint | Purpose | Permission |
|---|---|---|
| `GET /api/v1/archive` | Search and paginate archived import/export orders | `archive.read` |
| `GET /api/v1/archive/eligible` | View received imports, delivered exports, and cancelled orders eligible for archiving | `orders.archive` |
| `POST /api/v1/archive/{record_type}/{record_id}` | Archive eligible order with reason | `orders.archive` |
| `POST /api/v1/archive/{record_type}/{record_id}/restore` | Restore with reason | `orders.restore` |
| `GET /api/v1/archive/{record_type}/{record_id}/history` | Read archive/restore event history | `archive.read` |

Archiving is a reversible status on the order, not a destructive delete. It writes an `archive_events` record and retains documents, invoices, payments, stock postings, and business audit records. Archived orders are hidden from normal operational order lists, order/shipment reports, and routine trade-operation reminders. Restoring the order does not rewrite its earlier financial or inventory history.

No scheduled or automatic purge is provided. An organization must establish retention periods and legal deletion criteria before any separately authorized permanent-deletion capability is introduced.

## Database

Alembic revision `0009_reports_archive` adds archive metadata columns to `import_orders` and `export_orders`, organization/archive indexes, and the `archive_events` audit table.

## Frontend

- `/app/reports` provides date filters, order status metrics, currency-separated finance positions, inventory balances, order register, import cost variance, partner totals, shipment performance, missing-document detail, and CSV actions.
- `/app/archive` provides search, eligible-record archive actions, archived record listing, restore actions, and event history.
- Navigation visibility is role-aware; backend permissions remain authoritative.

## Known limitations

- Shipment tracking is based on stored manual carrier/milestone updates. No live carrier API data is synthesized.
- Financial reporting is currency-separated; consolidated reporting currency conversion is not implemented in this phase.
- Archive retention is non-destructive. Permanent deletion, legal holds, and organization-specific retention schedules require policy decisions and a later controlled implementation.
