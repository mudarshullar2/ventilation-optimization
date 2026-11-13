"""MQTT ingestion for home air-quality readings.

Subscribes to the broker and turns incoming JSON payloads into SensorReadings,
keeping the latest reading per room in memory (for the dashboard / API) and
persisting every reading to the database.

Broker settings come from the environment so the same code points at a local
Mosquitto broker in development and at the real broker in production:

    MQTT_HOST (default localhost)
    MQTT_PORT (default 1883)
    MQTT_TLS  (default false)
    MQTT_USERNAME / MQTT_PASSWORD (optional)
    MQTT_TOPIC (default home/+/airquality)
"""
import json
import logging
import os
import ssl

import paho.mqtt.client as mqtt

from sensors.models import SensorReading
from database.db import Database

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() == "true"
MQTT_USERNAME = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "home/+/airquality")


class MQTTClient:
    def __init__(self, db=None):
        self.latest = {}  # room -> latest reading dict
        self.db = db if db is not None else Database()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        if MQTT_TLS:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, reason_code, properties):
        logging.info("MQTT connected (%s); subscribing to %s", reason_code, MQTT_TOPIC)
        self.client.subscribe(MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            reading = SensorReading.from_payload(payload)
            self.latest[reading.room] = reading.to_dict()
            self.db.insert_reading(reading)
            logging.info("reading stored: room=%s co2=%s", reading.room, reading.co2)
        except Exception as e:
            logging.error("on_message: failed to handle message on %s: %s", msg.topic, e)

    def initialize(self):
        try:
            self.client.connect(MQTT_HOST, MQTT_PORT)
            self.client.loop_start()
            logging.info("MQTT client started (%s:%s)", MQTT_HOST, MQTT_PORT)
        except Exception as e:
            logging.error(
                "initialize: could not connect to broker %s:%s: %s", MQTT_HOST, MQTT_PORT, e
            )

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logging.error("stop: error stopping the client: %s", e)
