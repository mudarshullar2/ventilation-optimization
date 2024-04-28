import paho.mqtt.client as mqtt
from datetime import datetime
import logging
import time

logging.basicConfig(level=logging.INFO)

# Die Funktion wird aufgerufen, wenn die Verbindung hergestellt wird
def on_connect(client, userdata, flags, rc):
    logging.info("Connected with result code " + str(rc))
    # default 
    client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/#")
    # Klasse 1c
    client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up")
    # Außentemperaturen 
    client.subscribe("/application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/#")
    # Milesight Modul
    client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up")

# Die Funktion wird aufgerufen, wenn eine Nachricht empfangen wird 
def on_message(client, userdata, msg):
    logging.info(str(datetime.utcnow()) + ":  " + msg.topic + " " + str(msg.payload))


# MQTT-Client einrichten
def initialize_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set(username="kisam",password="dd9e3f43-a5bc-440d-8647-9c187376c1ef-kisam")

    return client

def main():
    while True:
        try:
            # 1. Client
            client1 = initialize_mqtt_client()
            logging.info("Connecting client 1...")
            client1.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883, 10)
            client1.loop_start()

            # 2. Client
            client2 = initialize_mqtt_client()
            logging.info("Connecting client 2...")
            client2.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883, 10)
            client2.loop_start()

            # 3. Client
            client3 = initialize_mqtt_client()
            logging.info("Connecting client 3...")
            client3.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883, 10)
            client3.loop_start()

            while True:
                time.sleep(10)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            logging.info("Retrying in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    main()
