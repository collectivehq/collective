#!/bin/sh
set -eu

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-collective.settings.production}"
PORT="${PORT:-8000}"
WORKERS="${GUNICORN_WORKERS:-3}"
TIMEOUT="${GUNICORN_TIMEOUT:-60}"

echo "[entrypoint] Applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] Starting Gunicorn on :${PORT}..."
exec gunicorn collective.wsgi:application \
	--bind "0.0.0.0:${PORT}" \
	--workers "${WORKERS}" \
	--timeout "${TIMEOUT}" \
	--access-logfile - \
	--error-logfile -
