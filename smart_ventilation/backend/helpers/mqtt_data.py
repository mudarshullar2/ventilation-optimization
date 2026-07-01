from backend.mqtt_client import MQTTClient
import logging

mqtt_client = MQTTClient()
mqtt_client.initialize()

def get_data(timestamp):
    try:
        return mqtt_client.fetch_data(timestamp)
    except Exception as e:
        logging.error("get_data: could not fetch data: %s", e)
        return {}