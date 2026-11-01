# Phase 9 — Invoices and Payments

Phase 9 adds organization-scoped supplier/customer invoicing, payment recording, allocation/reconciliation, balance calculation, and financial audit history. It uses the existing Phase 5 master data, Phase 6 import orders, Phase 7 export orders, Phase 8 document vault, authentication sessions, and role-permission checks.

## Delivered capabilities

### Invoices

- Create customer (receivable) and supplier (payable) invoice drafts.
- Link a supplier invoice to a supplier and, optionally, one of that supplier's import orders. Link a customer invoice to a customer and, optionally, one of that customer's export orders.
- Validate that linked partner/order records belong to the active organization and that the invoice currency matches the linked order currency.
- Store invoice number, issue/due dates, explicit three-letter currency code, notes, line descriptions, quantity, unit price, tax rate, net, tax, and line totals.
- Edit draft invoices only. Issue a draft as a financial record or void an unpaid invoice with a reason. Issued invoices cannot be silently rewritten.
- Derive paid amount and outstanding balance from posted payment allocations. Expose `overdue` as an effective response status when an issued/partially paid invoice is past due and still has a balance.

### Payments and allocations

- Record incoming payments against customer invoices and outgoing payments against supplier invoices.
- Support bank transfer, cash, card, cheque, and other payment methods, external references, and notes.
- A payment can be allocated across multiple invoices at creation. The allocated payment-currency total cannot exceed the payment amount; each invoice allocation cannot exceed its open balance.
- Payments may retain an unapplied balance. The reconciliation endpoint can allocate that balance to another open invoice later. A payment can have one allocation row per invoice; multiple separate payments can be allocated to the same invoice.
- Same-currency allocations require an exchange rate of exactly `1`. Cross-currency allocations require an explicit positive exchange rate and exchange-rate date. The stored rate convention is **invoice-currency units per one payment-currency unit**: `allocated_invoice_amount = allocated_payment_amount × exchange_rate`, rounded to two decimal places.
- The exchange rate and date are snapshots on each allocation. The system does not fetch market rates or overwrite historical conversion values.
- Payment creation uses a required idempotency key and a normalized request hash. Replaying the same key/payload returns the original payment; reusing the key with a changed payload returns HTTP `409`.
- Reconciliation of an already allocated payment/invoice pair is idempotent when the exact same allocation is replayed. A different allocation for that pair returns HTTP `409`.
- Posted payments are reversed through a controlled action with a required reason. Payment and allocation records remain in history; reversed allocations no longer reduce invoice balances or dashboard exposure.

### Financial dashboard

- `GET /api/v1/dashboard/summary` now includes `financial_metrics` grouped by currency.
- Each currency bucket shows customer receivables, supplier payables, overdue customer balances, overdue supplier balances, and open invoice count.
- Different currencies are never added together. Draft and void invoices are excluded. Reversed payment allocations do not reduce outstanding balances.

### Audit history and access control

- Financial audit events record invoice creation, update, issue, void, payment posting, payment allocation, payment reversal, and reconciliation actions, including actor and timestamp.
- Financial mutations require the existing authenticated session, CSRF/same-origin checks, organization membership, and action-specific backend permission.
- Queries and linked partner/order checks are scoped to the supplied organization. Cross-organization invoice, payment, customer, supplier, or order identifiers are not accepted as valid references.
- The `finance_staff` role can manage invoices/payments and perform reconciliation/adjustment actions. It also has read-only access to customers, suppliers, and import/export orders so invoice drafts can be linked to the correct business records; it does not receive import/export approval or inventory-adjustment permissions. Import/export operational roles do not receive financial mutation permissions by default.
- The React sidebar hides invoice/payment navigation for roles without financial read access, and direct page navigation displays a permission message. Backend authorization remains authoritative. Dashboard financial aggregates are omitted for members without `invoices.read`.

## API endpoint summary

All endpoints are under `/api/v1` and require the signed-in session plus `organization_id` query parameter.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/invoices` | Filter/search/paginate organization invoices |
| `POST` | `/invoices` | Create a draft invoice with line items |
| `GET` | `/invoices/{invoice_id}` | Read an invoice, items, paid amount, and outstanding balance |
| `PATCH` | `/invoices/{invoice_id}` | Update an eligible draft invoice |
| `POST` | `/invoices/{invoice_id}/issue` | Issue a draft invoice |
| `POST` | `/invoices/{invoice_id}/void` | Void an unpaid invoice with a reason |
| `GET` | `/invoices/{invoice_id}/audit` | Read invoice financial history |
| `GET` | `/payments` | Filter/search/paginate payments |
| `POST` | `/payments` | Record a payment and one or more allocations |
| `GET` | `/payments/{payment_id}` | Read payment, allocation, and unapplied-balance details |
| `POST` | `/payments/{payment_id}/allocations` | Allocate part of an existing payment's unapplied balance to another invoice |
| `POST` | `/payments/{payment_id}/reverse` | Reverse a posted payment with a reason |
| `GET` | `/payments/{payment_id}/audit` | Read payment financial history |

Payment allocation mutations use `X-CSRF-Token` and require the payment reconciliation permission. Payment creation uses `payments.create`; reversal uses `payments.adjust`.

## Database migration

Alembic revision `0007_financials` follows `0006_documents_shipments` and creates:

- `invoices`
- `invoice_items`
- `payments`
- `payment_allocations`
- `financial_audit_events`

The migration also adds a composite supplier key used by the organization-scoped invoice/supplier relationship. Foreign keys, unique constraints, indexes, amount checks, currency columns, and organization-scoped references protect the financial records.

## Calculation and operational assumptions

- Monetary amounts use Python `Decimal` and PostgreSQL `NUMERIC`; binary floating-point is not used for backend money arithmetic.
- The initial implementation applies **two decimal places and `ROUND_HALF_UP`** to monetary totals, tax amounts, discounts, allocations, and FX-converted amounts. It does not yet apply currency-specific minor-unit precision (for example, zero- or three-decimal currencies). Configure or extend the currency precision policy before enabling such currencies in production.
- Invoice line net and tax values are rounded per line, then aggregated. Discount is applied to the sum of line net plus tax and cannot exceed that sum.
- Tax is a simple percentage supplied on each line. It is not a jurisdiction-specific tax engine and does not determine legal tax treatment.
- FX rates are manually supplied by an authorized caller. There is no external exchange-rate provider, bank feed, payment gateway, automated bank reconciliation, accounting-system posting, invoice PDF generation, or invoice email delivery in this phase.
- The current React UI creates same-currency payments and same-currency reconciliations. The API and data model support cross-currency allocation with an explicit rate/date snapshot; the UI does not yet provide FX-rate entry controls.
- The payment register is not a general ledger. It records operational payment facts and allocations; accounting policy, statutory reporting, VAT returns, and tax compliance require separate review and integration.

## Validation coverage

`backend/tests/test_finance.py` covers invoice totals and rounding, draft update/issue/void lifecycle rules, partial and complete payments, idempotent payment replay, unapplied-balance reconciliation and replay, changed-payload conflicts, duplicate invoice/payment references, supplier outgoing payments, payment reversals, currency conversion snapshots, overpayment prevention, cross-organization isolation, currency-separated dashboard exposure, role-specific financial metric masking, and finance-staff read access to linked partner/order records without operational mutation permissions.

Run the backend tests and migration checks using the commands in the root README. PostgreSQL row-locking/concurrency behavior must still be exercised against a PostgreSQL instance; SQLite API tests do not prove production locking behavior.
