# TradeDesk 1.0.2 — Release notes

## Public website refresh

- Replaced the technical starter homepage with a public product page explaining TradeDesk, its business capabilities, how a business uses the system, and links to sign in or create a workspace.
- Removed public API documentation actions and live environment/database status cards from the homepage. Health endpoints remain available for operators.
- Authenticated users visiting `/` are redirected to their workspace.

## Workspace experience

- Removed the phase-oriented “Trade operations readiness” cards from the signed-in dashboard.
- Added a six-step “How to use TradeDesk” guide with descriptions of what to do, what happens next, and direct links to the relevant modules.
- Removed development phase labels from import/export page headings and removed the disabled “All orders” placeholder from the sidebar.
- Updated outdated copy that described implemented modules as future/planned work.

## Validation notes

The frontend source and tests were updated. Dependency installation in the patch environment timed out, so a fresh dependency-based production build and test run were not completed here. Run `npm install`, `npm run typecheck`, `npm run test -- --run`, and `npm run build` (or rebuild the frontend Docker image) before using this package as the active installation. No database schema or backend business behavior changed in this UI release.
