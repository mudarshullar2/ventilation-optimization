from sklearn.compose import ColumnTransformer
from sklearn.discriminant_analysis import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from load_api import load_api_config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
import pandas as pd
import numpy as np
import threading
import requests
import logging
import smtplib
import joblib
import json
import time 

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
        self.combined_data = {}
        self.data_points = [] 
        self.prediction_thread = threading.Thread(target=self.run_periodic_predictions)

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
        self.prediction_thread.start()


    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        # Daten von allen Sensoren in einem Dictionary zusammenfassen.
        if topic.endswith("0004a30b01045883/event/up"):
            self.combined_data.setdefault("time", []).append(payload["time"])
            self.combined_data.setdefault("humidity", []).append(round(payload["object"]["humidity"], 2))
            self.combined_data.setdefault("temperature", []).append(round(payload["object"]["temperature"], 2))
            self.combined_data.setdefault("co2", []).append(round(payload["object"]["co2"], 2))

        elif topic.endswith("647fda000000aa92/event/up"):
            self.combined_data.setdefault("time", []).append(payload["time"])
            self.combined_data.setdefault("ambient_temp", []).append(round(payload["object"]["ambient_temp"], 2))

        elif topic.endswith("24e124707c481005/event/up"):
            # Prüfen, ob „tvoc“ in payload[„object“] vorhanden ist, sonst auf Null setzen
            tvoc_value = payload["object"].get("tvoc", 0)
            self.combined_data.setdefault("time", []).append(payload["time"])
            self.combined_data.setdefault("tvoc", []).append(tvoc_value)

        required_keys = {"time", "humidity", "temperature", "co2", "tvoc"}
        if all(key in self.combined_data for key in required_keys):
            self.collect_data(self.combined_data)
            logging.info("All required data is present.")


    def collect_data(self, combined_data):
        try:
            max_length = max(len(combined_data[key]) for key in combined_data.keys())
            for i in range(max_length):
                data = {}
                for key in combined_data.keys():
                    if i < len(combined_data[key]):
                        data[key] = combined_data[key][i]
                self.data_points.append(data)
        except Exception as e:
            logging.error(f"Unexpected error occurred during data collection: {e}")


    def run_periodic_predictions(self):
        while True:
            time.sleep(3600)  # für 60 Minuten schlafen
            if self.data_points:
                try:
                    # data_points in DataFrame umwandeln
                    df = pd.DataFrame(self.data_points)

                    # Parsen von Zeitstempeln und Berechnen des durchschnittlichen Zeitstempels
                    df['parsed_time'] = pd.to_datetime(df['time'])
                    avg_time = df['parsed_time'].mean()
                    
                    # Durchschnittsdaten für Nicht-Zeit-Felder vorbereiten
                    avg_data = df.mean(numeric_only=True).to_dict()
                    avg_data['avg_time'] = avg_time.timestamp()  # In Zeitstempel umwandeln

                    # Merkmale für die Vorhersage vorbereiten
                    features_df = pd.DataFrame([avg_data])
                    
                    # Auf die richtige Reihenfolge und Einbeziehung achten !
                    features_prepared = self.prepare_features(features_df)

                    # Empfehlungen mit jedem Modell zurückgeben
                    predictions = {name: model.predict(features_prepared)[0] for name, model in self.models.items()}

                    # Prediction in combined_data hinzufügen, damit sie mit index() angezeigt werden können 
                    self.combined_data['predictions'] = predictions
                    
                    # Logging
                    logging.info("Processed data and generated predictions.")
                    self.data_points.clear()
                except Exception as e:
                    logging.error(f"Error during prediction: {e}")
            else:
                logging.info("No data has been collected in the last 3 minutes.")


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
            time.sleep(1)
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
    Generates and renders real-time data plots based on the latest sensor data, starting from the first non-empty data point and lasting for one hour.
    :return: HTML page with the real-time data plots or an error message if no sensor data is available.
    """
    global start_time  # Define start_time as a global variable
    start_time = start_time if 'start_time' in globals() else None  # Initialize start_time if not defined

    sensor_data = mqtt_client.get_latest_sensor_data()

    if sensor_data:
        if not start_time:
            start_time = datetime.now()  # Set start time when data first becomes non-empty

        current_time = datetime.now()
        if current_time - start_time > timedelta(hours=1):
            return "Data display interval has passed."

        # Prepare lists to collect filtered data
        co2_data = [data.get('co2', None) for data in sensor_data]
        temperature_data = [data.get('temperature', None) for data in sensor_data]
        humidity_data = [data.get('humidity', None) for data in sensor_data]
        tvoc_data = [data.get('tvoc', None) for data in sensor_data]
        time_data = [data.get('time', None) for data in sensor_data]

        # Align data points to ensure each sensor's data has the same length
        max_length = max(len(co2_data), len(temperature_data), len(humidity_data), len(tvoc_data), len(time_data))
        co2_data += [None] * (max_length - len(co2_data))
        temperature_data += [None] * (max_length - len(temperature_data))
        humidity_data += [None] * (max_length - len(humidity_data))
        tvoc_data += [None] * (max_length - len(tvoc_data))
        time_data += [None] * (max_length - len(time_data))

        # Render the HTML page with real-time data plots
        return render_template(
            "plots.html",
            co2_data=co2_data,
            temperature_data=temperature_data,
            humidity_data=humidity_data,
            tvoc_data=tvoc_data,
            time_data=time_data
        )
    else:
        return "Keine Daten zur Verfügung"


@app.route("/feedback", methods=["POST"])
def feedback():
    """
    Verarbeitet das Feedback, das über ein Formular gesendet wurde.
    :return: Weiterleitung zur Indexseite nach erfolgreicher Verarbeitung des Feedbacks
    """
    try:
        # Konvertiere das Feedback zu einer Ganzzahl (0 oder 1)
        is_correct = int(request.form["is_correct"])
        payload = {
            "temperature": request.form["temperature"],  # Temperaturwert aus dem Payload
            "humidity": request.form["humidity"],  # Luftfeuchtigkeitswert aus dem Payload
            "co2": request.form["co2"],  # CO2-Level aus dem Payload
            "accurate_prediction": is_correct,  # Genauigkeitsbewertung des Modells (0 oder 1)
        }
        headers = {
            "X-Api-Key": POST_DELETE_API_KEY,  # API-Schlüssel für den POST-Request
            "Content-Type": "application/json",  # Angegebener Inhaltstyp für die Anfrage
        }
        response = requests.post(API_BASE_URL, headers=headers, json=payload)  # POST-Anfrage an die API senden
        if response.status_code == 200:
            feedback_message = (
                "Vielen Dank! Dein Feedback wird die Genauigkeit "
                "des Modells verbessern!"
            )
        else:
            feedback_message = "Feedback konnte nicht gespeichert werden."
            
            # HTML-Seite mit Rückmeldung rendern
        return render_template("feedback.html", feedback_message=feedback_message)

    except Exception as e:
        return f"Fehler: {str(e)}"


# Neue Route zum Rendern von contact.html
@app.route('/contact')
def contact():
    """
    Rendert die contact.html-Seite.
    :return: Die gerenderte HTML-Seite contact.html.
    """
    return render_template('contact.html')


receiver_email = "mudarshullar22@gmail.com"


@app.route('/send_email', methods=['POST'])
def send_email():
    """
    Verarbeitet das Senden einer E-Mail über ein Formular.
    :return: Eine Bestätigungsmeldung bei erfolgreicher E-Mail-Zustellung oder eine Fehlermeldung.
    """
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        try:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587

            # Sichere Verbindung zum SMTP-Server von Gmail herstellen
            smtp = smtplib.SMTP(smtp_server, smtp_port)
            smtp.starttls()

            # Anmelden beim SMTP-Server von Gmail mit Ihren Anmeldeinformationen
            gmail_user = 'your_email@gmail.com'  # Durch Gmail-Adresse ersetzen
            gmail_password = 'your_password'  # Durch Ihr Gmail-Passwort ersetzen
            smtp.login(gmail_user, gmail_password)

            # E-Mail-Nachricht erstellen
            msg = MIMEMultipart()
            msg['From'] = email
            msg['To'] = receiver_email
            msg['Subject'] = f"New Message from {name} ({email})"
            msg.attach(MIMEText(message, 'plain'))

            # E-Mail senden
            smtp.sendmail(email, receiver_email, msg.as_string())

            # SMTP-Verbindung beenden
            smtp.quit()

            return "E-Mail erfolgreich gesendet!"
        except Exception as e:
            return f"Fehler: {str(e)}"


if __name__ == "__main__":
    app.run(debug=True)
