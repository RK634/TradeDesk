#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_FILE="${1:-}"

if [[ -z "${BACKUP_FILE}" || ! -f "${BACKUP_FILE}" ]]; then
  echo "Usage: $0 path/to/database.dump" >&2
  exit 2
fi
if [[ "${RESTORE_CONFIRM:-}" != "YES" ]]; then
  echo "Restore is destructive. It replaces the current database contents." >&2
  echo "Create and verify a fresh backup first, then rerun with RESTORE_CONFIRM=YES." >&2
  exit 2
fi
command -v docker >/dev/null 2>&1 || { echo "docker is required." >&2; exit 1; }

# Stop writers before replacing database objects. Keep PostgreSQL running.
docker compose --project-directory "${ROOT_DIR}" -f "${ROOT_DIR}/docker-compose.yml" stop backend worker

docker compose --project-directory "${ROOT_DIR}" -f "${ROOT_DIR}/docker-compose.yml" exec -T db sh -c \
  'pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  < "${BACKUP_FILE}"

printf 'Restore completed from: %s\n' "${BACKUP_FILE}"
printf 'Run migrations/checks before restarting the application.\n'
