from database_management import get_sensor_data_last_month
from load_api import load_api_config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime
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

# die vortrainierten Machine-Learning-Modelle laden
models = {
    'Logistic Regression': joblib.load('smart-ventilation/models/Logistic_Regression.pkl'),
    'Decision Tree': joblib.load('smart-ventilation/models/Decision_Tree.pkl'),
    'Random Forest': joblib.load('smart-ventilation/models/Random_Forest.pkl')
}

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


    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected with result code " + str(rc))
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up")
        self.prediction_thread.start()


    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        # Daten aus allen Sensoren in einem Dict kombinieren
        if topic.endswith("0004a30b01045883/event/up"):
            self.combined_data.update({
                "time": payload["time"], 
                "humidity": round(payload["object"]["humidity"], 2),
                "temperature": round(payload["object"]["temperature"], 2), 
                "co2": round(payload["object"]["co2"], 2)
            })
            logging.info("Daten aus device1: %s", self.combined_data)
        elif topic.endswith("647fda000000aa92/event/up"):
            self.combined_data.update({
                "time": payload["time"], 
                "ambient_temp": round(payload["object"]["ambient_temp"], 2)
            })
            logging.info("Daten aus device2: %s", self.combined_data)
        elif topic.endswith("24e124707c481005/event/up"):
            # Falls der Wert TVOC momentan nicht vorhanden ist
            if "tvoc" in payload["object"]:
                tvoc_value = round(payload["object"]["tvoc"], 2)
            else:
                 tvoc_value = None
            self.combined_data.update({
                "time": payload["time"], 
                "tvoc": tvoc_value
            })
            logging.info("Daten aus device3: %s", self.combined_data)


    def collect_data(self, payload):
        try:
            # Daten aus dem Payload sicher extrahieren
            data = {
                "temperature": payload["object"].get("temperature", 0),  # Standardwert 0, wenn die Temperatur nicht vorhanden ist
                "humidity": payload["object"].get("humidity", 0),  # Standardwert 0, wenn die Luftfeuchtigkiet nicht vorhanden ist
                "co2": payload["object"].get("co2", 0),  # Standardwert 0, wenn Co2 Werte nicht vorhanden sind
                "tvoc": payload["object"].get("tvoc", 0)  # Standardwert 0, wenn TVOC Werte nicht vorhanden sind
            }
            self.data_points.append(data)
        except Exception as e:
            logging.error(f"Unerwarteter Fehler bei der Datenerfassung: {e}")


    def run_periodic_predictions(self):
        while True:
            time.sleep(180)  # 3 Minuten (180 Sekunden) schlafen
            if self.data_points:
                # Berechnung von Durchschnittswerten für kontinuierliche Variablen
                average_data = {key: np.mean([d[key] for d in self.data_points if key in d]) for key in self.data_points[0] if key != 'time'}
                
                # Behandlung des Zeitstempels durch Überprüfung, ob er existiert und korrekt formatiert ist
                if any('time' in d for d in self.data_points):
                    last_timestamp = next((d['time'] for d in self.data_points if 'time' in d), None)
                    if last_timestamp:
                        try:
                            if last_timestamp.endswith('Z'):
                                last_timestamp = last_timestamp[:-1] + '+00:00'  # 'Z' zu '+00:00' umwandeln
                            average_data['hour'] = datetime.fromisoformat(last_timestamp).hour
                        except ValueError:
                            logging.error("Error parsing time: %s", last_timestamp)
                            average_data['hour'] = 0  # Standardwert 0 oder ein anderer sinnvoller Standardwert
                    else:
                        average_data['hour'] = 0  # Default, wenn keine gültige Zeit gefunden wird
                else:
                    average_data['hour'] = 0  # Default, wenn keine Zeitstempel vorhanden sind
                # Einbindung der 'tvoc'-Behandlung mit Standardwert
                average_data['tvoc'] = np.mean([d['tvoc'] for d in self.data_points if 'tvoc' in d]) if any('tvoc' in d for d in self.data_points) else 0
                # Feature-Array für ML-Modelle konstruieren 
                try:
                    features = np.array([[average_data.get('temperature', 0), average_data.get('co2', 0), average_data.get('humidity', 0), average_data.get('tvoc', 0), average_data.get('hour', 0)]])
                    # Vorhersage mit jedem Modell und Speicherung der Ergebnisse
                    predictions = {name: model.predict(features)[0] for name, model in models.items()}
                    # Vorhersagen für den Zugriff durch Flask speichern
                    self.combined_data['predictions'] = predictions
                    # Die Daten nach der Erstellung von Vorhersagen zurücksetzen
                    self.data_points.clear()
                except Exception as e:
                    logging.error("Fehler bei der Vorhersage: %s", str(e))
            else:
                logging.info("In den letzten 3 Minuten wurden keine Daten erfasst.")
    

    def get_latest_sensor_data(self):
        # Rückgabe einer Kopie der letzten Sensordaten
        return self.combined_data.copy()


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


@app.route("/data")
def data():
    # Die kombinierten Sensordaten vom MQTT-Client abrufen
    combined_data = mqtt_client.combined_data

    # Konvertieren Sie alle nicht serialisierbaren Datentypen (z. B. numpy int64) in reguläre Python-Typen
    serializable_data = convert_to_serializable(combined_data)

    # Die JSON-Antwort zurückgeben
    return jsonify(serializable_data)


def convert_to_serializable(data):
    """
    Konvertiert alle nicht serialisierbaren Datentypen innerhalb der Daten in serialisierbare Typen.
    """
    if isinstance(data, dict):
        # Wenn die Daten ein Wörterbuch sind, konvertieren Sie rekursiv seine Werte
        return {key: convert_to_serializable(value) for key, value in data.items()}
    elif isinstance(data, list):
        # Wenn die Daten eine Liste sind, konvertieren Sie rekursiv ihre Elemente
        return [convert_to_serializable(item) for item in data]
    elif isinstance(data, np.integer):
        # Wenn die Daten eine numpy-Ganzzahl sind, konvertieren Sie sie in eine reguläre Python-Ganzzahl
        return int(data)
    else:
        # Andernfalls sind die Daten bereits serialisierbar
        return data


@app.route("/plots")
def plots():
    """
    Generates and renders real-time data plots based on the latest sensor data.
    :return: HTML page with the real-time data plots or an error message if no sensor data is available.
    """
    # Die neuesten Sensordaten vom MQTTClient abrufen
    sensor_data = mqtt_client.get_latest_sensor_data()

    # Prüfen, ob Sensordaten vorhanden sind
    if sensor_data:
        # die notwendigen Daten für das Plotten extrahieren
        co2_data = sensor_data.get('co2', [])
        temperature_data = sensor_data.get('temperature', [])
        humidity_data = sensor_data.get('humidity', [])
        tvoc_data = sensor_data.get('tvoc', [])

        # Rendering der HTML-Seite mit den Echtzeit-Datenplots
        return render_template(
            "plots.html",
            co2_data=co2_data,
            temperature_data=temperature_data,
            humidity_data=humidity_data,
            tvoc_data=tvoc_data
        )
    else:
        return "Keine Daten vorhanden."


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


@app.route("/download_co2_data", methods=["GET"])
def download_co2_data():
    """
    Ruft Sensordaten der letzten Woche ab und erstellt eine Excel-Datei mit diesen Daten sowie deskriptive Statistiken.
    :return: Sendet die erstellte Excel-Datei als Download, falls Sensordaten vorhanden sind; ansonsten eine Fehlermeldung.
    """
    try:
        # Sensordaten des letzten Monats abrufen
        sensor_data = get_sensor_data_last_month()
        # Überprüfen, ob Sensordaten vorhanden sind
        if sensor_data:
            df = pd.DataFrame(sensor_data, columns=["Timestamp", "Temperature", "Humidity", "CO2", "TVOC"])
            descriptive_stats = df.describe()  # Deskriptive Statistiken über die Sensordaten berechnen
            # Excel-Datei erstellen
            output_path = "co2_data_last_month.xlsx"
            with pd.ExcelWriter(output_path) as writer:
                df.to_excel(writer, index=False, sheet_name="Sensor Data")
                descriptive_stats.to_excel(writer, sheet_name="Descriptive Statistics")
            # Excel-Datei als Download senden
            return send_file(output_path, as_attachment=True)
        else:
            return "Keine Sensordaten verfügbar für den letzten Monat."
    except Exception as e:
        return f"Fehler: {str(e)}"


@app.route('/select-design')
def select_design():
    return render_template('design.html')


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
