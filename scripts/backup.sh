#!/bin/sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DESTINATION="${BACKUP_ROOT}/${TIMESTAMP}"

umask 077
mkdir -p "${DESTINATION}"

docker compose -f "${COMPOSE_FILE}" exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    | gzip > "${DESTINATION}/database.sql.gz"

docker compose -f "${COMPOSE_FILE}" exec -T web \
    tar -czf - -C /app/var/media . \
    > "${DESTINATION}/media.tar.gz"

{
    echo "created_at=${TIMESTAMP}"
    echo "compose_file=${COMPOSE_FILE}"
    echo "database=$(docker compose -f "${COMPOSE_FILE}" exec -T db printenv POSTGRES_DB | tr -d '\r')"
} > "${DESTINATION}/manifest.txt"

echo "Backup created at ${DESTINATION}"
