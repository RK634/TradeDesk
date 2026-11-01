# TradeDesk 1.0.1 — Release notes

This cumulative package brings together Phases 1–12 of the Importer & Exporter Management System.

## Included capabilities

- Organization-aware accounts, cookie sessions, CSRF checks, and seven role profiles.
- Dashboard, customers, suppliers, products, locations, stock balances, and inventory ledger.
- Import orders, approvals, shipments, partial goods receipts, and transactional stock receipt posting.
- Export orders, stock reservation, partial dispatch, delivery tracking, and idempotent stock deduction.
- Private trade documents, immutable versions, configured requirements, and verification history.
- Unified shipment timelines and delay tracking using manually entered events.
- Supplier/customer invoices, partial payments, allocations, currency snapshots, reversals, and financial audit history.
- Tasks, comments, task status history, configurable approvals, in-app notifications, and scheduled reminder worker.
- Reports, CSV downloads, archived order search, restore, and archive audit history.
- Release CI, a Playwright browser smoke test, runtime configuration validation, backup/restore scripts, and release documentation.

## Database

The final Alembic head is `0009_reports_archive`. Phase 12 does not add a database schema revision. Always run `alembic upgrade head` as part of release deployment and validate backups before migrating production.

## Verification summary for this package

- 83 backend tests passed in the provided execution environment.
- Full migration upgrade/drift/downgrade/re-upgrade passed on a temporary SQLite test database.
- 62 TypeScript/TSX source files (excluding declaration files) passed syntax transpilation with no diagnostics. A fresh dependency-based typecheck and Vite production build could not be executed in this patch environment because npm package installation timed out; the original Docker build errors are addressed in `docs/FRONTEND-BUILD-FIX-1.0.1.md` and must be rechecked locally.
- Docker/PostgreSQL container build/runtime and the browser E2E test are configured in CI but were not executed in the provided environment.

## Known integrations not included

SMTP/email, password recovery, email verification, live carrier tracking, antivirus scanning, external banking/payment gateway, live FX rates, customs filing, and automatic legal-retention deletion are not included. See `docs/functionality-user-guide.md` and `docs/phase12-final-testing-deployment.md`.
