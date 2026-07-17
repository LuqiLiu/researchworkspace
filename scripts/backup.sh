#!/bin/sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
DAILY_RETENTION="${DAILY_RETENTION:-7}"
WEEKLY_RETENTION="${WEEKLY_RETENTION:-4}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WEEK_KEY="$(date -u +%G-W%V)"

case "${BACKUP_ROOT}" in
    ""|/|.) echo "Unsafe BACKUP_ROOT: ${BACKUP_ROOT}" >&2; exit 2 ;;
esac

compose() {
    if [ -n "${COMPOSE_ENV_FILE}" ]; then
        docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
    else
        docker compose -f "${COMPOSE_FILE}" "$@"
    fi
}

DAILY_ROOT="${BACKUP_ROOT}/daily"
WEEKLY_ROOT="${BACKUP_ROOT}/weekly"
DESTINATION="${DAILY_ROOT}/${TIMESTAMP}"
WORKING="${DESTINATION}.partial.$$"

umask 077
mkdir -p "${DAILY_ROOT}" "${WEEKLY_ROOT}" "${WORKING}"
trap 'rm -rf -- "${WORKING}"' EXIT HUP INT TERM

compose exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    > "${WORKING}/database.sql"
gzip "${WORKING}/database.sql"

compose exec -T web \
    tar -cf - -C /app/var/media . \
    > "${WORKING}/media.tar"
gzip "${WORKING}/media.tar"

gzip -t "${WORKING}/database.sql.gz"
gzip -t "${WORKING}/media.tar.gz"

DATABASE_NAME="$(compose exec -T db printenv POSTGRES_DB | tr -d '\r')"
PROJECT_NAME="$(compose config | sed -n 's/^name: //p' | head -n 1)"
GIT_REVISION="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
{
    echo "format_version=2"
    echo "created_at=${TIMESTAMP}"
    echo "compose_project=${PROJECT_NAME}"
    echo "compose_file=${COMPOSE_FILE}"
    echo "database=${DATABASE_NAME}"
    echo "git_revision=${GIT_REVISION}"
} > "${WORKING}/manifest.txt"

(
    cd "${WORKING}"
    sha256sum database.sql.gz media.tar.gz manifest.txt > SHA256SUMS
)

mv "${WORKING}" "${DESTINATION}"
trap - EXIT HUP INT TERM

if [ ! -e "${WEEKLY_ROOT}/${WEEK_KEY}" ]; then
    cp -al "${DESTINATION}" "${WEEKLY_ROOT}/${WEEK_KEY}"
fi

prune_backups() {
    directory="$1"
    keep="$2"
    find "${directory}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' \
        | sort -r \
        | awk -v keep="${keep}" 'NR > keep' \
        | while IFS= read -r entry; do
            [ -n "${entry}" ] || continue
            case "${entry}" in
                *[!A-Za-z0-9TWZ-]*) echo "Skipping unsafe retention entry: ${entry}" >&2 ;;
                *) rm -rf -- "${directory}/${entry}" ;;
            esac
        done
}

prune_backups "${DAILY_ROOT}" "${DAILY_RETENTION}"
prune_backups "${WEEKLY_ROOT}" "${WEEKLY_RETENTION}"

compose exec -T web python manage.py record_system_event \
    BACKUP_CREATED --detail "${TIMESTAMP}" >/dev/null \
    || echo "Warning: backup succeeded but audit event could not be recorded." >&2

echo "Backup created and verified at ${DESTINATION}"
