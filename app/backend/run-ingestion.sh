#!/usr/bin/env bash
# Launches the MQTT ingestion worker (subscribes + persists). Run alongside run.sh.
set -euo pipefail
cd "$(dirname "$0")"
set -a; [ -f ../.env ] && . ../.env; set +a
export MQTT_USERNAME="${MQTT_USERNAME:-app}"
export MQTT_PASSWORD="${MQTT_PASSWORD:-${MQTT_APP_PASSWORD:-}}"
exec python -m ingestion.worker
