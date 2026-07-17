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

if compose config --images | grep -Eq '(^|:)latest$'; then
    echo "Set WEB_IMAGE to an immutable release tag or digest, not latest." >&2
    exit 2
fi

compose config --quiet
compose build --pull web
compose up -d
compose exec -T web python manage.py check --deploy
compose exec -T web python manage.py check_storage --json
compose ps
