# Importer & Exporter Management System

A modular-monolith international trade management application. This cumulative release includes **Phases 1–12**: architecture, project foundation, authentication and organizations, dashboard, master data and inventory, import management, export management, documents and shipments, invoices and payments, tasks and approvals, reports and archive, and final testing/deployment preparation.

## Current release: 1.0.2

This release replaces the technical starter homepage with a public TradeDesk product website, redirects authenticated users directly to their workspace, removes development-phase labels and unavailable navigation placeholders from the signed-in experience, and adds a practical in-app guide explaining each business workflow and its effects. See [`docs/WEBSITE-AND-WORKSPACE-UX-1.0.2.md`](docs/WEBSITE-AND-WORKSPACE-UX-1.0.2.md).

## Implemented phases

### Phase 1 — Architecture and planning

- System and component architecture
- Database ER diagram and major relationships
- API plan and role/permission matrix
- Import and export workflow design
- Development milestones and key technical decisions

See [`docs/phase1-architecture.md`](docs/phase1-architecture.md).

### Phase 2 — Project foundation

- React + TypeScript + Vite frontend
- FastAPI REST backend under `/api/v1`
- SQLAlchemy 2.x and Alembic
- PostgreSQL 16 Docker Compose service
- Environment-based configuration, JSON logging, API health checks
- Frontend and backend containers

### Phase 3 — Authentication and organizations

- Registration creates the first user, organization, and organization-owner membership transactionally.
- Login verifies Argon2 password hashes and issues a database-backed opaque session.
- Logout revokes the current session.
- `HttpOnly` session cookie, CSRF cookie/header validation, allowed-Origin checks, absolute session expiry.
- Organization membership and role checks are enforced on the backend.
- Organization creation and member list/role/status management.
- Single-use, expiring organization invitations with token hashes stored in the database.
- Protected React workspace route, login, registration, and invitation acceptance pages.
- Pytest coverage for auth, CSRF, session revocation, organization isolation, member permissions, and invitation behavior.

See [`docs/phase3-authentication-organizations.md`](docs/phase3-authentication-organizations.md) for flows, endpoints, roles, and remaining limitations.

### Phase 4 — Application shell and dashboard

- Responsive nested application shell with collapsible sidebar, top navigation, organization selector (desktop and mobile), navigation filtering, user identity, and working sign-out.
- Protected dashboard and organization administration routes.
- Organization-scoped `GET /api/v1/dashboard/summary` API with server-validated date ranges and role-aware invitation counts.
- Real workspace metrics: total, active, inactive, and new memberships; pending invitations are returned only for roles with invitation visibility.
- Real charts for membership joins over time and active membership distribution by role.
- Loading skeletons, retryable API errors, organization-scoped business metrics, and a practical in-app guide that explains workspace setup, master data, import/export, logistics, and finance workflows.
- The signed-in sidebar displays working module destinations only; unavailable placeholder links are not shown.

See [`docs/phase4-dashboard.md`](docs/phase4-dashboard.md) for the endpoint contract, metric boundaries, and validation results.

### Phase 5 — Master data and basic inventory ledger

- Organization-scoped CRUD/list APIs for customers, suppliers, products, and inventory locations; collection endpoints support search and pagination.
- React pages for Customers, Suppliers, Products, Inventory, and Inventory Locations, including create/edit, active/inactive state, search, and loading/error states.
- Products use numeric monetary values and a currency code. Customer/supplier payment terms and country/currency inputs are validated and normalized.
- Inventory balances are scoped to a product and location. The append-only stock ledger records receipts, dispatches, reservations, reservation releases, adjustments, and returns.
- Stock movements are permission-checked, transactional, idempotent, and protected against negative stock and dispatching reserved units. Low-stock values are calculated from available quantity and the product's reorder threshold.
- Alembic revision `0003_master_data_inventory` adds the six Phase 5 tables and supporting constraints/indexes. The dashboard reports inventory as available but leaves later trade and financial modules explicitly unavailable.

See [`docs/phase5-master-data-inventory.md`](docs/phase5-master-data-inventory.md) for endpoints, movement rules, validation results, and limitations.

### Phase 6 — Import management

- Organization-scoped import order list, search, status filters, reference generation, detail views, item line editing, and planning details.
- Draft → submitted → approved / returned for correction → partial or complete goods receipt, with cancellation safeguards and append-only status history. Approval requires the Owner or Administrator permission; an Import Manager cannot approve their own submitted order through the normal role map.
- Estimated and actual logistics costs use `Decimal`/PostgreSQL `NUMERIC`; order cost summaries are kept in the order's explicit currency.
- Manual shipment records, status transitions, date validation, milestones, and order-level actual departure/arrival aggregation. External carrier tracking is not connected.
- Partial goods receipts update order-line received quantities, inventory balance, import receipt records, and inventory ledger movements in a database transaction. Each receipt has an idempotency key; replaying the same request does not post stock twice. Over-receipts are rejected.
- Private import documents support upload, authorized download, verification metadata, and deletion. Upload sizes and extensions are constrained, common file signatures are checked, and uploaded files stay outside public frontend assets.
- Live dashboard import metrics include active orders, awaiting approval, partially received orders, received orders, and delayed shipments.
- Revision `0004_import_management` adds import orders/items/status history, shipments/milestones, goods receipts/items, and document metadata.
- Pytest covers order approval, partial/duplicate receipt behavior, over-receipt prevention, inventory posting, shipment dates/milestones, private documents, and organization isolation.

See [`docs/phase6-import-management.md`](docs/phase6-import-management.md) for the workflow, endpoint summary, receipt posting guarantees, file handling, and remaining limitations.

### Phase 7 — Export management

- Organization-scoped export orders linked to customers, product snapshots, and inventory locations, with draft editing and status history.
- Owner/administrator approval validates available stock and reserves quantities transactionally.
- Partial shipment dispatch releases the corresponding reservation and deducts on-hand stock in the same transaction.
- Partial delivery records track delivered quantities without deducting stock a second time.
- Idempotency keys protect shipment and delivery posting against retries; altered payloads with an existing key are rejected.
- Export dashboard metrics are calculated from persisted data.
- Revision `b0c9e3760d43` adds export tables and the required composite customer-organization key; revision `c4b14ad0e571` follows it as an empty metadata reconciliation revision.
- Pytest covers approval, stock reservation, partial dispatch and delivery, idempotency, insufficient stock, and organization isolation.

See [`docs/phase7-export-management.md`](docs/phase7-export-management.md) for workflow details, API endpoints, inventory guarantees, and limitations.

### Phase 8 — Documents and shipment tracking

- Unified document vault for import/export orders and shipments, with authenticated, organization-scoped upload and download endpoints.
- Private local filesystem adapter for development and S3-compatible private object storage for production; no public URLs or public ACLs are generated.
- Upload size/extension/signature checks, SHA-256 checksums, immutable file versions, document verification/rejection audit history, and re-verification after a new version is uploaded.
- Configurable required/optional document rules per order or shipment. The system does not assume a document is universally required; compliance checks require a matching verified, unexpired file.
- Unified import/export shipment register with filters, status transitions, delay reasons, manual milestones, and system-generated creation/status timeline entries.
- Export deliveries remain controlled by the Phase 7 delivery workflow; live carrier tracking is not integrated and the interface identifies events as manually recorded.
- Alembic revision `0006_documents_shipments` adds document/version/audit/requirement tables, export shipment milestones, and export shipment delay/update fields.
- The backend test suite covers private upload/download, verification/versioning, compliance checks, cross-organization access, shipment status updates, delay handling, milestones, and export delivery constraints.

See [`docs/phase8-documents-shipments.md`](docs/phase8-documents-shipments.md) for storage configuration, endpoints, migration details, security boundaries, verification results, and limitations.

### Phase 9 — Invoices and payments

- Organization-scoped supplier and customer invoices, optionally linked to the matching supplier/import order or customer/export order. Partner, linked-order ownership, and order currency are validated by the backend.
- Draft invoice creation and editing, issuing, controlled voiding of unpaid invoices, line-level quantity/price/tax calculations, and invoice registers. Issued records are not silently rewritten.
- Customer incoming payments and supplier outgoing payments, with partial payments, one or more allocations per payment, unapplied balances, and later reconciliation against another invoice.
- Idempotency keys and request hashes prevent duplicate payment posting. Exact reconciliation replays return the existing allocation; changed allocations are rejected.
- Explicit currency and FX snapshots per allocation. The exchange rate is expressed as invoice-currency units per one payment-currency unit, with the rate and conversion date preserved in history.
- Controlled payment reversal with a reason. Reversed allocations remain auditable but no longer reduce invoice balances.
- Financial audit events, backend role/organization authorization, and dashboard receivables/payables grouped separately by currency. Finance Staff can read the required customer, supplier, and order records to link invoices, but do not receive import/export approval or inventory-adjustment permissions.
- Financial navigation and direct page access are permission-aware; dashboard financial aggregates are omitted for roles without invoice-read permission.
- Alembic revision `0007_financials` adds invoices, invoice items, payments, payment allocations, and financial audit events.
- Pytest covers invoice calculations, partial payments, payment replay, unapplied-balance reconciliation, FX snapshots, reversal, overpayment prevention, tenant isolation, and currency-separated dashboard metrics.

See [`docs/phase9-invoices-payments.md`](docs/phase9-invoices-payments.md) for endpoint contracts, calculation rules, currency assumptions, permission boundaries, verification coverage, and remaining limitations.


### Phase 10 — Tasks, approvals, notifications, and automation

- Organization-scoped task lifecycle with assignment to active members, priority, due date, related trade record, comments, and append-only status history.
- Configurable approval rules for import/export orders, invoices, payments, tasks, and custom actions; backend authorization checks action-specific approver roles, thresholds, and self-approval policy.
- Central approval inbox with submitted/approved/rejected/returned/cancelled states and actor/time/reason history. Import/export approval decisions continue through their domain endpoints so stock and order-state invariants cannot be bypassed.
- Per-user in-app notification inbox, unread count, read actions, category filters, and per-organization preferences. Notification APIs return only the current user's records.
- A separate lightweight worker creates duplicate-safe reminder notifications for task due dates, pending approvals, invoice due dates, shipment ETAs/delays, low stock, expiring documents, and missing required documents.
- Automation logs record event status, recipient count, retries, and failures. Failed events retry on later cycles up to five attempts; notification preferences are honored.
- Manual reminder runs and automation log inspection are restricted to organization owners/administrators and scoped to the selected organization. Scheduled worker scans are organization-aware.
- Automation sends reminders only; it does not auto-approve orders, post payments, dispatch goods, or change inventory.
- Alembic revision `0008_tasks_approvals_automation` adds tasks/comments/history, approval rules/requests/events, notifications/preferences, and automation logs.
- The API test suite covers task lifecycle, organization isolation, role-configured approvals, decision history, notification read/preference behavior, and duplicate-safe task/approval/shipment reminders.

See [`docs/phase10-tasks-approvals-automation.md`](docs/phase10-tasks-approvals-automation.md) for endpoints, permission boundaries, worker configuration, test coverage, and limitations.

## Technology baseline

- Node.js 22 LTS line
- Python 3.12
- PostgreSQL 16
- React 18, TypeScript 5, Vite 6
- FastAPI, Pydantic 2, SQLAlchemy 2, Alembic
- Tailwind CSS 3 and shadcn/ui-compatible components
- TanStack Query, React Hook Form, Zod, Lucide, Recharts
- Argon2 password hashing through `argon2-cffi`

Version pins are in `frontend/package.json` and `backend/requirements.txt`. They are a selected baseline, not a claim to be the latest versions. Review dependency advisories before deployment.

## Prerequisites

Recommended: Docker Engine/Desktop with Docker Compose v2. For non-Docker development, install Node.js 22/npm, Python 3.12, and PostgreSQL 16.

## Option A — Run with Docker Compose

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Change `POSTGRES_PASSWORD` in `.env` to a strong local development password. Use URL-safe characters for this Compose example; keep `.env` untracked. `SESSION_COOKIE_SECURE=false` is for local HTTP development only.

3. Build and start the frontend, backend, and PostgreSQL services:

   ```bash
   docker compose up --build -d
   ```

4. Apply database migrations:

   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. Open the services:

   - Frontend: http://localhost:8080
   - API root: http://localhost:8000/
   - API docs: http://localhost:8000/docs
   - Liveness: http://localhost:8000/api/v1/health/live
   - Database readiness: http://localhost:8000/api/v1/health/ready

6. If `ALLOW_SELF_REGISTRATION=true`, open the frontend and choose **Get started**. Registration creates the first organization owner. For a new deployment, disable public registration before exposing it to users.

To stop services:

```bash
docker compose down
```

To delete the local development database volume as well (destructive):

```bash
docker compose down -v
```

### Create the first owner when self-registration is disabled

Set `ALLOW_SELF_REGISTRATION=false`, start the backend and apply migrations, then run this interactive command. It prompts for the password twice and never accepts the password as a command-line argument:

```bash
# Docker

docker compose exec backend python -m app.cli create-owner \
  --email admin@example.com \
  --name "Initial Owner" \
  --organization "Example Trading GmbH"

# Or run from backend/ in a configured local Python environment
python -m app.cli create-owner \
  --email admin@example.com \
  --name "Initial Owner" \
  --organization "Example Trading GmbH"
```

The command creates the owner, organization, and owner membership in one transaction. The database must already be migrated.

## Option B — Run services locally

1. Copy `.env.example` to `.env` in the repository root and configure PostgreSQL.
2. Start PostgreSQL and create the configured database/user.
3. Start the API in one terminal:

   ```bash
   cd backend
   python3.12 -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. Start the frontend in another terminal:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Vite is configured for http://localhost:5173 and proxies `/api` to `http://127.0.0.1:8000`. Change `VITE_DEV_PROXY_TARGET` if your API uses a different local port.

## Environment variables

| Variable | Purpose | Development example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection | `postgresql+psycopg://...@localhost:5432/...` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose database setup | Local-only values |
| `APP_ENV` | Environment mode | `development` |
| `CORS_ORIGINS` | Explicit allowed frontend origins | `http://localhost:5173,http://localhost:8080` |
| `ALLOW_SELF_REGISTRATION` | Toggle public account registration | `true` locally; consider `false` in production |
| `SESSION_TTL_HOURS` | Absolute session lifetime | `12` |
| `SESSION_COOKIE_SECURE` | Require HTTPS for session/CSRF cookies | `false` locally; must be `true` in production |
| `INVITATION_TTL_HOURS` | Invitation validity | `72` |
| `PRIVATE_STORAGE_DIR` | Root directory for private uploaded trade documents | `.private_storage` locally; `/app/.private_storage` in Compose |
| `STORAGE_BACKEND` | Private storage adapter | `local` in development; `s3` in production |
| `S3_BUCKET_NAME`, `S3_REGION`, `S3_ENDPOINT_URL` | S3-compatible private object storage configuration | Private bucket and provider endpoint |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Object-storage credentials when static credentials are used | Inject through secret management; leave blank if using workload identity |
| `MAX_UPLOAD_BYTES` | Maximum size for each uploaded document | `15728640` (15 MiB) |
| `VITE_API_BASE_URL` | Frontend API prefix | `/api/v1` |
| `VITE_DEV_PROXY_TARGET` | Vite API proxy target | `http://127.0.0.1:8000` |

Do not commit `.env` or real secrets. The production settings validator rejects `APP_ENV=production` unless `SESSION_COOKIE_SECURE=true`, `STORAGE_BACKEND=s3`, and `S3_BUCKET_NAME` are configured.

## Migrations

Alembic revision `0001_baseline` establishes the initial chain. Revision `0002_auth_organizations` adds the Phase 3 auth/organization schema. Revision `0003_master_data_inventory` adds Phase 5 customers, suppliers, products, locations, balances, and movements. Revision `0004_import_management` adds Phase 6 import orders, order lines, approval history, shipments, milestones, goods receipts, receipt lines, and legacy document metadata. Revisions `b0c9e3760d43` and `c4b14ad0e571` add the Phase 7 export schema. Revision `0006_documents_shipments` adds Phase 8 document versioning/verification/requirements and the unified shipment timeline extensions. Revision `0007_financials` adds organization-scoped invoices, invoice items, payments, payment allocations, and financial audit events. Revision `0008_tasks_approvals_automation` adds task/comment/status history, configurable approval rules/requests/events, user notifications/preferences, and automation logs. Revision `0009_reports_archive` adds report query indexes and archive metadata/audit events. Phase 12 intentionally has no schema migration.

```bash
cd backend
alembic current
alembic history
alembic upgrade head
```

The cumulative migration chain ends at `0009_reports_archive`. Phase 12 does not add a schema revision; it adds runtime hardening, test/CI automation, browser smoke-test coverage, operational scripts, and release documentation. A temporary SQLite migration upgrade, `alembic check`, downgrade-one-revision, and re-upgrade cycle passed in the local validation run. The backend suite has **83 passing tests**. Frontend syntax transpilation checked 61 TypeScript/TSX files without syntax diagnostics. A full frontend typecheck was attempted but stops because `vite/client` is not installed; frontend unit tests/production build and Docker/PostgreSQL runtime checks were not run in this environment. CI is configured to run those checks on GitHub Actions, including migration validation against PostgreSQL 16. Do not manually edit deployed schema objects; add reviewed migrations.

## Tests and validation

Backend unit/API tests:

```bash
cd backend
pytest -q
```

Frontend checks:

```bash
cd frontend
npm run typecheck
npm run test -- --run
npm run build
```

Compose validation and runtime checks:

```bash
docker compose config
docker compose ps
docker compose logs --tail=100 backend
```

The backend API suite uses an isolated SQLite in-memory database. The CI workflow additionally upgrades and checks the schema against PostgreSQL 16, builds both container images, executes frontend typecheck/unit tests/production build, and runs a Playwright registration-to-dashboard-to-logout browser smoke test. Local PostgreSQL row-locking and live S3 provider behavior must still be exercised in the deployment environment.

## API endpoint summary

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/health/live` | API process liveness |
| `GET` | `/api/v1/health/ready` | Database readiness check |
| `GET` | `/api/v1/auth/csrf` | Issue/rotate CSRF token |
| `POST` | `/api/v1/auth/register` | Register first user and organization owner (if enabled) |
| `POST` | `/api/v1/auth/login` | Sign in |
| `POST` | `/api/v1/auth/logout` | Revoke current session |
| `GET` | `/api/v1/auth/me` | Signed-in identity and active organizations |
| `POST` | `/api/v1/auth/invitations/preview` | Preview invitation (token in request body) |
| `POST` | `/api/v1/auth/accept-invitation` | Accept invitation |
| `GET` | `/api/v1/dashboard/summary` | Organization-scoped dashboard aggregates and date-filtered member trend |
| `GET` | `/api/v1/organizations` | List memberships |
| `POST` | `/api/v1/organizations` | Create organization |
| `GET` | `/api/v1/organizations/{id}/members` | List organization members, if allowed |
| `PATCH` | `/api/v1/organizations/{id}/members/{membership_id}` | Change allowed member role/status |
| `POST` | `/api/v1/organizations/{id}/invitations` | Create invitation |
| `DELETE` | `/api/v1/organizations/{id}/invitations/{invitation_id}` | Revoke pending invitation |
| `GET/POST` | `/api/v1/customers` | List/create organization-scoped customers |
| `GET/PATCH` | `/api/v1/customers/{id}` | Read/update customer or active status |
| `GET/POST` | `/api/v1/suppliers` | List/create organization-scoped suppliers |
| `GET/PATCH` | `/api/v1/suppliers/{id}` | Read/update supplier or active status |
| `GET/POST` | `/api/v1/products` | List/create organization-scoped products |
| `GET/PATCH` | `/api/v1/products/{id}` | Read/update product or active status |
| `GET/POST` | `/api/v1/inventory/locations` | List/create inventory locations |
| `GET/PATCH` | `/api/v1/inventory/locations/{id}` | Read/update inventory location or active status |
| `GET` | `/api/v1/inventory/balances` | Query real stock balances and low-stock records |
| `GET/POST` | `/api/v1/inventory/movements` | Query ledger / post idempotent stock movements |
| `GET/POST` | `/api/v1/imports` | Search/list import orders and create a draft order |
| `GET/PATCH` | `/api/v1/imports/{order_id}` | Read/update import order planning details |
| `POST` | `/api/v1/imports/{order_id}/submit` | Submit a complete order for approval |
| `POST` | `/api/v1/imports/{order_id}/approve` | Approve submitted order (owner/administrator) |
| `POST` | `/api/v1/imports/{order_id}/reject` | Return a submitted order with a reason |
| `POST` | `/api/v1/imports/{order_id}/receipts` | Post a partial or complete goods receipt and update inventory atomically |
| `GET` | `/api/v1/imports/{order_id}/receipts` | List recorded receipts |
| `GET/POST` | `/api/v1/imports/{order_id}/shipments` | List/create import shipments |
| `PATCH` | `/api/v1/imports/shipments/{shipment_id}` | Update shipment status and actual dates |
| `GET/POST` | `/api/v1/imports/shipments/{shipment_id}/milestones` | List/add manual shipment milestones |
| `GET/POST` | `/api/v1/imports/{order_id}/documents` | List/upload private import documents |
| `GET/PATCH/DELETE` | `/api/v1/imports/{order_id}/documents/{document_id}` | Download, verify/update, or delete an authorized document (download uses `/download`) |
| `GET/POST` | `/api/v1/exports` | Search/list export orders or create a draft export order |
| `GET/PATCH` | `/api/v1/exports/{order_id}` | Read or update an eligible export order |
| `POST` | `/api/v1/exports/{order_id}/submit` | Submit an export order for approval |
| `POST` | `/api/v1/exports/{order_id}/approve` | Approve order and reserve inventory |
| `POST` | `/api/v1/exports/{order_id}/reject` | Reject/return an order with reason |
| `POST` | `/api/v1/exports/{order_id}/cancel` | Cancel an eligible order and release outstanding reservations |
| `GET/POST` | `/api/v1/exports/{order_id}/shipments` | List shipments or dispatch reserved stock |
| `POST` | `/api/v1/exports/{order_id}/shipments/{shipment_id}/deliveries` | Record partial/full delivery against dispatched quantities |
| `GET` | `/api/v1/exports/{order_id}/deliveries` | List delivery records |
| `GET` | `/api/v1/documents` | List organization-scoped trade documents |
| `POST` | `/api/v1/documents` | Upload private document for an import/export order or shipment |
| `GET/POST` | `/api/v1/documents/{document_id}/versions` | List immutable document versions or upload a new version |
| `GET` | `/api/v1/documents/{document_id}/download` | Download an authorized document version |
| `PATCH` | `/api/v1/documents/{document_id}/verification` | Verify/reject document and record audit history |
| `GET` | `/api/v1/documents/{document_id}/verification-history` | Read verification history |
| `GET/POST` | `/api/v1/documents/requirements` | List/configure record-specific document requirements |
| `DELETE` | `/api/v1/documents/requirements/{requirement_id}` | Remove a configured document requirement |
| `GET` | `/api/v1/documents/compliance` | Evaluate configured requirements against verified/unexpired files |
| `GET` | `/api/v1/shipments` | Unified import/export shipment register |
| `PATCH` | `/api/v1/shipments/{shipment_type}/{shipment_id}` | Update shipment tracking details/status and delay reason |
| `GET/POST` | `/api/v1/shipments/{shipment_type}/{shipment_id}/milestones` | List/add chronological shipment timeline events |
| `GET/POST` | `/api/v1/invoices` | List or create organization-scoped supplier/customer invoice records |
| `GET/PATCH` | `/api/v1/invoices/{invoice_id}` | Read or update an eligible draft invoice |
| `POST` | `/api/v1/invoices/{invoice_id}/issue` | Issue a draft invoice |
| `POST` | `/api/v1/invoices/{invoice_id}/void` | Void an unpaid invoice with a reason |
| `GET` | `/api/v1/invoices/{invoice_id}/audit` | Read invoice financial audit history |
| `GET/POST` | `/api/v1/payments` | List payments or record incoming/outgoing payments with allocations |
| `GET` | `/api/v1/payments/{payment_id}` | Read payment and allocation details |
| `POST` | `/api/v1/payments/{payment_id}/allocations` | Reconcile an unapplied payment balance to another invoice |
| `POST` | `/api/v1/payments/{payment_id}/reverse` | Reverse a posted payment with an audit reason |
| `GET` | `/api/v1/payments/{payment_id}/audit` | Read payment financial audit history |
| `GET` | `/api/v1/reports/summary` | Date-filtered operational and permission-controlled financial summary |
| `GET` | `/api/v1/reports/orders` | Organization-scoped import/export order report |
| `GET` | `/api/v1/reports/inventory` | Current inventory/low-stock report |
| `GET` | `/api/v1/reports/inventory-movements` | Inventory ledger report |
| `GET` | `/api/v1/reports/import-costs` | Estimated versus actual import cost report |
| `GET` | `/api/v1/reports/partners` | Partner order totals by direction and currency |
| `GET` | `/api/v1/reports/shipment-performance` | Shipment arrival/delay report |
| `GET` | `/api/v1/reports/missing-documents` | Missing/unverified required-document report |
| `GET` | `/api/v1/reports/financial` | Currency-separated receivables/payables report |
| `GET` | `/api/v1/reports/csv` | Authorized CSV report download |
| `GET` | `/api/v1/archive` | Search archived import/export orders |
| `GET` | `/api/v1/archive/eligible` | List completed/cancelled orders eligible for archiving |
| `POST` | `/api/v1/archive/{record_type}/{record_id}` | Archive an eligible order with a reason |
| `POST` | `/api/v1/archive/{record_type}/{record_id}/restore` | Restore an archived order with a reason |
| `GET` | `/api/v1/archive/{record_type}/{record_id}/history` | Read archive/restore audit events |
| `GET/POST` | `/api/v1/tasks` | List/filter tasks or create an organization task |
| `GET` | `/api/v1/tasks/{task_id}` | Read a task with comments and status history |
| `PATCH` | `/api/v1/tasks/{task_id}` | Update task details or assignment |
| `POST` | `/api/v1/tasks/{task_id}/status` | Change task status and append status history |
| `POST` | `/api/v1/tasks/{task_id}/comments` | Add a task comment |
| `GET` | `/api/v1/approval-rules` | Read effective approval rules |
| `PUT` | `/api/v1/approval-rules/{business_action}` | Configure an approval rule (owner/admin) |
| `GET/POST` | `/api/v1/approvals` | List approvals or submit a generic action for approval |
| `POST` | `/api/v1/approvals/{approval_id}/decision` | Approve, reject, or return an approval request |
| `POST` | `/api/v1/approvals/{approval_id}/cancel` | Cancel an eligible generic pending request |
| `GET` | `/api/v1/notifications` | List current-user notifications with filters |
| `GET` | `/api/v1/notifications/unread-count` | Read current-user unread notification count |
| `PATCH` | `/api/v1/notifications/{notification_id}/read` | Mark one notification as read |
| `POST` | `/api/v1/notifications/read-all` | Mark all current-user notifications as read |
| `GET/PUT` | `/api/v1/notifications/preferences` | Read/update current-user notification preferences |
| `GET` | `/api/v1/notifications/automation-logs` | Read organization automation logs (owner/admin) |
| `POST` | `/api/v1/notifications/automation/run` | Run an organization-scoped reminder cycle (owner/admin) |

## Security and operational limitations

Phase 12 adds a safer deployment baseline, but **a successful local test suite does not certify a deployment as production-ready**. Before public exposure or real business data:

- Terminate HTTPS at a trusted ingress/reverse proxy, enable HSTS there, restrict ingress/network access, and configure `APP_ENV=production`, `SESSION_COOKIE_SECURE=true`, an explicit HTTPS-only `CORS_ORIGINS` allowlist, PostgreSQL, and private S3-compatible storage.
- Use a secret manager or deployment secrets for database and S3 credentials. Do not commit `.env` or share local development passwords.
- The bundled Nginx edge applies a basic per-client rate limit to login, registration, invitation preview, and invitation acceptance. If deployed behind another proxy, configure trusted client-IP forwarding at that ingress; for multiple Nginx/backend replicas, use a shared distributed rate limiter at the gateway/WAF.
- Invitation links are returned to the authorized inviter and must currently be shared out of band. SMTP delivery, email verification, password/account recovery, and outbound email notifications are not implemented.
- Live carrier tracking APIs and malware scanning for uploaded files are not implemented. Shipment milestones are manually recorded; document requirements are organization-configured workflow checks, not legal/customs advice.
- Archive is reversible and does not permanently delete records. Organizations must set their own legally reviewed retention schedule and separately implement any approved permanent-deletion process.
- Run and regularly test the backup/restore scripts. Backups must be stored encrypted and off-host in production; the provided scripts do not configure offsite replication or retention rotation.
- CI runs the browser smoke test and production build. The current working container used for this deliverable did not have npm dependencies or Docker available, so those particular checks were not executed locally; use the CI results and repeat them in your target environment before release.


## Phase 11 — Reports and archive

Phase 11 adds organization-scoped reporting and retention-aware order archiving.

### Reports

- `GET /api/v1/reports/summary` — operational metrics and permission-controlled financial summaries.
- `GET /api/v1/reports/orders` — import/export order register with partner and currency labels.
- `GET /api/v1/reports/partners` — customer/supplier order totals grouped by direction and currency; currencies are not combined.
- `GET /api/v1/reports/import-costs` — estimated and actual import landed-cost comparison using `Decimal`.
- `GET /api/v1/reports/shipment-performance` — shipment status, ETA/actual arrival and calculated days late.
- `GET /api/v1/reports/missing-documents` — required document records without a verified document, including order and shipment requirements.
- `GET /api/v1/reports/inventory` and `/inventory-movements` — current balances, low-stock rows, and the stock ledger.
- `GET /api/v1/reports/financial` — currency-separated receivables, payables and overdue balances; requires `reports.finance.read`.
- `GET /api/v1/reports/csv` — permission-controlled CSV exports for orders, inventory, stock movements, import costs, partners, shipment performance, missing documents, invoices and payments. Spreadsheet formula prefixes are escaped in text cells.

All report queries are organization-scoped and operational order/shipment reports exclude archived parent orders. Financial reports never aggregate different currencies as if they were equivalent.

### Archive

- `GET /api/v1/archive` — paginated search of archived import/export orders.
- `GET /api/v1/archive/eligible` — completed or cancelled orders eligible for archiving.
- `POST /api/v1/archive/{record_type}/{record_id}` — archive a received import, delivered export, or cancelled order with a required reason.
- `POST /api/v1/archive/{record_type}/{record_id}/restore` — restore an archived order with a required reason.
- `GET /api/v1/archive/{record_type}/{record_id}/history` — archive/restore audit events.

Archiving does not delete business records, shipment documents, invoices, payments, inventory ledger entries, or audit history. Archived records are excluded from operational lists and routine shipment/document/task/approval reminders. The application does not automatically purge archived records: permanent deletion and retention durations must be configured only after the organization has established its applicable legal and business retention policy.

### Migration

Phase 11 adds Alembic revision `0009_reports_archive`. Apply all migrations with:

```bash
docker compose exec backend alembic upgrade head
```

### Verification

Phase 11 backend tests cover report authorization, currency separation, CSV exports, import cost variance, partner summaries, shipment late-day calculations, missing order/shipment documents, archive/restore history, organization isolation, and reminder suppression for archived trade records.

## Phase 12 — Final testing and deployment preparation

Phase 12 adds release and operations hardening across the cumulative application:

- **Runtime configuration validation:** production mode now rejects insecure session cookies, local file storage, SQLite, missing PostgreSQL hosts, wildcard/HTTP CORS origins, and missing S3 bucket configuration.
- **HTTP hardening:** every response gets a validated `X-Request-ID`, `nosniff`, frame-denial, referrer, and permissions headers. API responses use `Cache-Control: no-store` because they contain organization-scoped business and financial data.
- **Ingress protection:** the unprivileged Nginx frontend container listens on port 8080, provides security headers and hashed-asset caching, and applies a basic IP-based request limit to authentication/invitation endpoints.
- **Automated CI:** `.github/workflows/ci.yml` checks Python compilation and tests, PostgreSQL 16 migration upgrade/drift, frontend TypeScript typecheck/unit tests/build, Docker Compose configuration/image builds, and a Playwright browser smoke journey.
- **Browser test:** `qa/e2e/test_workspace_smoke.py` creates an owner workspace, verifies the protected dashboard and primary navigation, then signs out.
- **Operations scripts:** `scripts/backup_postgres.sh`, `scripts/verify_backup.sh`, and `scripts/restore_postgres.sh` use PostgreSQL custom-format dumps. Restore requires `RESTORE_CONFIRM=YES` and stops the app/worker before changing database contents.
- **Preflight script:** `scripts/preflight.sh` runs Python compilation, backend tests, migration upgrade/drift/downgrade/re-upgrade, frontend checks, and Compose validation where available.
- **Version:** application/package version is set to `1.0.1` for this cumulative handoff.

See [`docs/phase12-final-testing-deployment.md`](docs/phase12-final-testing-deployment.md) for the release checklist and [`docs/functionality-user-guide.md`](docs/functionality-user-guide.md) for the names of all working modules and how to use them.

## Functionality user guide

The application uses the navigation groups **Workspace**, **Trade operations**, **Partners & stock**, **Logistics**, **Work management**, and **Finance & insights**. See [`docs/functionality-user-guide.md`](docs/functionality-user-guide.md) for the practical end-to-end import/export procedures, role notes, feature boundaries, and step-by-step use.

