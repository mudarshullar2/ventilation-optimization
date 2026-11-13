#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# load .env (POSTGRES_*, MQTT_*_PASSWORD, FLASK_SECRET_KEY, COOKIE_SECURE)
set -a; [ -f ../.env ] && . ../.env; set +a
: "${FLASK_SECRET_KEY:?set FLASK_SECRET_KEY in .env}"
export COOKIE_SECURE="${COOKIE_SECURE:-true}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
# MQTT identity for the backend
export MQTT_USERNAME="${MQTT_USERNAME:-app}"
export MQTT_PASSWORD="${MQTT_PASSWORD:-${MQTT_APP_PASSWORD:-}}"
exec gunicorn -w "${WEB_WORKERS:-4}" --threads "${WEB_THREADS:-2}" -b 127.0.0.1:8000 application:app
