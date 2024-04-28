import paho.mqtt.client as mqtt
import logging
import json
import paho.mqtt.client as mqtt
import json
import logging

logging.basicConfig(level=logging.INFO)

class MQTTClient:

    def __init__(self):             
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.tls_set()
        self.client.username_pw_set(username="kisam", password="dd9e3f43-a5bc-440d-8647-9c187376c1ef-kisam")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.parameters = {}
        self.combined_data = {}


    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected with result code " + str(rc))
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up")


    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        # Update combined data dictionary with data from all devices
        if topic.endswith("0004a30b01045883/event/up"):
            self.combined_data.update({
                "time": payload["time"], 
                "humidity": round(payload["object"]["humidity"], 2),
                "temperature": round(payload["object"]["temperature"], 2), 
                "co2": round(payload["object"]["co2"], 2)
            })
            logging.info("Data extracted for device1: %s", self.combined_data)
        elif topic.endswith("647fda000000aa92/event/up"):
            self.combined_data.update({
                "ambient_temp": round(payload["object"]["ambient_temp"], 2)
            })
            logging.info("Data extracted for device2: %s", self.combined_data)
        elif topic.endswith("24e124707c481005/event/up"):
            self.combined_data.update({
                "tvoc": round(payload["object"]["tvoc"], 2)
            })
            logging.info("Data extracted for device3: %s", self.combined_data)

        # Check if all required data is available before processing
        required_keys = ["time", "humidity", "temperature", "co2", "ambient_temp", "tvoc"]
        if all(key in self.combined_data for key in required_keys):
            # Perform further processing here...
            logging.info("All required data is available. Processing...")


    def initialize(self):
        self.client.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883)
        self.client.loop_start()


mqtt_client = MQTTClient()
