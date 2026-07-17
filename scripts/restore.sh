#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$2" != "--yes" ]; then
    echo "Usage: $0 BACKUP_DIRECTORY --yes" >&2
    exit 2
fi

COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
RESTORE_START_CADDY="${RESTORE_START_CADDY:-true}"
SOURCE="$1"

compose() {
    if [ -n "${COMPOSE_ENV_FILE}" ]; then
        docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
    else
        docker compose -f "${COMPOSE_FILE}" "$@"
    fi
}

test -f "${SOURCE}/database.sql.gz"
test -f "${SOURCE}/media.tar.gz"
test -f "${SOURCE}/manifest.txt"
test -f "${SOURCE}/SHA256SUMS"

(
    cd "${SOURCE}"
    sha256sum -c SHA256SUMS
)
gzip -t "${SOURCE}/database.sql.gz"
gzip -t "${SOURCE}/media.tar.gz"

compose stop caddy web >/dev/null 2>&1 || true
compose up -d db

attempt=0
until compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "${attempt}" -ge 30 ]; then
        echo "Database did not become ready for restore." >&2
        exit 1
    fi
    sleep 2
done

compose exec -T db \
    sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'

gzip -dc "${SOURCE}/database.sql.gz" \
    | compose exec -T db \
        sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'

compose run --rm --no-deps -T --entrypoint sh web \
    -c 'find /app/var/media -mindepth 1 -delete'

gzip -dc "${SOURCE}/media.tar.gz" \
    | compose run --rm --no-deps -T --entrypoint tar web \
        -xf - -C /app/var/media

compose up -d web

attempt=0
until compose exec -T web python manage.py check >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "${attempt}" -ge 30 ]; then
        echo "Web service did not become ready after restore." >&2
        exit 1
    fi
    sleep 2
done

compose exec -T web python manage.py record_system_event \
    RESTORE_COMPLETED --detail "$(basename "${SOURCE}")" >/dev/null

if [ "${RESTORE_START_CADDY}" = "true" ]; then
    compose up -d caddy
fi

echo "Restore completed and verified from ${SOURCE}"
