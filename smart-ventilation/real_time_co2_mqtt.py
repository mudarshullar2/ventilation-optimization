import paho.mqtt.client as mqtt
import logging
import json
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.tls_set()
        self.client.username_pw_set(username="kisam", password="dd9e3f43-a5bc-440d-8647-9c187376c1ef-kisam")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.parameters = {}
        self.combined_data = {"time": [], "co2": []}  # Initialize data for plotting
        self.fig, self.ax = plt.subplots()  # Create figure and axis objects
        self.line, = self.ax.plot([], [], marker='o')  # Create an empty line plot
        self.counter = 0  # Counter for x-axis values

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
            self.plot_data()

    def plot_data(self):
        if len(self.combined_data["time"]) > 0:
            df = pd.DataFrame(self.combined_data)
            df["time"] = pd.to_datetime(df["time"])  # Convert time to datetime format
            df["time"] = df["time"].dt.strftime("%H:%M")  # Format time to display only hour and minute
            x = range(self.counter, self.counter+len(df))  # Generate x-axis values
            self.line.set_data(x, df["co2"])  # Update the line plot data
            self.ax.set_xticks(x)  # Set x-axis ticks
            self.ax.set_xticklabels(df["time"])  # Set x-axis tick labels
            self.counter += len(df)  # Increment counter for the next set of x-axis values
            self.ax.relim()  # Recalculate limits
            self.ax.autoscale_view()  # Autoscale the view
            plt.draw()  # Redraw the plot

    def initialize(self):
        self.client.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883)
        self.client.loop_start()  # Start the MQTT client loop
        plt.xlabel("Time")
        plt.ylabel("CO2")
        plt.title("Real-time CO2 Plot")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()  # Show the plot window

def main():
    mqtt_client = MQTTClient()
    mqtt_client.initialize()

if __name__ == "__main__":
    main()