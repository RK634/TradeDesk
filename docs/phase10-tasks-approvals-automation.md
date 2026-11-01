# Phase 10 — Tasks, approvals, notifications, and automation

## Scope delivered

Phase 10 completes the workflow-operations layer on top of the Phase 1–9 trade, shipment, document, inventory, and financial records.

### Tasks

- Organization-scoped task creation, listing, filtering, detail, editing, assignment, comments, and status transitions.
- Fields include title, description, assigned organization member, related trade record, priority, due date, status, creator, and timestamps.
- Statuses: `open`, `in_progress`, `blocked`, `completed`, and `cancelled`.
- Every status transition is written to task status history with actor, time, prior status, new status, and optional note.
- Assignment is validated against an active membership in the same organization.
- Assignment and comments can generate in-app notifications; a task cannot be retrieved or mutated outside its organization.

### Configurable approvals

- Organization owners and administrators can configure approval rules for import orders, export orders, invoices, payments, tasks, and custom actions.
- Rules configure enabled/disabled state, one or more permitted roles, optional minimum amount, and self-approval policy.
- Decision states are `submitted`, `approved`, `rejected`, `returned`, and `cancelled`.
- Rejection and return require a reason. Every decision records the acting user, timestamp, from/to state, and decision note.
- Import/export approvals are mirrored in the central approval inbox but must be decided through their domain-specific order endpoints. This preserves the inventory reservation/receipt safeguards already implemented in Phases 6 and 7.
- Generic approval requests can target invoices, payments, tasks, or a separately described custom action. Approval itself records a decision; it does not automatically post a payment, change stock, or execute another irreversible action.
- Approval authorization is enforced by the backend against the configured action-specific roles. Self-approval is rejected unless explicitly enabled.

### In-app notifications

- User-specific notification inbox with unread count, category filter, unread-only filter, mark-one-read, and mark-all-read.
- Per-user, per-organization category preferences for tasks, approvals, invoices, shipments, inventory, documents, orders, and system events.
- The API returns only notifications belonging to the authenticated user in the requested organization.
- Sidebar bell links to the inbox and displays the current unread count.

### Scheduled reminder automation

- A small standalone worker polls at a configurable interval. Celery/Redis are intentionally not introduced because the initial reminder checks are bounded database queries; this can be revisited if long-running jobs or higher throughput justify a queue.
- Reminder categories currently include:
  - Assigned tasks due within 24 hours or overdue.
  - Approval requests pending for at least 24 hours.
  - Issued invoices due within 7 days or overdue, only while an outstanding balance remains.
  - Import/export shipments with an ETA within 3 days, past ETA, or explicitly marked delayed.
  - Available inventory at or below the configured reorder threshold.
  - Trade documents expiring within 30 days or already expired.
  - Configured required documents with no verified, unexpired document attached.
- Each generated event has an organization-scoped deduplication key and an automation log entry. Failed delivery attempts are retried on later cycles with a maximum of five attempts. A processed `sent` or `skipped` event is not generated again for the same dedupe key.
- User category preferences are honored by the scheduler. A preference opt-out is stored per user and organization.
- The worker is a single Compose service by default. Unique database constraints protect deduplication, but production deployments that run multiple workers should still validate locking behavior against PostgreSQL.
- Manual runs are available only to organization owners and administrators and are scoped to the selected organization. The background worker runs across organizations by design.
- Automation only creates notifications and logs. It does not approve orders, post payments, dispatch goods, adjust inventory, or otherwise perform irreversible/financially consequential operations.

## Important endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/tasks` | Search and filter organization tasks |
| `POST` | `/api/v1/tasks` | Create a task |
| `GET` | `/api/v1/tasks/{task_id}` | Read task and activity history |
| `PATCH` | `/api/v1/tasks/{task_id}` | Update task details/assignment |
| `POST` | `/api/v1/tasks/{task_id}/status` | Record an allowed status transition |
| `POST` | `/api/v1/tasks/{task_id}/comments` | Add a comment |
| `GET` | `/api/v1/approval-rules` | Read effective approval rules |
| `PUT` | `/api/v1/approval-rules/{business_action}` | Configure an approval rule (owner/admin) |
| `GET` | `/api/v1/approvals` | List pending or historical approvals |
| `POST` | `/api/v1/approvals` | Submit a generic record/custom action for approval |
| `POST` | `/api/v1/approvals/{approval_id}/decision` | Approve, reject, or return (reason required for reject/return) |
| `POST` | `/api/v1/approvals/{approval_id}/cancel` | Cancel an eligible pending generic request |
| `GET` | `/api/v1/notifications` | List user notifications with filters |
| `GET` | `/api/v1/notifications/unread-count` | Read current unread count |
| `PATCH` | `/api/v1/notifications/{notification_id}/read` | Mark one notification read |
| `POST` | `/api/v1/notifications/read-all` | Mark all current-user notifications read |
| `GET/PUT` | `/api/v1/notifications/preferences` | Read/update notification preferences |
| `GET` | `/api/v1/notifications/automation-logs` | Read organization automation logs (owner/admin) |
| `POST` | `/api/v1/notifications/automation/run` | Trigger an organization-scoped reminder cycle (owner/admin) |

All mutating endpoints require an authenticated session and CSRF validation. Organization scoping and permission checks are enforced on the backend; frontend route visibility is not treated as a security boundary.

## Configuration and commands

```dotenv
AUTOMATION_ENABLED=true
AUTOMATION_POLL_SECONDS=60
```

- `AUTOMATION_ENABLED=false` pauses the background worker without disabling ordinary in-app notifications created by user actions.
- `AUTOMATION_POLL_SECONDS` must be between 15 and 3600 seconds.
- Run the worker once for troubleshooting:

```bash
cd backend
python -m app.worker --once
```

- Compose runs the scheduler as a separate `worker` service. View it with:

```bash
docker compose logs --tail=100 worker
```

## Database migration

Alembic revision `0008_tasks_approvals_automation` adds tasks, task comments/history, configurable approval rules, approval requests/events, notifications, notification preferences, and automation logs with organization-scoped foreign keys, unique dedupe constraints, indexes, and status/category constraints.

## Verification

- Backend API tests cover task lifecycle/history/comments, assignment and notification behavior, approval configuration and action-specific roles, decision audit history, rejection reason validation, read-only restrictions, organization isolation, automation deduplication, user preference opt-out, pending approval reminders, and upcoming shipment ETA reminders.
- The combined backend suite contains **59 passing tests**.
- The migration chain through `0008_tasks_approvals_automation` upgrades successfully against a temporary SQLite database and passes `alembic check` without schema drift. PostgreSQL locking and multi-worker contention still require runtime validation on PostgreSQL.
- Frontend TypeScript/TSX syntax is checked separately. A full frontend typecheck/build and browser tests require the pinned npm dependencies to be installed.

## Current limitations

- Notifications are in-app only. SMTP/email, SMS, push notifications, and external chat delivery are not configured.
- The scheduler is intentionally simple and database-backed. It does not use Celery/Redis, and it is not a general-purpose user-defined automation engine.
- Approval records for generic invoice/payment/task/custom actions record decisions but do not automatically execute the approved operation. Financial and stock operations remain in their respective business endpoints.
- Approval reminder cadence is one reminder per pending request after 24 hours; repeated reminders at daily intervals are not enabled.
- The worker must be monitored and backed by normal database backup/restore procedures in deployment.
