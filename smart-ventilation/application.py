from sklearn.compose import ColumnTransformer
from sklearn.discriminant_analysis import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from load_api import load_api_config
from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta
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


class MQTTClient:

    def __init__(self):             
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.tls_set()
        self.client.username_pw_set(username="kisam", password="dd9e3f43-a5bc-440d-8647-9c187376c1ef-kisam")
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

        elif topic.endswith("647fda000000aa92/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)
            self.combined_data.setdefault("ambient_temp", []).append(round(payload["object"]["ambient_temp"], 2))

        elif topic.endswith("24e124707c481005/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            tvos_value = payload["object"].get("tvoc")
            self.combined_data.setdefault("time", []).append(formatted_time)
            # Only append "tvoc" value if it is not None
            if tvos_value is not None:
                self.combined_data.setdefault("tvoc", []).append(tvos_value)

        required_keys = {"time", "humidity", "temperature", "co2", "tvoc"}
        if all(key in self.combined_data for key in required_keys):
            self.collect_data(self.combined_data)
            logging.info("All required data is present.")


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
            time.sleep(600)  # für 10 Minuten schlafen
            if self.data_points:
                try:
                    data_points_copy = copy.deepcopy(self.data_points)
                    df = pd.DataFrame(data_points_copy)
                    logging.info("DataFrame wurde erfolgreich erstellt.")

                    # Parsen von Zeitstempeln und Berechnen des durchschnittlichen Zeitstempels
                    df['parsed_time'] = pd.to_datetime(df['time'])
                    avg_time = df['parsed_time'].mean()
                    logging.info("Zeitstempel-Parsing und Durchschnittsberechnung erfolgreich.")

                    # Durchschnittsdaten für Nicht-Zeit-Felder vorbereiten
                    avg_data = df.mean(numeric_only=True).to_dict()
                    avg_data['avg_time'] = avg_time.timestamp()  # In Zeitstempel umwandeln
                    logging.info("Vorbereitung der Durchschnittsdaten erfolgreich.")

                    # Merkmale für die Vorhersage vorbereiten
                    features_df = pd.DataFrame([avg_data])
                    features_prepared = self.prepare_features(features_df)
                    logging.info("Vorbereitung der Merkmale für die Vorhersage erfolgreich.")

                    # Empfehlungen mit jedem Modell zurückgeben
                    predictions = {name: model.predict(features_prepared)[0] for name, model in self.models.items()}
                    self.combined_data['predictions'] = predictions
                    logging.info("Vorhersagen wurden generiert und zu combined_data hinzugefügt.")
                    self.latest_predictions = predictions

                    # data_points nach erfolgreicher Verarbeitung löschen
                    data_points_copy.clear()
                except Exception as e:
                    logging.error(f"Fehler während der Verarbeitung der Vorhersagen: {e}")
            else:
                logging.info("In den letzten 10 Minuten wurden keine Daten gesammelt.")
    

    def restart_thread(self):
        """Restart the thread if it has stopped."""
        self.thread_alive = True
        self.prediction_thread = threading.Thread(target=self.run_periodic_predictions)
        self.prediction_thread.start()
        logging.info("Prediction thread restarted successfully.")


    def prepare_features(self, X):
        # Numerische und kategoriale Merkmale definieren
        numeric_features = ['avg_time', 'temperature', 'co2', 'humidity', 'tvoc']

        # numerische Merkmale transformationen
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])

        # Transformationen kombinieren
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numeric_features)
            ])

        return preprocessor.fit_transform(X)


    def get_latest_sensor_data(self):
        # Return a copy of the latest sensor data
        return self.data_points.copy()


    def periodic_clear(self):
        while True:
            time.sleep(1200)  # Sleep for 20 minutes
            with self.data_lock:
                self.data_points.clear()
                self.combined_data.clear()
            logging.info("Data points and combined data have been cleared after 20 minutes.")
            logging.info(f"content of self.data_points after clearning: {self.data_points}")
            logging.info(f"content of self.combined_data after clearning is: {self.combined_data}")


    def initialize(self):
        self.client.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883)
        self.client.loop_start()


# Pfad zu Ihrer YAML-Konfigurationsdatei
config_file_path = 'smart-ventilation/api_config.yaml'

# API-Konfiguration aus YAML-Datei laden
api_config = load_api_config(config_file_path)

# API-Schlüssel und Basis-URL extrahieren
READ_API_KEY = api_config['READ_API_KEY']
POST_DELETE_API_KEY = api_config['POST_DELETE_API_KEY']
API_BASE_URL = api_config['API_BASE_URL']

# MQTT-Client initialisieren
mqtt_client = MQTTClient()
mqtt_client.client.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883)
mqtt_client.client.loop_start()


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        # Warten, bis die Daten ankommen
        while not mqtt_client.combined_data:
            time.sleep(15)
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
    global start_time  # Startzeit als globale Variable definieren
    start_time = start_time if 'start_time' in globals() else None  # Startzeit initialisieren, falls nicht definiert
    
    sensor_data = mqtt_client.get_latest_sensor_data()

    if sensor_data: 
        if not start_time:
            start_time = datetime.now()  # Startzeit setzen, wenn Daten zum ersten Mal nicht leer sind

        current_time = datetime.now()
        if current_time - start_time > timedelta(hours=1):
        #if current_time - start_time > timedelta(minutes=5):
            start_time = datetime.now()  # Startzeit für ein neues Intervall zurücksetzen
            logging.info("Resetting plots() after reaching 5 minutes")
            #mqtt_client.clear_data()  # Clear the sensor data from the source
            return "Datenanzeigeintervall wurde zurückgesetzt. Neue Daten werden angezeigt."

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
            if not predictions:
                return "No predictions available to submit feedback on", 400

            feedback_data = {
                "temperature": predictions.get('temperature', 0),
                "humidity": predictions.get('humidity', 0),
                "co2": predictions.get('co2', 0),
                "outdoor_temperature": predictions.get('outdoor_temperature', 0),
                "accurate_prediction": int(request.form['accurate_prediction'])
            }

            headers = {
                "X-Api-Key": "9dcff132-400a-41bd-9391-24f08e66f383-kisamadm",
                "Content-Type": "application/json"
            }

            response = requests.post(
                "https://cs1-swp.westeurope.cloudapp.azure.com:8443/air_data",
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
            # Fetch the latest predictions
            predictions = mqtt_client.latest_predictions
            if predictions:
                return render_template('feedback.html', predictions=predictions)
            else:
                return "No predictions available", 400
        except Exception as e:
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
