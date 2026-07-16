#!/bin/sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"

docker compose -f "${COMPOSE_FILE}" build --pull web
docker compose -f "${COMPOSE_FILE}" up -d
docker compose -f "${COMPOSE_FILE}" exec -T web python manage.py check --deploy
docker compose -f "${COMPOSE_FILE}" ps

