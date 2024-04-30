from database_management import get_sensor_data_last_month
from load_api import load_api_config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request, send_file, jsonify
from collections import deque
import joblib
import pandas as pd
import smtplib
import requests
import logging
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
import json
import time 
import threading

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

# Das vortrainierte Machine-Learning-Modell laden
model = joblib.load("smart-ventilation/models/model.pkl")

# Pfad zu Ihrer YAML-Konfigurationsdatei
config_file_path = 'smart-ventilation/api_config.yaml'

# API-Konfiguration aus YAML-Datei laden
api_config = load_api_config(config_file_path)

# API-Schlüssel und Basis-URL extrahieren
READ_API_KEY = api_config['READ_API_KEY']
POST_DELETE_API_KEY = api_config['POST_DELETE_API_KEY']
API_BASE_URL = api_config['API_BASE_URL']

# Initialize MQTT client
mqtt_client = MQTTClient()
mqtt_client.client.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883)
mqtt_client.client.loop_start()  # Start the MQTT client loop

data_queue = deque(maxlen=5)  # Assuming data arrives approximately every minute, this will store data for the five minutes

# Lock for synchronizing access to data_queue
data_lock = threading.Lock()

def aggregate_last_hour_data(data):
    # Convert timestamp to datetime
    data['time'] = pd.to_datetime(data['time'])
    
    # Calculate the timestamp for the start of the last hour
    last_five_minutes = datetime.now() - timedelta(minutes=5)
    
    # Filter data for the last hour
    last_five_minutes = data[data['time'] >= last_five_minutes]
    
    # Calculate aggregated values for the last hour
    if not last_five_minutes.empty:
        aggregated_values = last_five_minutes[['co2', 'humidity', 'temperature', 'tvoc']].agg(['mean'])
        return aggregated_values
    else:
        return pd.DataFrame()  # Return an empty DataFrame if no data available


def get_prediction(aggregated_data):
    if not aggregated_data.empty:
        # Extract mean values for prediction
        temperature = aggregated_data.loc['mean', 'temperature']
        humidity = aggregated_data.loc['mean', 'humidity']
        co2 = aggregated_data.loc['mean', 'co2']
        tvoc = aggregated_data.loc['mean', 'tvoc']
        
        # Make prediction using the pre-trained model
        prediction = model.predict([[temperature, humidity, co2, tvoc]])
        return prediction[0]
    else:
        return "No data available"


def make_predictions():
    global data_queue
    
    # Wait until data is available in the queue
    while True:
        with data_lock:
            if data_queue:
                break
        time.sleep(1)  # Check every second
        
    # Get the last hour of data from the queue
    last_hour_data = pd.concat(list(data_queue))
    
    # Calculate aggregated values for the last hour
    aggregated_values = aggregate_last_hour_data(last_hour_data)
    
    # Get prediction from the model
    prediction = get_prediction(aggregated_values)
    
    # Print prediction in the terminal
    print("Prediction:", prediction)
    
    # Log prediction
    logging.info("Prediction: %s", prediction)

# Start a thread to make predictions
prediction_thread = threading.Thread(target=make_predictions)
prediction_thread.start()


@app.route("/")
def index():
    try:
        global data_queue
        
        # Wait until data arrives
        while not mqtt_client.combined_data:
            time.sleep(1)
        
        # Extracting sensor data from mqtt_client.combined_data
        sensor_data = mqtt_client.combined_data
        temperature = sensor_data.get("temperature", 0)
        humidity = sensor_data.get("humidity", 0)
        co2 = sensor_data.get("co2", 0)
        tvoc = sensor_data.get("tvoc", "Currently not available")  # Initialize with a message if not present
        ambient_temp = sensor_data.get("ambient_temp", 0)

        with data_lock:
            if data_queue: 
                # Extracting sensor data from the queue
                sensor_data = pd.concat(list(data_queue))
                
                # Calculate aggregated values for the last hour
                aggregated_values = aggregate_last_hour_data(sensor_data)
                
                # Get prediction from the model
                prediction = get_prediction(aggregated_values)
            else: 
                prediction = "Currently not available"

        # Render the index.html template with the data
        return render_template(
            "index.html",
            sensor_data=sensor_data,
            temperature=temperature,
            humidity=humidity,
            co2=co2,
            tvoc=tvoc,
            ambient_temp=ambient_temp,
            prediction=prediction
        )

    except Exception as e:
        logging.error("An error occurred in index(): %s", str(e))
        return "Internal server error", 500


@app.route("/plots")
def plots():
    """
    Generates and renders real-time data plots based on the latest sensor data.
    :return: HTML page with the real-time data plots or an error message if no sensor data is available.
    """
    # Get the latest sensor data
    sensor_data = mqtt_client.combined_data

    # Check if sensor data is available
    if sensor_data:
        # Debugging output of received sensor data
        logging.info("Received sensor data in plots function:", sensor_data)

        # Render the HTML page with the real-time data plots
        return render_template(
            "plots.html",
            sensor_data=sensor_data  # Pass sensor data to the template
        )
    else:
        return "No sensor data available for plots."

@app.route("/data")
def data():
    return jsonify(mqtt_client.combined_data)


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
