"""MQTT ingestion worker.

A standalone process that subscribes to the broker and persists air-quality
readings and radiator state. Kept separate from the web app so the web app can
run multiple gunicorn workers without each one ingesting (which would create
duplicate rows). Run it alongside the web app:

    MQTT_USERNAME=app MQTT_PASSWORD=... python -m ingestion.worker
"""
import logging
import time

from mqtt_client import MQTTClient


def main():
    logging.basicConfig(level=logging.INFO)
    client = MQTTClient(subscribe=True)
    client.initialize()
    logging.info("ingestion worker started")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("ingestion worker stopping")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
