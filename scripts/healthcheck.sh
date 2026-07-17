#!/bin/sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"

compose() {
    if [ -n "${COMPOSE_ENV_FILE}" ]; then
        docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
    else
        docker compose -f "${COMPOSE_FILE}" "$@"
    fi
}

compose exec -T web python manage.py check
compose exec -T web python manage.py check_storage --json
compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
compose ps
