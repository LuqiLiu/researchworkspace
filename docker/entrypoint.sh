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
    --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
    --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" \
    --worker-tmp-dir /tmp \
    --access-logfile - \
    --error-logfile -
