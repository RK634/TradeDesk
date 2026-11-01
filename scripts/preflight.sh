#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

printf '\n== Python compile ==\n'
python -m compileall -q "${BACKEND_DIR}/app"

printf '\n== Backend tests ==\n'
(cd "${BACKEND_DIR}" && pytest -q)

printf '\n== Migration upgrade, drift, and rollback/re-upgrade ==\n'
TEMP_DB="$(mktemp /tmp/iem-release-XXXXXX.db)"
rm -f "${TEMP_DB}"
cleanup() { rm -f "${TEMP_DB}"; }
trap cleanup EXIT
(
  cd "${BACKEND_DIR}"
  export DATABASE_URL="sqlite:///${TEMP_DB}"
  alembic upgrade head
  alembic check
  alembic downgrade -1
  alembic upgrade head
)

printf '\n== Frontend checks ==\n'
if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo "Frontend dependencies are not installed. Run: cd frontend && npm install" >&2
  exit 3
fi
(cd "${FRONTEND_DIR}" && npm run typecheck && npm run test -- --run && npm run build)

printf '\n== Docker Compose configuration ==\n'
if command -v docker >/dev/null 2>&1; then
  (cd "${ROOT_DIR}" && docker compose config --quiet)
else
  echo "Docker not installed; Compose validation skipped." >&2
fi

printf '\nPreflight checks completed.\n'
