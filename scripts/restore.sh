#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$2" != "--yes" ]; then
    echo "Usage: $0 BACKUP_DIRECTORY --yes" >&2
    exit 2
fi

COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
SOURCE="$1"

test -f "${SOURCE}/database.sql.gz"
test -f "${SOURCE}/media.tar.gz"

docker compose -f "${COMPOSE_FILE}" up -d db web

docker compose -f "${COMPOSE_FILE}" exec -T db \
    sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'

gzip -dc "${SOURCE}/database.sql.gz" \
    | docker compose -f "${COMPOSE_FILE}" exec -T db \
        sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'

docker compose -f "${COMPOSE_FILE}" exec -T web \
    sh -c 'find /app/var/media -mindepth 1 -delete'

gzip -dc "${SOURCE}/media.tar.gz" \
    | docker compose -f "${COMPOSE_FILE}" exec -T web \
        tar -xf - -C /app/var/media

docker compose -f "${COMPOSE_FILE}" exec -T web python manage.py migrate --noinput
echo "Restore completed from ${SOURCE}"
