#!/bin/sh
set -eu

if [ "$#" -ne 3 ] || { [ "$2" != "--yes" ] && [ "$2" != "--dry-run" ]; }; then
    echo "Usage: $0 BACKUP_DIRECTORY (--dry-run|--yes) COMPOSE_PROJECT_NAME" >&2
    exit 2
fi

COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
RESTORE_START_CADDY="${RESTORE_START_CADDY:-true}"
SOURCE="$1"
ACTION="$2"
CONFIRMED_PROJECT="$3"
CURRENT_PROJECT="${COMPOSE_PROJECT_NAME:-}"

if [ -z "${CURRENT_PROJECT}" ] || [ "${CURRENT_PROJECT}" != "${CONFIRMED_PROJECT}" ]; then
    echo "Restore target mismatch: export COMPOSE_PROJECT_NAME and repeat it as the third argument." >&2
    exit 2
fi

case "${CONFIRMED_PROJECT}" in
    *[!A-Za-z0-9_-]*|"") echo "Unsafe Compose project name." >&2; exit 2 ;;
esac

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

MANIFEST_DATABASE="$(sed -n 's/^database=//p' "${SOURCE}/manifest.txt" | head -n 1)"
MANIFEST_PROJECT="$(sed -n 's/^compose_project=//p' "${SOURCE}/manifest.txt" | head -n 1)"
FORMAT_VERSION="$(sed -n 's/^format_version=//p' "${SOURCE}/manifest.txt" | head -n 1)"
if [ "${FORMAT_VERSION}" != "2" ] || [ -z "${MANIFEST_DATABASE}" ] || [ -z "${MANIFEST_PROJECT}" ]; then
    echo "Backup manifest is not a V1 format-2 backup with project/database identity." >&2
    exit 1
fi
if [ "${MANIFEST_PROJECT}" != "${CONFIRMED_PROJECT}" ] \
    && [ "${ALLOW_CROSS_PROJECT_RESTORE:-false}" != "true" ]; then
    echo "Backup project ${MANIFEST_PROJECT} does not match target ${CONFIRMED_PROJECT}." >&2
    echo "Use the isolated recovery drill for cross-project verification." >&2
    exit 1
fi

if [ "${ACTION}" = "--dry-run" ]; then
    echo "Restore preflight passed for project ${CONFIRMED_PROJECT}; backup project ${MANIFEST_PROJECT}; database ${MANIFEST_DATABASE}."
    exit 0
fi

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

TARGET_DATABASE="$(compose exec -T db printenv POSTGRES_DB | tr -d '\r')"
if [ "${TARGET_DATABASE}" != "${MANIFEST_DATABASE}" ]; then
    echo "Backup database ${MANIFEST_DATABASE} does not match target ${TARGET_DATABASE}." >&2
    exit 1
fi

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
