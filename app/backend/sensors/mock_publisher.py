"""Mock air-quality sensor publisher.

Simulates one or more rooms of home air-quality sensors by publishing realistic,
drifting readings to the MQTT broker on the same topics real hardware would use
(home/<room>/airquality). Run it alongside the app to exercise the full pipeline
without any physical sensors:

    python -m sensors.mock_publisher

Configure via env: MQTT_HOST, MQTT_PORT, MOCK_INTERVAL (seconds), MOCK_ROOMS.
"""
import json
import logging
import os
import random
import ssl
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() == "true"
MQTT_CA_CERT = os.environ.get("MQTT_CA_CERT")
MQTT_USERNAME = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
INTERVAL = int(os.environ.get("MOCK_INTERVAL", "5"))
ROOMS = [r.strip() for r in os.environ.get("MOCK_ROOMS", "living_room,bedroom,office").split(",") if r.strip()]

logging.basicConfig(level=logging.INFO)


def clamp(value, low, high):
    return max(low, min(high, value))


class RoomState:
    """Holds a room's current readings and advances them with a random walk."""

    def __init__(self, room):
        self.room = room
        self.co2 = random.uniform(450, 600)
        self.pm25 = random.uniform(5, 15)
        self.voc = random.uniform(80, 150)
        self.temperature = random.uniform(20, 22)
        self.humidity = random.uniform(40, 55)
        self.occupied = False

    def step(self):
        # Occupancy flips occasionally; occupied rooms accumulate CO2, empty ones vent.
        if random.random() < 0.1:
            self.occupied = not self.occupied
        co2_drift = random.uniform(15, 40) if self.occupied else -random.uniform(10, 30)
        self.co2 = clamp(self.co2 + co2_drift, 400, 2200)
        self.pm25 = clamp(self.pm25 + random.uniform(-2, 2), 0, 120)
        self.voc = clamp(self.voc + random.uniform(-15, 20), 50, 600)
        self.temperature = clamp(self.temperature + random.uniform(-0.2, 0.2), 16, 28)
        self.humidity = clamp(self.humidity + random.uniform(-1, 1), 25, 70)
        return {
            "room": self.room,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "co2": round(self.co2, 1),
            "pm25": round(self.pm25, 1),
            "voc": round(self.voc, 1),
            "temperature": round(self.temperature, 1),
            "humidity": round(self.humidity, 1),
        }


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set(ca_certs=MQTT_CA_CERT, cert_reqs=ssl.CERT_REQUIRED)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    states = [RoomState(room) for room in ROOMS]
    logging.info(
        "mock publisher: %d room(s) -> %s:%s every %ss", len(states), MQTT_HOST, MQTT_PORT, INTERVAL
    )
    try:
        while True:
            for state in states:
                payload = state.step()
                topic = f"home/{state.room}/airquality"
                client.publish(topic, json.dumps(payload))
                logging.info("published %s co2=%s pm25=%s", topic, payload["co2"], payload["pm25"])
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logging.info("mock publisher stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
