"""MQTT ingestion and control for the home system.

Subscribes to the broker for both air-quality readings and radiator state,
keeps the latest of each per room in memory (for the dashboard / API), persists
them, and can publish radiator set-commands.

Broker settings come from the environment so the same code points at a local
Mosquitto broker in development and at the real broker in production:

    MQTT_HOST (default localhost)
    MQTT_PORT (default 1883)
    MQTT_TLS  (default false)
    MQTT_USERNAME / MQTT_PASSWORD (optional)
    MQTT_TOPIC          (air-quality subscribe, default home/+/airquality)
    MQTT_RADIATOR_TOPIC (radiator state subscribe, default home/+/radiator/state)
"""
import json
import logging
import os
import ssl

import paho.mqtt.client as mqtt

from sensors.models import SensorReading
from control.models import RadiatorState
from database.db import Database

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() == "true"
MQTT_CA_CERT = os.environ.get("MQTT_CA_CERT")  # path to CA cert for TLS verification
MQTT_USERNAME = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "home/+/airquality")
MQTT_RADIATOR_TOPIC = os.environ.get("MQTT_RADIATOR_TOPIC", "home/+/radiator/state")


class MQTTClient:
    def __init__(self, db=None):
        self.latest = {}           # room -> latest air-quality reading dict
        self.latest_radiator = {}  # room -> latest radiator state dict
        self.db = db if db is not None else Database()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        if MQTT_TLS:
            self.client.tls_set(ca_certs=MQTT_CA_CERT, cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            logging.error("MQTT connection refused: %s (check credentials/ACL)", reason_code)
            return
        logging.info("MQTT connected; subscribing")
        self.client.subscribe(MQTT_TOPIC)
        self.client.subscribe(MQTT_RADIATOR_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            if msg.topic.endswith("/radiator/state"):
                self._handle_radiator_state(msg)
            else:
                self._handle_reading(msg)
        except Exception as e:
            logging.error("on_message: failed to handle message on %s: %s", msg.topic, e)

    def _handle_reading(self, msg):
        payload = json.loads(msg.payload.decode())
        reading = SensorReading.from_payload(payload)
        self.latest[reading.room] = reading.to_dict()
        self.db.insert_reading(reading)
        logging.info("reading stored: room=%s co2=%s", reading.room, reading.co2)

    def _handle_radiator_state(self, msg):
        payload = json.loads(msg.payload.decode())
        state = RadiatorState.from_payload(payload)
        self.latest_radiator[state.room] = state.to_dict()
        self.db.insert_radiator_state(state)
        logging.info(
            "radiator state: room=%s current=%s target=%s valve=%s",
            state.room, state.current_temp, state.target_temp, state.valve,
        )

    def publish_radiator_command(self, room, target_temp):
        """Send a target-temperature command to a room's radiator."""
        topic = f"home/{room}/radiator/set"
        self.client.publish(topic, json.dumps({"target_temp": target_temp}))
        logging.info("published command %s target=%s", topic, target_temp)

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
