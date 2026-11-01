# TradeDesk 1.0.2 — Public website and workspace guidance

## Public homepage (`/`)

The public homepage is now a product-information page rather than a developer environment/readiness screen. It explains what TradeDesk is for and includes:

- Product overview focused on managing trade from order to settlement.
- Feature descriptions for import/export orders, inventory, shipments/documents, finance, tasks/approvals, reports/archive.
- A five-step explanation of how a business gets started and uses the system.
- A concise description of organization access, inventory traceability, and private documents.
- Sign-in and workspace-registration calls to action.

The homepage no longer displays API documentation links, backend/database readiness status, environment connection checks, development phase labels, or statements that business workflows are still planned. The health endpoints remain available for operators and monitoring; they are simply not part of the public marketing page.

Authenticated users visiting `/` are redirected to `/app`. While authentication state is loading, a neutral loading state is displayed to prevent a public-page flash.

## Signed-in workspace (`/app`)

The dashboard no longer renders the development-oriented “Trade operations readiness” panel or phase badges. It now displays **How to use TradeDesk**, a six-step practical guide:

1. Set up the workspace: organization profile, team invitations, and access roles.
2. Add business records: customers, suppliers, products, and warehouse locations.
3. Create and manage an import: supplier, order lines, approval, shipment, and goods receipt. Confirmed receipts increase inventory and create movement history.
4. Prepare and deliver an export: customer, order lines, approval, stock reservation, dispatch, and delivery. Approval reserves stock; dispatch deducts on-hand stock; delivery does not deduct it again.
5. Manage shipments and documents: record milestones, upload files, and complete verification.
6. Invoice, reconcile, and review: issue invoices, record/allocate payments, and review currency-separated reports.

Each guide card explains both the action and what happens as a result, and links directly to the relevant application page. The guide appears once an organization is selected. Existing organization and trade KPI cards remain separate and continue to use backend-derived data.

## Navigation and page copy

- Removed the non-functional “All orders” sidebar placeholder that was marked with a development phase/lock.
- Sidebar items now require a real route; no locked phase placeholders are rendered.
- Removed development phase labels from import/export page headings.
- Replaced outdated organization-page copy that said business modules would arrive later.
- Updated the import cost panel copy to direct users to the existing Finance section for supplier invoices and payment reconciliation.

## Validation

- Added homepage tests for product content, absence of technical environment details, and redirect of authenticated users to `/app`.
- Updated dashboard tests to assert practical workflow guidance and absence of phase badges.
- Source search confirms there are no development phase labels or unavailable-phase placeholders in runtime frontend pages and layout.
- A fresh dependency-based `npm run build` and Vitest run should be executed in the user's Docker environment before replacing the currently working installation.
