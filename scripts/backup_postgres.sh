#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="${1:-${BACKUP_DIR}/import_export_${TIMESTAMP}.dump}"

command -v docker >/dev/null 2>&1 || { echo "docker is required." >&2; exit 1; }
mkdir -p "$(dirname "${OUTPUT_FILE}")"
umask 077

# pg_dump runs inside the database container, so the database password is not
# exposed in shell arguments or written into a backup command line.
docker compose --project-directory "${ROOT_DIR}" -f "${ROOT_DIR}/docker-compose.yml" exec -T db sh -c \
  'pg_dump --format=custom --no-owner --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  > "${OUTPUT_FILE}"

if [[ ! -s "${OUTPUT_FILE}" ]]; then
  rm -f "${OUTPUT_FILE}"
  echo "Backup failed: output file is empty." >&2
  exit 1
fi
chmod 600 "${OUTPUT_FILE}"
printf 'Database backup created: %s\n' "${OUTPUT_FILE}"
