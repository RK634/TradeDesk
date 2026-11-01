# Phase 12 — Final testing and deployment preparation

## Purpose

Phase 12 adds a repeatable release process and security/operations baseline across the cumulative Phase 1–11 application. It does not introduce another business module or database migration.

## Code delivered

### Runtime configuration guardrails

`backend/app/core/config.py` now:

- Normalizes and validates `APP_ENV` (`development`, `test`, `staging`, `production`).
- Requires a secure session cookie in production.
- Requires private S3-compatible storage and a configured bucket in production.
- Requires a PostgreSQL URL with a configured host in production; SQLite remains available for tests/development only.
- Requires explicit HTTPS CORS origins in production and rejects wildcard/HTTP origins.

The validator intentionally does not require static AWS credentials. A deployment can use workload identity/instance roles instead.

### HTTP response hardening

`backend/app/main.py` now attaches:

- A validated incoming `X-Request-ID` or a server-generated UUID.
- `X-Content-Type-Options: nosniff`.
- `X-Frame-Options: DENY`.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- A restrictive `Permissions-Policy` for camera, microphone, and geolocation.
- `Cache-Control: no-store` for `/api/*` responses.

The application does not set HSTS itself because TLS is expected to terminate at the trusted deployment ingress. Set HSTS at that HTTPS ingress after confirming all traffic is HTTPS.

### Nginx and containers

- The frontend runtime uses the unprivileged Nginx image and listens on container port `8080`.
- The Compose host binding remains loopback-only (`127.0.0.1:8080`).
- Nginx adds common security headers, disables server tokens, caches fingerprinted static files, and revalidates `index.html`.
- Nginx applies a basic per-client request limit to login, registration, invitation acceptance, and invitation preview. This protects the bundled single ingress. When placed behind another proxy, configure trusted client-IP forwarding; for multiple replicas use a shared ingress/WAF rate limiter.
- Backend and worker use the same production settings so the worker cannot silently fall back to development storage/configuration.

### Continuous integration

`.github/workflows/ci.yml` includes four jobs:

1. Backend: Python 3.12, compilation, pytest, PostgreSQL 16 migration upgrade, and Alembic metadata drift check.
2. Frontend: npm dependency installation, strict TypeScript typecheck, Vitest, and production build.
3. Containers: Docker Compose configuration validation and frontend/backend image builds.
4. Browser E2E: start the Compose stack, apply migrations, then use Playwright to register an owner, open the protected dashboard, verify navigation, and sign out.

`.github/dependabot.yml` checks Python, npm, Docker, and GitHub Actions dependencies weekly.

### Backup, restore, and release preflight

Scripts in `scripts/`:

- `preflight.sh` runs backend compilation/tests, a temporary migration upgrade/drift/downgrade/re-upgrade cycle, frontend typecheck/tests/build, and Compose validation when Docker is installed.
- `backup_postgres.sh [optional-output-file]` produces a PostgreSQL custom-format dump with restrictive local file permissions.
- `verify_backup.sh path/to/file.dump` checks that PostgreSQL can read the dump archive.
- `restore_postgres.sh path/to/file.dump` stops backend/worker writers and restores the dump. It refuses to proceed unless `RESTORE_CONFIRM=YES` is explicitly set.

The backup scripts do not encrypt, upload off-host, or rotate backups. Production backups must be encrypted, access-controlled, copied to a separate failure domain, monitored, and retained according to the organization's approved policy. Perform periodic restore drills in a separate environment.

## Local release checks

Copy and configure the root environment template:

```bash
cp .env.example .env
```

Install Python requirements and run backend/migration checks:

```bash
python -m pip install -r backend/requirements.txt
cd backend
pytest -q
DATABASE_URL=sqlite:////tmp/iem-migration-check.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/iem-migration-check.db alembic check
cd ..
```

Install frontend dependencies and run the full frontend checks:

```bash
cd frontend
npm install
npm run typecheck
npm run test -- --run
npm run build
cd ..
```

Then run Docker validation/runtime checks:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose exec backend alembic upgrade head
curl --fail http://127.0.0.1:8000/api/v1/health/ready
curl --fail http://127.0.0.1:8080/
```

Run the browser smoke test after the stack is available:

```bash
python -m pip install -r qa/requirements-e2e.txt
playwright install chromium
BASE_URL=http://127.0.0.1:8080 python -m pytest -q qa/e2e
```

Or run `scripts/preflight.sh` after installing all local dependencies.

## Production checklist

Before production deployment:

- Set `APP_ENV=production` and `SESSION_COOKIE_SECURE=true`.
- Use a PostgreSQL URL and a private S3-compatible bucket; never use local uploads as production storage.
- Set `CORS_ORIGINS` to exact HTTPS frontend origins, without wildcards.
- Use long randomly generated credentials from a secrets manager. For the Compose-generated Postgres URL, use URL-safe database passwords (for example, hexadecimal generated secrets) or provide a safely URL-encoded `DATABASE_URL` through your deployment platform.
- Terminate HTTPS at a trusted reverse proxy/load balancer, enable HSTS there, and restrict direct access to the backend/database ports.
- Set `ALLOW_SELF_REGISTRATION=false` when organization onboarding should be invitation/admin controlled.
- Configure trusted proxy IP handling before using client-IP based ingress rate limits behind another proxy.
- Configure SMTP and account recovery only after choosing a provider and validating the complete email lifecycle; those features are not included yet.
- Configure centralized logs, metrics, alerting, database monitoring, S3 lifecycle/versioning, backup encryption, and recovery objectives.
- Test backup restoration, role permissions, tenant isolation, concurrent stock posting, payment idempotency, and the exact target Postgres version before onboarding customers.
- Have security, privacy, legal, and customs compliance requirements reviewed for the actual countries/commodities/retention rules in scope.

## Verification record for this delivery

- Backend API/unit tests: 83 passed in the provided execution environment.
- Alembic: full upgrade to `0009_reports_archive`, no schema drift, one-revision downgrade, and upgrade back passed on a temporary SQLite database.
- Python compileall: passed.
- Frontend TypeScript/TSX source syntax transpilation: 61 files checked with no syntax diagnostics. This is not a substitute for semantic TypeScript typechecking or Vite build.
- `npm run typecheck` was attempted and stopped because `vite/client` is unavailable; `frontend/node_modules` is not installed in the provided environment. Frontend unit tests and the production build were not run locally.
- Docker is unavailable in the provided environment, so Compose image builds and PostgreSQL container runtime checks were not run locally. YAML parsing and shell-script syntax checks passed.
- Playwright source and CI execution are included, but Chromium is not installed in the provided environment, so the browser test was not run locally.

A green SQLite test suite alone is not a production certification. The PostgreSQL CI and target-environment deployment checklist must pass before release.
