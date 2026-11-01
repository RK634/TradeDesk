# Phase 4 — Application Shell and Dashboard

> Historical phase note: Phase 5 has since implemented master data and basic inventory. Inventory is now marked available in the dashboard capability metadata; import/export, shipment, document, and finance workflows remain unavailable.

## Included

- Responsive application shell with a collapsible mobile sidebar, top navigation, organization selector, navigation search, current user display, and sign-out action.
- Protected nested routes at `/app` and `/app/organization`.
- Clear, disabled navigation items for modules that are scheduled for later phases; unavailable modules are not presented as working routes.
- Organization-scoped dashboard API at `GET /api/v1/dashboard/summary`.
- Dashboard KPIs computed from persisted organization memberships and invitation records: total/active/inactive members, new members within the selected date range, and pending invitations for roles allowed to view invitations.
- Workspace charts for member joins over time and active members by role. They display the API response, not client-side sample metrics.
- Loading, retryable error, no-organization, and empty-role-chart states.
- Explicit operational-readiness metadata for imports, exports, inventory, shipments, documents, invoices, and payments. These entries describe planned capabilities; they are not fabricated business counts.
- Backend tests for real membership aggregates, session requirement, cross-organization denial, reversed date ranges, and maximum date-range size.

## Dashboard API

`GET /api/v1/dashboard/summary?organization_id=<uuid>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

`organization_id` is required. `start_date` and `end_date` are optional; the default period is the last 30 calendar days ending today in UTC. The period can be up to 366 days. A reversed or excessively long range returns HTTP 422.

The backend verifies the current user's active organization membership and `organization.read` permission for every request. A non-member receives the same 404 response used for an inaccessible organization. Invitation counts are only included for roles that hold the `members.invite` permission.

## Current boundaries

This phase does not implement import/export orders, inventory, shipment, document, or finance records. Their dashboard values are therefore intentionally unavailable instead of displayed as fabricated zeroes. Their metrics should be connected as the corresponding feature phases add real source tables and services.

The notification button and not-yet-implemented sidebar destinations are visibly disabled and identified as planned work. The navigation search filters visible navigation entries; it is not a cross-record business search.

## Verification

Backend verification executed in this environment: `pytest -q` — 21 tests passed. Frontend dependencies could not be installed because npm registry access timed out, so a full TypeScript typecheck, Vitest suite, and Vite production build remain to be run on a machine with npm registry access. Docker/PostgreSQL runtime verification was not performed in this environment.
