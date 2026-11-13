"""Mock smart-radiator (TRV) simulator.

Simulates one TRV per room. It:
  - subscribes to  home/<room>/radiator/set   (target temperature commands)
  - simulates simple heating physics each tick
  - publishes      home/<room>/radiator/state (current temp, target, valve, mode)

So the app can command a target temperature and watch the room heat toward it,
exercising the full control loop with no hardware. Run it alongside the app:

    python -m control.mock_radiator

Config via env: MQTT_HOST, MQTT_PORT, MOCK_INTERVAL (s), MOCK_ROOMS.
"""
import json
import logging
import os
import ssl
import threading
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

# Simple thermal constants (per tick).
HEAT_RATE = 0.4      # °C gained per tick at 100% valve
AMBIENT_LOSS = 0.1   # °C lost per tick toward a cool ambient
AMBIENT = 17.0       # ambient the room drifts toward when the valve is shut

logging.basicConfig(level=logging.INFO)


def clamp(value, low, high):
    return max(low, min(high, value))


class Radiator:
    def __init__(self, room):
        self.room = room
        self.current = 19.0
        self.target = 20.0
        self.valve = 0.0
        self.lock = threading.Lock()

    def set_target(self, target):
        with self.lock:
            self.target = clamp(float(target), 5.0, 30.0)

    def step(self):
        with self.lock:
            gap = self.target - self.current
            # Proportional valve: opens as the room sits below target.
            self.valve = clamp(gap * 40.0, 0.0, 100.0)
            # Heat added by the valve, minus loss toward ambient.
            self.current += (self.valve / 100.0) * HEAT_RATE
            self.current += (AMBIENT - self.current) * (AMBIENT_LOSS / 10.0)
            self.current = round(self.current, 2)
            mode = "heat" if self.valve > 0 else "off"
            return {
                "room": self.room,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "current_temp": self.current,
                "target_temp": round(self.target, 1),
                "valve": round(self.valve, 1),
                "mode": mode,
            }


def main():
    radiators = {room: Radiator(room) for room in ROOMS}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(c, userdata, flags, reason_code, properties):
        c.subscribe("home/+/radiator/set")
        logging.info("mock radiator: subscribed to home/+/radiator/set")

    def on_message(c, userdata, msg):
        try:
            room = msg.topic.split("/")[1]
            payload = json.loads(msg.payload.decode())
            target = payload.get("target_temp")
            if room in radiators and target is not None:
                radiators[room].set_target(target)
                logging.info("set target: %s -> %s", room, target)
        except Exception as e:
            logging.error("mock radiator: bad command on %s: %s", msg.topic, e)

    client.on_connect = on_connect
    client.on_message = on_message
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set(ca_certs=MQTT_CA_CERT, cert_reqs=ssl.CERT_REQUIRED)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    logging.info("mock radiator: %d room(s) -> %s:%s every %ss", len(radiators), MQTT_HOST, MQTT_PORT, INTERVAL)
    try:
        while True:
            for radiator in radiators.values():
                state = radiator.step()
                client.publish(f"home/{radiator.room}/radiator/state", json.dumps(state))
                logging.info(
                    "state %s: current=%s target=%s valve=%s",
                    radiator.room, state["current_temp"], state["target_temp"], state["valve"],
                )
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logging.info("mock radiator stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
