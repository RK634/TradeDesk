# Browser end-to-end tests

The Playwright smoke suite verifies a complete browser journey against a running application:

1. Open the registration page.
2. Create an organization owner account and organization.
3. Confirm the protected dashboard loads.
4. Confirm import, export, and reports navigation are available to the owner.
5. Sign out and confirm the login page is shown.

## Run locally

Start the application using the root README instructions, apply Alembic migrations, then run:

```bash
python -m pip install -r qa/requirements-e2e.txt
playwright install chromium
BASE_URL=http://127.0.0.1:8080 python -m pytest -q qa/e2e
```

The smoke test creates a unique organization and user on every run. Use a disposable development database; it does not clean up that account after execution.

For CI, Chromium is installed with OS dependencies and the Compose stack is created from scratch for the job.
