#!/usr/bin/env bash
# Generate the Mosquitto password file (hashed) for the three identities.
# Passwords come from the environment so they are never written in the repo.
#   MQTT_APP_PASSWORD=... MQTT_SENSOR_PASSWORD=... MQTT_TRV_PASSWORD=... ./setup-auth.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${MQTT_APP_PASSWORD:?set MQTT_APP_PASSWORD}"
: "${MQTT_SENSOR_PASSWORD:?set MQTT_SENSOR_PASSWORD}"
: "${MQTT_TRV_PASSWORD:?set MQTT_TRV_PASSWORD}"

docker run --rm -v "$PWD:/work" eclipse-mosquitto:2 sh -c "
  mosquitto_passwd -c -b /work/passwd app    '$MQTT_APP_PASSWORD' &&
  mosquitto_passwd      -b /work/passwd sensor '$MQTT_SENSOR_PASSWORD' &&
  mosquitto_passwd      -b /work/passwd trv    '$MQTT_TRV_PASSWORD'
"
echo "wrote mosquitto/passwd (app, sensor, trv)"
