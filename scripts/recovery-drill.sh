#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 BACKUP_DIRECTORY" >&2
    exit 2
fi

BACKUP_DIRECTORY="$1"
COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env}"
DRILL_ID="$(date -u +%Y%m%d%H%M%S)-$$"
DRILL_PROJECT="rwl_recovery_${DRILL_ID}"
RECOVERY_REPORT="${RECOVERY_REPORT:-./backups/recovery-drill-${DRILL_ID}.txt}"

case "${DRILL_PROJECT}" in
    rwl_recovery_*) ;;
    *) echo "Unsafe recovery project name." >&2; exit 2 ;;
esac

compose() {
    COMPOSE_PROJECT_NAME="${DRILL_PROJECT}" \
        docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

cleanup() {
    if [ "${KEEP_RECOVERY_ENV:-false}" != "true" ]; then
        compose down -v --remove-orphans >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$(dirname "${RECOVERY_REPORT}")"
compose config --quiet

COMPOSE_PROJECT_NAME="${DRILL_PROJECT}" \
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE}" \
COMPOSE_FILE="${COMPOSE_FILE}" \
RESTORE_START_CADDY=false \
ALLOW_CROSS_PROJECT_RESTORE=true \
    ./scripts/restore.sh "${BACKUP_DIRECTORY}" --yes "${DRILL_PROJECT}"

MIGRATION_COUNT="$(compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM django_migrations"' | tr -d '\r')"
USER_COUNT="$(compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM auth_user"' | tr -d '\r')"
compose exec -T web python manage.py check
compose exec -T web python manage.py check_storage --minimum-free-mb 1 --json

{
    echo "recovery_drill=${DRILL_ID}"
    echo "status=passed"
    echo "backup=${BACKUP_DIRECTORY}"
    echo "isolated_project=${DRILL_PROJECT}"
    echo "migration_rows=${MIGRATION_COUNT}"
    echo "user_rows=${USER_COUNT}"
    echo "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${RECOVERY_REPORT}"

echo "Recovery drill passed; report written to ${RECOVERY_REPORT}"
