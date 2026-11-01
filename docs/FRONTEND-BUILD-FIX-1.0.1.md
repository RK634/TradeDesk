# TradeDesk 1.0.1 — Frontend build fixes

This patch release fixes the frontend TypeScript/Vite errors reported while building the Phase 1–12 Docker images.

## Fixes included

- Removed unused imports that failed the strict `noUnusedLocals` TypeScript check.
- Renamed the import shipment milestone query variable to `milestonesQuery`, matching the component that reads its data and restoring inference for each milestone entry.
- Moved the upload helper text from the native `<input>` element to the surrounding `Field` component, which owns the `hint` property.
- Removed unused `organizationId` and undeclared `orderId` props from `ShipmentRow`.
- Added the missing React `useState` import in `NotificationsPage`.
- Removed the unused `ShipmentType` import from `ShipmentsPage`.
- Explicitly typed the dynamic Zod resolver bridge in `MasterDataPage` for React Hook Form.
- Imported `loadEnv` from `vite`; `vitest/config` supplies `defineConfig` and test config, but does not export `loadEnv`.

## Validation status

The reported compiler errors have been addressed in source. The patch environment could not complete `npm install` because the package registry request timed out, so a fresh `npm run typecheck` and `npm run build` could not be executed here. Rebuild the frontend Docker target on the development machine and share any remaining compiler output if it fails.

## Rebuild commands

From the project root:

```bash
docker compose build --no-cache frontend
docker compose up -d
```

If the frontend image builds successfully, continue with:

```bash
docker compose exec backend alembic upgrade head
docker compose ps
```
