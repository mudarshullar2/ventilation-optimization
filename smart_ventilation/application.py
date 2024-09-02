import base64
from flask_apscheduler import APScheduler
from flask import Flask, jsonify, make_response, redirect, render_template, request, session
import logging
import requests
from datetime import datetime, timedelta
from mqtt_client import MQTTClient
from api_config_loader import load_api_config
from datetime import datetime, timedelta
import numpy as np
import redis
import os


logging.basicConfig(level=logging.INFO)
base_dir = os.path.abspath(os.path.dirname(__file__))
static_folder = os.path.join(base_dir, 'static')

app = Flask(__name__, static_folder=static_folder)
#app.secret_key = secrets.token_hex(16)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))


# Pfad zu YAML-Konfigurationsdatei
config_file_path = 'api_config.yaml'

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


class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Diese Funktion wird aufgerufen, wenn auf die Route "/" zugegriffen wird. Sie dient dazu,
    Sensordaten, die über MQTT empfangen wurden, auszulesen und in einer Webseite anzuzeigen.
    Die Funktion handhabt sowohl GET- als auch POST-Anfragen, um Daten dynamisch darzustellen.

    Die Sensordaten beinhalten typischerweise Temperatur, Feuchtigkeit, CO2, TVOC, Umgebungstemperatur
    und Vorhersagen. Falls keine Daten vorhanden sind, werden Standardwerte verwendet.

    Bei einem Fehler während der Verarbeitung wird eine benutzerfreundliche Fehlermeldung zurückgegeben,
    und es wird protokolliert, was zum Fehler geführt hat.

    :return: Ein gerendertes Template mit Sensordaten oder eine Fehlermeldung bei Problemen.
    """
    try:
 
        # Sicherstellen, dass combined_data initialisiert ist und alle erwarteten Schlüssel enthält
        if not hasattr(mqtt_client, 'combined_data') or not mqtt_client.combined_data:
            # Standardwerte einrichten, falls combined_data nicht verfügbar oder leer ist
            sensor_data = {}
            temperature = 0
            humidity = 0
            co2 = 0
            tvoc = "Zurzeit nicht verfügbar"
            ambient_temp = 0
            predictions = {}
        else:
            # Sensordaten aus mqtt_client.combined_data sicher extrahieren
            sensor_data = mqtt_client.combined_data
            temperature = sensor_data.get("temperature", 0)
            humidity = sensor_data.get("humidity", 0)
            co2 = sensor_data.get("co2", 0)
            tvoc = sensor_data.get("tvoc", "Zurzeit nicht verfügbar")
            ambient_temp = sensor_data.get("ambient_temp", 0)
            predictions = sensor_data.get('predictions', {})

        # Das Template index.html mit den Daten rendern
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
        # Detailliertes Protokollieren des Fehlers und der Sensordaten zur Fehlerbehebung
        logging.error("Ein Fehler ist in index() aufgetreten: %s. Sensordaten: %s", str(e), str(mqtt_client.combined_data))
        return "Es gab ein Problem bei der Verarbeitung Ihrer Anfrage. Bitte aktualisieren Sie die Seite.", 500


@app.route("/plots")
def plots():
    """
    Generiert und rendert Echtzeit-Datenplots basierend auf den neuesten Sensordaten.
    """
    try:
        sensor_data = mqtt_client.get_latest_sensor_data()

        if sensor_data:
            
            unique_data = {}

            for data in sensor_data:
                time = data.get('time')
                if time and time not in unique_data:
                    unique_data[time] = {
                        'co2': data.get('co2'),
                        'temperature': data.get('temperature'),
                        'humidity': data.get('humidity'),
                        'tvoc': data.get('tvoc'),
                        'ambient_temp': data.get('ambient_temp')
                    }
                
                elif time:
                    if data.get('co2') is not None:
                        unique_data[time]['co2'] = data.get('co2')
                    if data.get('temperature') is not None:
                        unique_data[time]['temperature'] = data.get('temperature')
                    if data.get('humidity') is not None:
                        unique_data[time]['humidity'] = data.get('humidity')
                    if data.get('tvoc') is not None:
                        unique_data[time]['tvoc'] = data.get('tvoc')
                    if data.get('ambient_temp') is not None:
                        unique_data[time]['ambient_temp'] = data.get('ambient_temp')

            
            time_data = list(unique_data.keys())
            co2_data = [v['co2'] for v in unique_data.values()]
            temperature_data = [v['temperature'] for v in unique_data.values()]
            humidity_data = [v['humidity'] for v in unique_data.values()]
            tvoc_data = [v['tvoc'] for v in unique_data.values()]
            ambient_temp_data = [v['ambient_temp'] for v in unique_data.values()]

            
            return render_template(
                "plots.html",
                co2_data=co2_data,
                temperature_data=temperature_data,
                humidity_data=humidity_data,
                tvoc_data=tvoc_data,
                ambient_temp_data=ambient_temp_data,
                time_data=time_data
            )

        else:
            
            return render_template(
                "plots.html",
                co2_data=[],
                temperature_data=[],
                humidity_data=[],
                tvoc_data=[],
                ambient_temp_data=[],
                time_data=[]
            )
    except Exception as e:
        logging.error(f"Fehler in plots(): {e}")

    

def convert_to_serializable(obj):
    if isinstance(obj, (np.int64, np.int32, np.float64, np.float32)):
        return obj.item()
    raise TypeError("Nicht serialisierbares Objekt {} vom Typ {}".format(obj, type(obj)))


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

            logistic_prediction = predictions.get("Logistic Regression")
            user_feedback = int(request.form['accurate_prediction'])

            if user_feedback == 1:  # "Korrekt"
                accurate_prediction = int(logistic_prediction)
            else:  # "Nicht Korrekt"
                accurate_prediction = 1 - int(logistic_prediction)

            # Feedback-Daten erstellen
            feedback_data = {
                "temperature": float(features_df['temperature'].iloc[0]),
                "humidity": float(features_df['humidity'].iloc[0]),
                "co2": float(features_df['co2'].iloc[0]),
                "timestamp": combined_data["time"][-1],
                "outdoor_temperature": float(features_df['ambient_temp'].iloc[0]),
                "accurate_prediction": accurate_prediction
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
                # Store feedback data in the database
                #mqtt_client.store_feedback_data(feedback_data)

                last_prediction = mqtt_client.latest_predictions.get("Logistic Regression")
                logging.info(f"last_prediciton in feedback(): {last_prediction}")

                if isinstance(last_prediction, np.integer):
                    last_prediction = int(last_prediction)
                elif not isinstance(last_prediction, int):
                    last_prediction = int(last_prediction)

                return render_template('thank_you.html')
            else:
                return jsonify({"Meldung": "Keine Rückmeldung übermittelt", "status": response.status_code, "response": response.text}), 400

        except Exception as e:
            logging.error(f"feedback: Ein unerwarteter Fehler ist aufgetreten:: {e}")
            return jsonify({"Meldung": "Ein unerwarteter Fehler ist aufgetreten:", "Fehler:": str(e)}), 500
        
    else:
        try:
            predictions = mqtt_client.latest_predictions
            if not predictions:
                return render_template('feedback.html', error=True)
            
            predictions = mqtt_client.latest_predictions
            features_df = mqtt_client.latest_features_df

            return render_template('feedback.html', predictions=predictions, features=features_df.to_dict(orient='records')[0])

        except Exception as e:
            logging.error(f"feedback: Beim Abrufen von Vorhersagen ist ein unerwarteter Fehler aufgetreten: {e}")
            return str(e), 500


def get_data(timestamp):

    """
    Utility-Funktion zum Abrufen von Daten für einen bestimmten Zeitstempel
    """

    try:
        return mqtt_client.fetch_data(timestamp)
    except Exception as e:
        logging.error(f"get_data: Die Daten konnten nicht abgerufen werden: {e}")
        return {}


@app.route('/leaderboard', methods=['GET', 'POST'])
def leaderboard():
    try:
        if request.method == "POST":
            predictions = mqtt_client.latest_predictions
            logging.info(f"Vorhersage im Leaderboard: {predictions}")
            if not predictions:
                logging.error("Keine Vorhersagen verfügbar in latest_predictions")
                return render_template('leaderboard.html', error=True)
            
            last_prediction = predictions.get("Logistic Regression")
            logging.debug(f"Initial last_prediction: {last_prediction}, type: {type(last_prediction)}")

            if isinstance(last_prediction, np.integer):
                last_prediction = int(last_prediction)
            elif not isinstance(last_prediction, int):
                last_prediction = int(last_prediction)

            combined_data = mqtt_client.combined_data
            latest_date = combined_data["time"][-1]

            logging.info(f"latest_date: innerhalb der Leaderboard-Funktion {latest_date}")
            
            latest_date = datetime.strptime(latest_date, "%Y-%m-%d %H:%M")
            adjusted_date = latest_date - timedelta(minutes=1)

            adjusted_date_str = adjusted_date.strftime("%Y-%m-%d %H:%M")
            logging.info(f"Angepasstes Datum: {adjusted_date_str}")

            current_data = get_data(adjusted_date_str)
            logging.info(f"letzte current_data in der Leaderboard-Funktion: {current_data}")
            
            formatted_current_data = [{
                'timestamp': current_data.get('timestamp'),
                'co2_values': float(current_data.get('co2_values')) if current_data.get('co2_values') is not None else None,
                'temperature': float(current_data.get('temperature')) if current_data.get('temperature') is not None else None,
                'humidity': float(current_data.get('humidity')) if current_data.get('humidity') is not None else None,
            }]

            logging.info(f"Predictions Typ: {type(last_prediction)} und Wert: {last_prediction}")

            if last_prediction == 1:
                response = render_template('leaderboard2.html', current_data=formatted_current_data, future_data=None, adjusted_date_str=adjusted_date_str, error=False)
            else:
                response = render_template('leaderboard.html', current_data=formatted_current_data, future_data=None, adjusted_date_str=adjusted_date_str, error=False)
                
            return response
            
        elif request.method == "GET":
            predictions = mqtt_client.latest_predictions
            logging.info(f"last_prediction aus der Sitzung: {predictions}")
            
            if not predictions:
                logging.error("Keine Daten in der Sitzung verfügbar, bitte erst eine Vorhersage machen")
                return "Keine Daten verfügbar, bitte führen Sie eine Vorhersage durch.", 400
            
            combined_data = mqtt_client.combined_data
            logging.info(f"combined_data in leaderboard: {combined_data}")

            latest_date = combined_data["time"][-1]
            logging.info(f"latest_date: innerhalb der Leaderboard-Funktion {latest_date}")
            
            latest_date = datetime.strptime(latest_date, "%Y-%m-%d %H:%M")
            adjusted_date = latest_date - timedelta(minutes=1)

            adjusted_date_str = adjusted_date.strftime("%Y-%m-%d %H:%M")
            logging.info(f"Angepasstes Datum: {adjusted_date_str}")

            current_data = get_data(adjusted_date_str)
            logging.info(f"letzte current_data in der Leaderboard-Funktion: {current_data}")
            
            formatted_current_data = [{
                'timestamp': current_data.get('timestamp'),
                'co2_values': float(current_data.get('co2_values')) if current_data.get('co2_values') is not None else None,
                'temperature': float(current_data.get('temperature')) if current_data.get('temperature') is not None else None,
                'humidity': float(current_data.get('humidity')) if current_data.get('humidity') is not None else None,
            }]

            future_data_response = get_future_data(adjusted_date_str)

            if future_data_response.status_code != 200:
                return future_data_response
            
            future_data = future_data_response.get_json()
            logging.info(f"aktuellste future_data innerhalb der Leaderboard-Funktion: {future_data}")

            formatted_future_data = [{
                'timestamp': future_data.get('timestamp'),
                'co2_values': float(future_data.get('co2_values')) if future_data.get('co2_values') is not None else None,
                'temperature': float(future_data.get('temperature')) if future_data.get('temperature') is not None else None,
                'humidity': float(future_data.get('humidity')) if future_data.get('humidity') is not None else None,
            }]

            last_prediction = predictions.get("Logistic Regression")

            logging.info(f"Predictions Typ: {type(last_prediction)} und Wert: {last_prediction}")
            
            if last_prediction == 1:
                response = render_template('leaderboard2.html', current_data=formatted_current_data, future_data=formatted_future_data, adjusted_date_str=adjusted_date_str, error=False)
            else:
                response = render_template('leaderboard.html', current_data=formatted_current_data, future_data=formatted_future_data, adjusted_date_str=adjusted_date_str, error=False)
            return response

    except Exception as e:
        logging.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        return jsonify({"message": "Ein unerwarteter Fehler ist aufgetreten:", "Fehler:": str(e), "Hinweis": "Bitte zur Hauptseite zurückgehen"}), 500
    
    
@app.route('/future_data/<timestamp>')
def get_future_data(timestamp):
    try:
        # Überprüfen, ob die Anfrage Anmeldedaten enthält
        auth_header = request.headers.get('Authorization')
        if auth_header:
            auth_type, auth_credentials = auth_header.split(' ', 1)
            if auth_type.lower() == 'basic':
                benutzername, passwort = base64.b64decode(auth_credentials).decode('utf-8').split(':', 1)
                if benutzername != 'admin' or passwort != 'HJ|*fS1i':
                    return make_response('Verifizierung fehlgeschlagen', 401, {'WWW-Authenticate': 'Basic realm="Login erforderlich!"'})
            else:
                return make_response('Verifizierung fehlgeschlagen', 401, {'WWW-Authenticate': 'Basic realm="Login erforderlich!"'})
        else:
            return make_response('Verifizierung fehlgeschlagen', 401, {'WWW-Authenticate': 'Basic realm="Login erforderlich!"'})

        # Den eingehenden Zeitstempel analysieren
        timestamp_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M")
        
        # 5 Minuten zum Zeitstempel hinzufügen
        future_timestamp_dt = timestamp_dt + timedelta(minutes=5)
        future_timestamp_str = future_timestamp_dt.strftime("%Y-%m-%d %H:%M")
        
        logging.info(f"Abruf zukünftiger Daten für Zeitstempel: {future_timestamp_str}")
        
        # Zukünftige Daten sofort abrufen
        future_data = mqtt_client.fetch_future_data(future_timestamp_str)
        
        if not future_data:
            logging.info(f"Keine zukünftigen Daten für Zeitstempel verfügbar: {future_timestamp_str}")
            return jsonify({"Fehler": "Keine zukünftigen Daten verfügbar"}), 404
        
        formatted_future_data = {
            'timestamp': future_data.get('timestamp'),
            'co2_values': float(future_data.get('co2_values')) if future_data.get('co2_values') is not None else None,
            'temperature': float(future_data.get('temperature')) if future_data.get('temperature') is not None else None,
            'humidity': float(future_data.get('humidity')) if future_data.get('humidity') is not None else None,
        }

        logging.info(f"Zukünftige Daten wurden erfolgreich abgerufen: {formatted_future_data}")
        return jsonify(formatted_future_data)
    
    except Exception as e:
        logging.error(f"get_future_data: Fehler beim Abrufen von Zukunftsdaten: {e}")
        return jsonify({"Fehler": str(e)}), 500


@app.route('/save_analysis_data', methods=['POST'])
def save_analysis_data():
    try:
        data = request.json
        current_data = {
            'co2_values': data['current_co2'],
            'temperature': data['current_temperature'],
            'humidity': data['current_humidity']
        }
        future_data = {
            'co2_values': data['future_co2'],
            'temperature': data['future_temperature'],
            'humidity': data['future_humidity']
        }
        co2_change = data['co2_change']
        temperature_change = data['temperature_change']
        humidity_change = data['humidity_change']
        decision = data["decision"]

        mqtt_client.save_analysis_data(current_data, future_data, co2_change, temperature_change, humidity_change, decision)

        return jsonify({"message": "Daten erfolgreich gespeichert"}), 200
    except Exception as e:
        logging.error(f"save_analysis_data: Fehler beim Speichern von Analysedaten: {e}")
        return jsonify({"Fehler": str(e)}), 500


@app.route('/clear_session')
def clear_session():
    try:
        session.clear()
        return "Die Sitzungsdaten wurden erfolgreich gelöscht", 200
    except Exception as e:
        logging.error(f"clear_session: Fehler beim Löschen von Sitzungsdaten: {e}")
        return jsonify({"error": str(e)}), 500


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
    # app.run(debug=True)
    
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
