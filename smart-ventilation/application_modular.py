from flask import Flask, jsonify, render_template, request
import logging
from datetime import datetime, timezone
import requests
from mqtt_client import MQTTClient
from api_config_loader import load_api_config

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

# MQTT-Client initialisieren
mqtt_client = MQTTClient()
mqtt_client.initialize()


@app.route("/", methods=["GET", "POST"])
def index():

    try:
        # Prüfen, ob combined_data verfügbar ist, falls nicht, Standardwerte setzen
        if not mqtt_client.combined_data:
            sensor_data = {}
            temperature = 0
            humidity = 0
            co2 = 0
            tvoc = "Zurzeit nicht verfügbar"
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

    """
    Diese Funktion behandelt das Feedback der Benutzer bezüglich der Vorhersagen.
    
    Wenn die Methode POST ist, wird das Feedback gesendet.
    Wenn die Methode GET ist, wird das Feedback-Formular angezeigt.
    Validiert die Daten und sendet sie an die API.
    Bei Erfolg wird die Dankeseite angezeigt.
    
    :return: gerenderte HTML-Seite oder JSON-Antwort mit Fehlermeldung
    """

    if request.method == 'POST':

        try:
            # Vorhersagen vom MQTT-Client abrufen
            predictions = mqtt_client.latest_predictions
            if not predictions:
                return "Keine Vorhersagen verfügbar, um Feedback zu geben", 400
            
            combined_data = mqtt_client.combined_data
            logging.info(f"current combined_data: {combined_data}")

            features_df = mqtt_client.latest_features_df
            logging.info(f"current features_df: {features_df}")
            
            # Konvertierung von avg_time von UNIX-Zeitstempel in ein lesbares Format unter Verwendung von zeitzonengerechter datetime
            avg_time_unix = float(features_df['avg_time'].iloc[0]) if 'avg_time' in features_df else 0.0
            avg_time_readable = datetime.fromtimestamp(avg_time_unix, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            # Feedback-Daten erstellen
            feedback_data = {
                "temperature": float(features_df['temperature'].iloc[0]),
                "humidity": float(features_df['humidity'].iloc[0]),
                "co2": float(features_df['co2'].iloc[0]),
                "avg_time": avg_time_readable,
                "outdoor_temperature": float(features_df['ambient_temp'].iloc[0]),
                "accurate_prediction": int(request.form['accurate_prediction'])
            }

            # Header für die API-Anfrage
            headers = {
                "X-Api-Key": POST_API_KEY,
                "Content-Type": CONTENT_TYPE
            }

            # Feedback-Daten an die API senden
            response = requests.post(
                API_BASE_URL,
                headers=headers,
                json=feedback_data
            )

            logging.info(f"Payload gesendet: {feedback_data}")
            logging.info(f"API Antwort: {response.json()}")

            if response.status_code == 200:
                # latest_predictions löschen, um Speicherplatz freizugeben
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
            logging.error(f"Beim Abrufen von Vorhersagen ist ein unerwarteter Fehler aufgetreten: {e}")
            return str(e), 500


@app.route('/thank_you')
def thank_you():
    """
    Diese Funktion rendert die Dankeseite nach dem Absenden des Feedbacks.
    
    :return: gerenderte HTML-Seite
    """
    return render_template('thank_you.html')


@app.route('/contact')
def contact():
    """
    Diese Funktion rendert die Kontaktseite der Anwendung.
    
    :return: gerenderte HTML-Seite
    """
    return render_template('contact.html')


if __name__ == "__main__":

    # Anwendung im Debug-Modus starten
    app.run(debug=True)
