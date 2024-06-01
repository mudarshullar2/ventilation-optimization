from api_config_loader import load_api_config
from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta, timezone
import datetime as dt
import paho.mqtt.client as mqtt
import pandas as pd
import copy
import threading
import requests
import logging
import joblib
import json
import time 
import requests, json

logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder='/Users/mudarshullar/Desktop/ventilation-optimization Project/ventilation-optimization/smart-ventilation/static')

# Pfad zu Ihrer YAML-Konfigurationsdatei
config_file_path = './smart-ventilation/api_config.yaml'

# API-Konfiguration aus YAML-Datei laden
api_config = load_api_config(config_file_path)

# API-Schlüssel und Basis-URL extrahieren
READ_API_KEY = api_config['READ_API_KEY']
POST_API_KEY = api_config['POST_API_KEY']
API_BASE_URL = api_config['API_BASE_URL']
CONTENT_TYPE = api_config["CONTENT_TYPE"]
CLOUD_SERVICE_URL = api_config["CLOUD_SERVICE_URL"]
USERNAME = api_config["USERNAME"]
PASSWORD = api_config["PASSWORD"]


class MQTTClient:

    def __init__(self):             
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.tls_set()
        self.client.username_pw_set(username=USERNAME, password=PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.parameters = {}
        self.latest_predictions = {}
        self.combined_data = {}
        self.data_points = []
        self.thread_alive = True
        self.prediction_thread = threading.Thread(target=self.run_periodic_predictions)
        self.prediction_thread.start()
        self.data_lock = threading.Lock()

        # Start the periodic clearing thread
        self.clearing_thread = threading.Thread(target=self.periodic_clear)
        self.clearing_thread.start()

        # die vortrainierten Machine-Learning-Modelle laden
        self.models = {
            'Logistic Regression': joblib.load('smart-ventilation/models/Logistic_Regression.pkl'),
            'Decision Tree': joblib.load('smart-ventilation/models/Decision_Tree.pkl'),
            'Random Forest': joblib.load('smart-ventilation/models/Random_Forest.pkl')
        }


    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected with result code " + str(rc))
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up")

        if not self.prediction_thread.is_alive():
            logging.warning("Prediction thread has stopped, restarting...")
            self.restart_thread()
    
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        # Function to adjust and format the time
        def adjust_and_format_time(raw_time):
                utc_time = dt.datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S.%f%z")
                local_time = utc_time + dt.timedelta(hours=2)
                return local_time.strftime("%Y-%m-%d %H:%M")
        
        # Daten von allen Sensoren in einem Dictionary zusammenfassen.
        if topic.endswith("0004a30b01045883/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)
            self.combined_data.setdefault("humidity", []).append(round(payload["object"]["humidity"], 2))
            self.combined_data.setdefault("temperature", []).append(round(payload["object"]["temperature"], 2))
            self.combined_data.setdefault("co2", []).append(round(payload["object"]["co2"], 2))

            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)
            tvoc_values = 400
            ambient_temp_values = 500
            self.combined_data.setdefault("tvoc", []).append(tvoc_values)
            self.combined_data.setdefault("ambient_temp", []).append(ambient_temp_values)

        #elif topic.endswith("647fda000000aa92/event/up"):
        #    formatted_time = adjust_and_format_time(payload["time"])
        #    self.combined_data.setdefault("time", []).append(formatted_time)
        #    self.combined_data.setdefault("ambient_temp", []).append(round(payload["object"]["ambient_temp"], 2))

        #elif topic.endswith("24e124707c481005/event/up"):
        #    formatted_time = adjust_and_format_time(payload["time"])
        #    tvos_value = payload["object"].get("tvoc")
        #    self.combined_data.setdefault("time", []).append(formatted_time)
        #    # Only append "tvoc" value if it is not None
        #    if tvos_value is not None:
        #        self.combined_data.setdefault("tvoc", []).append(tvos_value)

        required_keys = {"time", "humidity", "temperature", "co2", "tvoc", "ambient_temp"}
        if all(key in self.combined_data for key in required_keys):
            self.collect_data(self.combined_data)


    def collect_data(self, combined_data):
        try:
            max_length = max(len(combined_data[key]) for key in combined_data if isinstance(combined_data[key], list))  # Only consider lists
            for i in range(max_length):
                data = {}
                for key in combined_data:
                    # Ensure the key points to a list and index is within range
                    if isinstance(combined_data[key], list) and i < len(combined_data[key]):
                        data[key] = combined_data[key][i]
                if data:  # Ensure data is not empty before appending
                    self.data_points.append(data)
        except Exception as e:
            logging.error(f"Unexpected error occurred during data collection: {e}")
            logging.error(f"combined data content: {combined_data}")
            logging.swrror(f"data_points content: {self.data_points}")
    

    def run_periodic_predictions(self):
        while self.thread_alive:
            time.sleep(120)  # Sleep for 2 minutes
            if self.data_points:
                try:
                    data_points_copy = copy.deepcopy(self.data_points)
                    df = pd.DataFrame(data_points_copy)
                    logging.info("DataFrame created successfully: %s", df)

                    # Parse timestamps and calculate the average timestamp
                    df['parsed_time'] = pd.to_datetime(df['time'])
                    avg_time = df['parsed_time'].mean()
                    logging.info("Timestamp parsing and average calculation successful: avg_time=%s", avg_time)

                    # Prepare average data for non-time fields
                    avg_data = df.mean(numeric_only=True).to_dict()
                    avg_data['avg_time'] = avg_time.timestamp()  # In Zeitstempel umwandeln

                    logging.info("Average data preparation successful: %s", avg_data)

                    # Prepare features for prediction
                    features_df = pd.DataFrame([avg_data])
                    logging.info("Features prepared for prediction: %s", features_df)

                    # Generate predictions with each model
                    predictions = {name: model.predict(features_df)[0] for name, model in self.models.items()}
                    self.combined_data['predictions'] = predictions
                    self.latest_predictions = predictions

                    # Store features_df for later use in feedback
                    self.latest_features_df = features_df

                    # Clear data_points after successful processing
                    self.data_points.clear()
                    logging.info("Data points cleared after processing.")
                except Exception as e:
                    logging.error(f"Error during prediction processing: {e}")
            else:
                logging.info("No data collected in the last 2 minutes.")

    
    def restart_thread(self):
        """Restart the thread if it has stopped."""
        self.thread_alive = True
        self.prediction_thread = threading.Thread(target=self.run_periodic_predictions)
        self.prediction_thread.start()
        logging.info("Prediction thread restarted successfully.")


    def get_latest_sensor_data(self):
        # Return a copy of the latest sensor data
        return self.data_points.copy()


    def periodic_clear(self):
        while True:
            time.sleep(360)  # Sleep for 6 minutes
            with self.data_lock:
                self.data_points.clear()
                self.combined_data.clear()
            logging.info("Data points and combined data have been cleared after 6 minutes.")
            logging.info(f"content of self.data_points after clearning: {self.data_points}")
            logging.info(f"content of self.combined_data after clearning is: {self.combined_data}")


    def initialize(self):
        self.client.connect(CLOUD_SERVICE_URL, 8883)
        self.client.loop_start()


# MQTT-Client initialisieren
mqtt_client = MQTTClient()
mqtt_client.client.connect(CLOUD_SERVICE_URL, 8883)
mqtt_client.client.loop_start()


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        # Check if combined_data is available, if not set default values
        if not mqtt_client.combined_data:
            sensor_data = {}
            temperature = 0
            humidity = 0
            co2 = 0
            tvoc = "Currently not available"
            ambient_temp = 0
            predictions = {}
        else: 
            # Extrahieren von Sensordaten aus mqtt_client.combined_data
            sensor_data = mqtt_client.combined_data
            temperature = sensor_data.get("temperature", 0)
            humidity = sensor_data.get("humidity", 0)
            co2 = sensor_data.get("co2", 0)
            tvoc = sensor_data.get("tvoc", "Currently not available")
            ambient_temp = sensor_data.get("ambient_temp", 0)
            predictions = sensor_data.get('predictions', {})  # Standardmäßig auf ein leeres Dict eingestellt
        # Die Vorlage index.html mit den Daten rendern
        return render_template(
            "index.html",
            sensor_data=sensor_data,
            temperature=temperature,
            humidity=humidity,
            co2=co2,
            tvoc=tvoc,
            ambient_temp=ambient_temp,
            predictions=predictions,
        )
    except Exception as e:
        logging.error("An error occurred in index(): %s", str(e))
        return "Internal server error", 500


@app.route("/plots")
def plots():

    """
    Generiert und rendert Echtzeit-Datenplots basierend auf den neuesten Sensordaten, beginnend beim ersten nicht-leeren Datenpunkt und dauert eine Stunde.
    Wenn das einstündige Intervall erreicht ist, wird die Startzeit zurückgesetzt und die Anzeige beginnt erneut mit den neuen Daten.
    :return: HTML-Seite mit den Echtzeit-Datenplots oder eine Fehlermeldung, falls keine Sensordaten verfügbar sind.
    """

    sensor_data = mqtt_client.get_latest_sensor_data()

    if sensor_data: 
       # Listen vorbereiten, um gefilterte Daten zu sammeln
        co2_data = [data.get('co2', None) for data in sensor_data]
        temperature_data = [data.get('temperature', None) for data in sensor_data]
        humidity_data = [data.get('humidity', None) for data in sensor_data]
        tvoc_data = [data.get('tvoc', None) for data in sensor_data]
        time_data = [data.get('time', None) for data in sensor_data]

        # Datenpunkte ausrichten, um sicherzustellen, dass die Daten jedes Sensors die gleiche Länge haben
        max_length = max(len(co2_data), len(temperature_data), len(humidity_data), len(time_data) , len(tvoc_data))
        co2_data += [None] * (max_length - len(co2_data))
        temperature_data += [None] * (max_length - len(temperature_data))
        humidity_data += [None] * (max_length - len(humidity_data))
        tvoc_data += [None] * (max_length - len(tvoc_data))
        time_data += [None] * (max_length - len(time_data))

        # HTML-Seite mit Echtzeit-Datenplots rendern
        return render_template(
            "plots.html",
            co2_data=co2_data,
            temperature_data=temperature_data,
            humidity_data=humidity_data,
            tvoc_data=tvoc_data,
            time_data=time_data
        )
    else:
        # Prepare empty data sets for the plots
        co2_data = []
        temperature_data = []
        humidity_data = []
        tvoc_data = []
        time_data = []

        # Render the template with empty data sets
        return render_template(
            "plots.html",
            co2_data=co2_data,
            temperature_data=temperature_data,
            humidity_data=humidity_data,
            tvoc_data=tvoc_data,
            time_data=time_data
        )


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        try:
            predictions = mqtt_client.latest_predictions
            # Check if combined_data exists and contains the 'predictions' key with actual values
            if not predictions: 
                return "No predictions available to submit feedback on", 400
            
            combined_data = mqtt_client.combined_data
            logging.info(f"current combined_data: {combined_data}")

            features_df = mqtt_client.latest_features_df  # Get the stored features_df
            logging.info(f"current features_df: {features_df}")
            
            # Convert avg_time from UNIX timestamp to a readable format using timezone-aware datetime
            avg_time_unix = float(features_df['avg_time'].iloc[0]) if 'avg_time' in features_df else 0.0
            avg_time_readable = datetime.fromtimestamp(avg_time_unix, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            feedback_data = {
                "temperature": float(features_df['temperature'].iloc[0]),
                "humidity": float(features_df['humidity'].iloc[0]),
                "co2": float(features_df['co2'].iloc[0]),
                "avg_time": avg_time_readable,
                "outdoor_temperature": float(features_df['ambient_temp'].iloc[0]),
                "accurate_prediction": int(request.form['accurate_prediction'])
            }

            headers = {
                "X-Api-Key": POST_API_KEY,
                "Content-Type": CONTENT_TYPE
            }

            response = requests.post(
                API_BASE_URL,
                headers=headers,
                json=feedback_data
            )

            logging.info(f"Payload sent: {feedback_data}")
            logging.info(f"API Response: {response.json()}")

            if response.status_code == 200:
                # Clear the latest_predictions to free up memory
                mqtt_client.latest_predictions = {}
                return render_template('thank_you.html')
            else:
                return jsonify({"message": "Failed to submit feedback", "status": response.status_code, "response": response.text}), 400

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            return jsonify({"message": "An unexpected error occurred", "error": str(e)}), 500
        
    else:
        try:
            predictions = mqtt_client.latest_predictions
            if not predictions:
                return "No predictions available", 400
            
            predictions = mqtt_client.latest_predictions
            features_df = mqtt_client.latest_features_df

            return render_template('feedback.html', predictions=predictions, features=features_df.to_dict(orient='records')[0])

        except Exception as e:
            logging.error(f"An unexpected error occurred while fetching predictions: {e}")
            return str(e), 500


@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')


# Neue Route zum Rendern von contact.html
@app.route('/contact')
def contact():
    """
    Rendert die contact.html-Seite.
    :return: Die gerenderte HTML-Seite contact.html.
    """
    return render_template('contact.html')


if __name__ == "__main__":
    app.run(debug=True)
