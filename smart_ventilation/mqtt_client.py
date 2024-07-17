import time
import copy
import pandas as pd
import threading
import uuid
import joblib
import json
import logging
import datetime as dt
from datetime import datetime
from db.database_connection import load_config, connect_to_database
from api_config_loader import load_api_config
import paho.mqtt.client as mqtt

# Pfad zu YAML-Konfigurationsdatei
config_file_path = 'api_config.yaml'
db_config_path = 'db/db_config.yaml'
db = load_config(db_config_path)

# API-Konfiguration aus YAML-Datei laden
api_config = load_api_config(config_file_path)

# API-Schlüssel und Basis-URL extrahieren
CLOUD_SERVICE_URL = api_config["CLOUD_SERVICE_URL"]
USERNAME = api_config["USERNAME"]
PASSWORD = api_config["PASSWORD"]

class MQTTClient:
    """
    Diese Klasse stellt einen MQTT-Client dar, der Sensordaten sammelt,
    periodisch Vorhersagen trifft und die Daten speichert.
    """

    def __init__(self):
        """
        Initialisiert den MQTT-Client und lädt die Modelle.
        Startet auch Timer zur periodischen Vorhersage und Datenlöschung.
        """
        self.client = mqtt.Client()
        self.client.tls_set()
        self.client.username_pw_set(username=USERNAME, password=PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.parameters = {}
        self.latest_predictions = {}
        self.combined_data = {}
        self.data_points = []
        self.data_lock = threading.Lock()
        self.first_time = None
        self.first_topic_data = []

        self.conn = connect_to_database(db)

        logistic_regression_model = joblib.load('models/Logistic_Regression.pkl')
        random_forest_model = joblib.load('models/Random_Forest.pkl')

        self.models = {
            'Logistic Regression': logistic_regression_model,
            'Random Forest': random_forest_model
        }

        # Timer für periodische Vorhersagen
        self.prediction_timer = threading.Timer(1200, self.run_periodic_predictions)
        self.prediction_timer.start()

        # Timer für periodisches Löschen der Daten
        self.clear_timer = threading.Timer(5400, self.periodic_clear)
        self.clear_timer.start()

    def on_connect(self, client, userdata, flags, rc):
        """
        Wird aufgerufen, wenn der Client eine Verbindung zum Broker herstellt.
        Abonniert die relevanten Topics und prüft, ob der Vorhersage-Thread läuft.

        :param client: MQTT-Client-Instanz
        :param userdata: Benutzerdaten
        :param flags: Antwortflaggen vom Broker
        :param rc: Verbindungs-Result-Code
        """
        logging.info("Verbunden mit Ergebniscode" + str(rc))

        # Für Uhrzeit und TVOC
        self.client.subscribe("application/cefebad2-a2a8-49dd-a736-747453fedc6c/device/24e124707c501858/event/up")

        # Für Uhrzeit, Co2, Luftfeuchtigkeit, Temperaturen
        self.client.subscribe("application/cefebad2-a2a8-49dd-a736-747453fedc6c/device/0004a30b00fd0f5e/event/up")

        # Für Uhrzeit, Co2, Luftfeuchtigkeit, Temperaturen
        self.client.subscribe("application/cefebad2-a2a8-49dd-a736-747453fedc6c/device/0004a30b00fd09aa/event/up")

        # Für Außentemperaturen
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up")

    def on_message(self, client, userdata, msg):
        """
        Wird aufgerufen, wenn eine Nachricht empfangen wird.
        Verarbeitet die Nachricht und speichert die Sensordaten.

        :param client: MQTT-Client-Instanz
        :param userdata: Benutzerdaten
        :param msg: empfangene Nachricht
        """
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        def adjust_and_format_time(raw_time):
            utc_time = dt.datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S.%f%z")
            local_time = utc_time + dt.timedelta(hours=2)
            return local_time.strftime("%Y-%m-%d %H:%M")

        if topic.endswith("0004a30b00fd0f5e/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)

            humidity_values = payload["object"].get("humidity")
            temperature_values = payload["object"].get("temperature")
            co2_values = payload["object"].get("co2")

            if humidity_values is not None:
                self.combined_data.setdefault("humidity", []).append(round(humidity_values, 2))

            if temperature_values is not None:
                self.combined_data.setdefault("temperature", []).append(round(temperature_values, 2))

            if co2_values is not None:
                self.combined_data.setdefault("co2", []).append(round(co2_values, 2))

            data_point = {
                'time': formatted_time,
                'humidity': round(humidity_values, 2) if humidity_values is not None else None,
                'temperature': round(temperature_values, 2) if temperature_values is not None else None,
                'co2': round(co2_values, 2) if co2_values is not None else None
            }

            if all(value is not None for value in data_point.values()):
                logging.info(f"data_point is {data_point}")
                self.store_first_topic_data(data_point)

        elif topic.endswith("24e124707c501858/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)

            tvos_value = payload["object"].get("tvoc")

            if tvos_value is not None:
                self.combined_data.setdefault("tvoc", []).append(round(tvos_value, 2))

        elif topic.endswith("647fda000000aa92/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)

            ambient_temp_value = payload["object"].get("ambient_temp")

            if ambient_temp_value is not None:
                self.combined_data.setdefault("ambient_temp", []).append(round(ambient_temp_value, 2))

        # Überprüfen, ob alle erforderlichen Schlüssel vorhanden sind
        required_keys = {"time", "humidity", "temperature", "co2", "tvoc", "ambient_temp"}

        if all(key in self.combined_data for key in required_keys):
            self.collect_data(self.combined_data)

    def collect_data(self, combined_data):
        """
        Sammeln und speichern der Sensordaten.

        :param combined_data: kombinierten Sensordaten
        """
        try:
            max_length = max(len(combined_data[key]) for key in combined_data if isinstance(combined_data[key], list))
            for i in range(max_length):
                data = {}
                for key in combined_data:
                    if isinstance(combined_data[key], list) and i < len(combined_data[key]):
                        data[key] = combined_data[key][i]
                if data:
                    self.data_points.append(data)
                    logging.debug(f"data_points in der Funktion collect_data!: {data}")

        except Exception as e:
            logging.error(f"Unerwarteter Fehler bei der Datensammlung: {e}")
            logging.error(f"Inhalt der kombinierten Daten: {combined_data}")
            logging.error(f"Inhalt der Datenpunkte: {self.data_points}")

    def run_periodic_predictions(self):
        """
        Führt periodisch Vorhersagen durch, indem Sensordaten gesammelt und Modelle verwendet werden.
        """
        if self.data_points:
            try:
                # Deep Kopie der Datenpunkte erstellen
                data_points_copy = copy.deepcopy(self.data_points)
                df = pd.DataFrame(data_points_copy)
                logging.info("DataFrame wurde erfolgreich erstellt.")

                df['parsed_time'] = pd.to_datetime(df['time'])
                avg_time = df['parsed_time'].mean()
                logging.info("Zeitstempel-Parsing und Durchschnittsberechnung erfolgreich.")

                avg_data = df.mean(numeric_only=True).to_dict()
                avg_data['avg_time'] = avg_time.timestamp()
                logging.info("Vorbereitung der Durchschnittsdaten erfolgreich.")

                avg_data['hour'] = avg_time.hour
                avg_data['day_of_week'] = avg_time.dayofweek
                avg_data['month'] = avg_time.month

                # Merkmale für die Vorhersage vorbereiten
                features_df = pd.DataFrame([avg_data])
                logging.info("Merkmale für die Vorhersage vorbereitet: %s", features_df)

                # Reihenfolge der DataFrame-Spalten an die Trainingsreihenfolge anpassen
                correct_order = ['co2', 'temperature', 'humidity', 'tvoc', 'ambient_temp', 'hour', 'day_of_week', 'month']
                features_df = features_df[correct_order]
                features_array = features_df.to_numpy()

                # Spaltenreihenfolge für das zweite Modell anpassen
                restricted_model_order = ['co2', 'temperature']
                restricted_features_df = features_df[restricted_model_order]
                restricted_features_array = restricted_features_df.to_numpy()

                # Vorhersagen mit jedem Modell erstellen
                predictions = {}
                for name, model in self.models.items():
                    if 'Random Forest' in name:
                        predictions[name] = model.predict(restricted_features_array)[0]
                    else:
                        predictions[name] = model.predict(features_array)[0]

                self.combined_data['predictions'] = predictions
                self.latest_predictions = predictions
                logging.info(f"latest predictions are: {self.latest_predictions}")

                # Einen eindeutigen Bezeichner zur Vorhersage hinzufügen
                prediction_id = str(uuid.uuid4())
                self.latest_predictions['id'] = prediction_id

                # features_df zur späteren Verwendung im Feedback speichern
                self.latest_features_df = features_df

                data_points_copy.clear()
            except Exception as e:
                logging.error(f"Fehler während der Verarbeitung der Vorhersagen: {e}")
        else:
            logging.info("In den letzten 20 Minuten wurden keine Daten gesammelt.")

        # Timer für die nächste Ausführung neu starten
        self.prediction_timer = threading.Timer(1200, self.run_periodic_predictions)
        self.prediction_timer.start()

    def periodic_clear(self):
        """
        Löscht periodisch die gesammelten Daten alle 1.5 Stunden.
        """
        with self.data_lock:
            self.data_points.clear()
            self.combined_data.clear()
            self.latest_predictions.clear()
        logging.info("Datenpunkte und kombinierte Daten wurden nach 1.5 Stunden gelöscht.")
        logging.info(f"Inhalt der Datenpunkte nach dem Löschen: {self.data_points}")
        logging.info(f"Inhalt der kombinierten Daten nach dem Löschen: {self.combined_data}")

        # Timer für die nächste Ausführung neu starten
        self.clear_timer = threading.Timer(5400, self.periodic_clear)
        self.clear_timer.start()

    def store_first_topic_data(self, data_point):
        """
        Speichert die Sensordaten aus dem ersten Thema in der PostgreSQL-Datenbank 
        und stellt die Vollständigkeit der Daten sicher.
        """
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                if all(data_point.get(key) is not None for key in ['time', 'co2', 'temperature', 'humidity']):
                    query = """
                        INSERT INTO classroom_environmental_data
                        (timestamp, co2_values, temperature, 
                        humidity, classroom_number)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (
                        data_point['time'], 
                        data_point['co2'], 
                        data_point['temperature'],
                        data_point['humidity'], 
                        '2.09' # Feste Besprechungsraum
                    ))
                self.conn.commit()
                # Datenpunkt löschen, um Speicherplatz freizugeben
                data_point = None
            except Exception as e:
                logging.error(f"Fehler beim Speichern von Daten in der Datenbank: {e}")
                self.conn.rollback()
            finally:
                cursor.close()

    def initialize(self):
        """
        Initialisiert die Verbindung zum MQTT-Broker und startet den Loop.
        """
        self.client.connect(CLOUD_SERVICE_URL, 8883)
        self.client.loop_start()
