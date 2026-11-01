#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_FILE="${1:-}"
if [[ -z "${BACKUP_FILE}" || ! -f "${BACKUP_FILE}" ]]; then
  echo "Usage: $0 path/to/database.dump" >&2
  exit 2
fi
command -v docker >/dev/null 2>&1 || { echo "docker is required." >&2; exit 1; }
docker compose --project-directory "${ROOT_DIR}" -f "${ROOT_DIR}/docker-compose.yml" exec -T db pg_restore --list < "${BACKUP_FILE}" >/dev/null
printf 'Backup archive format is readable: %s\n' "${BACKUP_FILE}"
