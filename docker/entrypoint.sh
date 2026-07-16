#!/bin/sh
set -eu

if [ "${MIGRATE_ON_STARTUP:-true}" = "true" ]; then
    python manage.py migrate --noinput
fi

python manage.py collectstatic --noinput

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --access-logfile - \
    --error-logfile -

