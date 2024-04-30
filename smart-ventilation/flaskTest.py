# app.py
from flask import Flask, render_template, jsonify
import paho.mqtt.client as mqtt
import logging
import json

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.tls_set()
        self.client.username_pw_set(username="kisam", password="dd9e3f43-a5bc-440d-8647-9c187376c1ef-kisam")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.combined_data = {"time": [], "co2": []}  # Initialize data for plotting

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected with result code " + str(rc))
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        if topic.endswith("0004a30b01045883/event/up"):
            self.combined_data["time"].append(payload["time"])
            self.combined_data["co2"].append(payload["object"]["co2"])
            logging.info("Data extracted for device1: %s", payload)

mqtt_client = MQTTClient()
mqtt_client.client.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883)
mqtt_client.client.loop_start()  # Start the MQTT client loop

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    return jsonify(mqtt_client.combined_data)

if __name__ == "__main__":
    app.run(debug=True)
