# TradeDesk — functionality and user guide

## Public website and first sign-in

The public homepage explains what TradeDesk manages, describes the main business capabilities, and guides prospective users through the overall workflow. It intentionally does not expose API documentation links, database readiness details, developer status, or implementation-phase labels. Sign in takes existing users to their workspace; authenticated users who visit the public root URL are redirected to `/app`.

## How to use TradeDesk dashboard guide

After choosing an organization, the dashboard shows a **How to use TradeDesk** guide. It explains the order of work and links to the relevant screens:

1. Set up organization information and invite the team.
2. Add customers, suppliers, products, and warehouse locations.
3. Create import orders and confirm goods receipts; confirmed receipts update stock.
4. Create export orders; approval reserves stock and dispatch deducts on-hand stock.
5. Record shipment milestones and upload/verify documents.
6. Issue invoices, allocate payments, and review reports.

The guide explains the effect of each action and does not show development-phase names.


This guide lists the application functionality delivered across Phases 1–12 and explains the practical user workflows. The backend is the authority for organization scope, roles, stock, payments, and status transitions; hiding a frontend action is not treated as security.

## 1. Sign in and organization workspace

**Navigation/pages:** `/register`, `/login`, `/accept-invitation`, `/app/organization`.

**What it does:** Creates a user and organization owner, signs a user in with a hashed password and database-backed session, provides organization membership, role assignments, invitations, and secure logout.

**How to use it:**

1. In a new development workspace, open **Create an account** and enter your name, email, organization name, and a password of at least 12 characters.
2. The first registered user becomes the organization owner.
3. Use the organization selector in the application header to switch between organizations where you have active membership.
4. Organization owners/administrators can manage members and generate invitations in **Organization & members**.
5. Share the one-time invitation token/link out of band with the invited user; SMTP delivery is not currently configured.
6. Use **Sign out** to revoke the current session.

For a controlled deployment, an initial owner can also be created using `python -m app.cli create-owner --email ... --name ... --organization ...` inside the backend container. The password is requested interactively.

## 2. Dashboard

**Page:** `/app`.

**What it does:** Displays organization-scoped counts and operational signals from persisted data, including membership/workspace data and available import/export, inventory, shipment, task, approval, document, and financial metrics as implemented. Financial figures are omitted for roles without financial read permission.

**How to use it:** Select an organization in the header, choose a date range where supported, and use dashboard cards/links to navigate to the related module. The first screen is not seeded with fake trade data: create master records and orders to populate operational metrics.

## 3. Customers and suppliers

**Pages:** `/app/customers`, `/app/suppliers`.

**What it does:** Maintains organization-scoped business partner master data used by export and import orders, respectively. Records can be searched, created, updated, and activated/deactivated.

**How to use it:** Create a supplier before an import order. Create a customer before an export order. Enter contact, address, country, payment terms, and preferred currency where applicable. Avoid creating duplicate partner records; duplicate suggestions/validation depend on the fields supported by the form/API.

## 4. Products, locations, and inventory

**Pages:** `/app/products`, `/app/locations`, `/app/inventory`.

**What it does:** Stores product SKUs, units, prices, reorder thresholds, inventory locations, quantity on hand, reserved quantity, available quantity, and an auditable movement ledger.

**How to use it:**

1. Create product records and one or more inventory locations.
2. Record opening stock through an authorized inventory movement using the documented movement reason and idempotency key.
3. Review stock balances and low-stock alerts in **Inventory**.
4. Review the stock movement history when reconciling a balance.
5. Never edit a stock balance directly; use a receipt, dispatch, reservation/release, return, or authorized adjustment.

Available stock is calculated as on-hand stock less reserved stock. A receipt or dispatch only changes inventory when its business transaction commits.

## 5. Import management

**Page:** `/app/imports`.

**What it does:** Handles purchase-side orders from draft through approval, shipment, partial goods receipt, actual cost entry, and receipt completion.

**How to use it:**

1. Create the supplier and product master records first.
2. Create a draft import order and add order lines with quantities, unit prices, currency, origin/destination, terms, and estimated dates/costs.
3. Submit the completed draft for approval. An authorized approver approves or returns it with a reason.
4. Record one or more inbound shipments and manual milestones; add carrier/tracking reference and ETD/ETA where known.
5. Upload relevant purchase/shipping documents and verify them.
6. When physical goods arrive, record a goods receipt with the quantities actually received. Partial receipts are supported. The receipt transaction posts stock ledger movements atomically and prevents over-receipt/duplicate posting.
7. Enter actual freight, insurance, duties, and other costs to support landed-cost variance reporting.
8. Review receipt and status history before considering the order complete/eligible for archive.

Creating or approving an import order alone does not add stock. Stock is increased only by a confirmed goods receipt.

## 6. Export management

**Page:** `/app/exports`.

**What it does:** Handles sales-side orders from draft through approval, stock reservation, shipment dispatch, partial deliveries, and order completion.

**How to use it:**

1. Create the customer and product records and make sure stock exists at the selected location.
2. Create an export draft with products, quantities, selling prices, destination, terms, and planned dates.
3. Submit the order for approval.
4. An authorized approver checks stock and approves the order. Approval reserves available stock.
5. Create a dispatch shipment for a permitted part or all of the reserved quantity. Dispatch releases the relevant reservation and deducts on-hand stock in one transaction.
6. Record partial or complete delivery against the dispatched quantities.
7. Review the shipment and delivery history. The same idempotency key and payload can be safely replayed; a changed payload under an already-used key is rejected.

A draft does not reserve stock. Approval reserves stock. Dispatch deducts stock. Delivery does not deduct stock again.

## 7. Shipments and timelines

**Page:** `/app/shipments`.

**What it does:** Provides a combined import/export shipment register with manual milestones, estimated/actual dates, status, and delay reasons.

**How to use it:** Find a shipment by reference/order, update its status and dates, add a dated milestone when a meaningful event occurs, and record a delay reason when marking a shipment delayed. Events are manually entered. No live carrier API is connected.

## 8. Documents and verification

**Page:** `/app/documents`.

**What it does:** Stores private trade documents associated with orders/shipments, document versions, verification history, and configured required-document checks.

**How to use it:** Upload a document against the relevant record, choose its category and expiry date where applicable, upload a new version rather than silently replacing a prior version, and have an authorized reviewer verify or reject it with notes. Use compliance/missing-document views to see configured requirements that do not have a verified and unexpired file.

Uploaded files are not served from the public frontend directory. Authorized API download endpoints enforce access. Malware scanning is not currently integrated; do not treat file-signature checks as a virus scan.

## 9. Invoices and payments

**Pages:** `/app/invoices`, `/app/payments`.

**What it does:** Supports supplier/customer invoices, line items, taxes/discounts, issue/void workflows, incoming/outgoing payment records, partial payment allocations, unapplied balances, reversal records, and financial audit history.

**How to use it:**

1. Create an invoice and link it to the relevant supplier/customer and import/export order.
2. Add line items, tax/discount values, invoice currency, and due date.
3. Issue the invoice to make it part of the financial workflow.
4. Record a payment with its payment currency, date, method/reference, and any invoice allocation.
5. Allocate an unapplied balance to another eligible invoice where appropriate.
6. Review remaining/outstanding balances and audit events. Use a controlled reversal with a reason for a correction rather than editing financial history.

Money calculations use `Decimal`. Invoice currency and payment currency remain explicit. Exchange-rate values are stored as transaction snapshots where conversion/allocation occurs; the application does not fetch a live FX rate feed. Reports group amounts by currency and do not sum unlike currencies.

## 10. Tasks and approvals

**Pages:** `/app/tasks`, `/app/approvals`.

**What it does:** Creates assigned work items with due dates, priority, status history, comments, and approval requests with configured roles and decision history.

**How to use it:** Create a task, set owner/assignee and due date, add comments, and update status as work progresses. Submit a supported business action for approval; an authorized reviewer approves, rejects, or returns it with a reason. Import/export approvals use their own workflow operations so the relevant stock/order checks remain in force.

## 11. Notifications and automation

**Page:** `/app/notifications`.

**What it does:** Provides per-user notification preferences, unread counts, read/read-all controls, and duplicate-safe reminder logs. The worker evaluates supported events such as overdue/upcoming invoices, pending approvals, overdue/upcoming shipment ETAs, low stock, expiring documents, missing required documents, and overdue tasks.

**How to use it:** Review the notification center, mark completed notices as read, configure enabled categories, and ask an owner/administrator to review automation logs when investigating generated reminders. The worker is controlled by `AUTOMATION_ENABLED` and polls at `AUTOMATION_POLL_SECONDS`.

Reminders are in-app notifications. SMTP/email, SMS, and external push notifications are not configured.

## 12. Reports and CSV export

**Page:** `/app/reports`.

**What it does:** Produces date-filtered order summaries, inventory/stock movement reports, import cost variance, customer/supplier totals, shipment performance, missing-document details, and receivables/payables by currency.

**How to use it:** Select the reporting period, review the appropriate section, and use its CSV export action if your role has report-export permission. Financial report endpoints require financial reporting permission. The reports use persisted business records; there are no fabricated dashboard/report totals. CSV output includes basic spreadsheet formula-prefix escaping.

## 13. Archive and restore

**Page:** `/app/archive`.

**What it does:** Archives eligible received import orders, delivered export orders, and cancelled orders. It records who archived/restored the order, date, reason, and history.

**How to use it:** Filter the eligible list, open an eligible order, archive it with a meaningful reason, and later search archived records. An authorized user can restore an archived order with a reason. Archive does not delete records/documents/invoices/payments or set a legally approved retention period.

## 14. Organization roles

The initial roles are **Organization Owner**, **Administrator**, **Import Manager**, **Export Manager**, **Operations Staff**, **Finance Staff**, and **Read-Only User**. The UI hides selected navigation for roles without read permissions, but every protected API endpoint independently checks organization membership and role permissions. The owner/admin roles manage organization users/settings. Finance Staff handle invoice/payment/reporting operations but do not receive stock adjustment or import/export approval privileges by default. Read-only users can inspect permitted records but cannot post business changes.

For the authoritative permission mapping, see `backend/app/core/permissions.py`; for backend coverage, see `backend/tests/`.

## 15. Functionality intentionally not included

- Live tracking-provider/carrier API integration.
- Outbound invitation email, account email verification, password reset/account recovery, email notifications, and SMS/push.
- Malware/antivirus scanning for uploaded files.
- Automatic FX rate sourcing or bank-feed/payment gateway integration.
- Automatic customs filing, document legal determination, or jurisdiction-specific trade compliance advice.
- Permanent retention-based deletion/purge jobs.
- Production TLS termination, centralized observability, off-site encrypted backup storage/rotation, and disaster recovery are deployment responsibilities and must be configured for the target environment.

## 16. Support and troubleshooting

- Check `http://localhost:8000/api/v1/health/live` for process liveness and `/api/v1/health/ready` for database readiness.
- Open `http://localhost:8000/docs` in development for API contracts.
- Inspect logs with `docker compose logs --tail=200 backend worker frontend`.
- If the frontend is reachable but APIs fail, confirm that migrations were applied and `DATABASE_URL` points to the Compose database.
- If login writes fail with a CSRF error, refresh the app to obtain a new CSRF cookie/token and retry.
- If an upload fails, check the configured upload limit, private storage volume permissions, and selected storage backend.
