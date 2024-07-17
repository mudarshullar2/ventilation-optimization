from db.database_connection import load_config, connect_to_database
import paho.mqtt.client as mqtt
import pandas as pd
import threading
import uuid
import copy
import joblib
import json
import logging
import datetime as dt
from datetime import datetime
from api_config_loader import load_api_config
from datetime import datetime
import pytz


# Pfad zu YAML-Konfigurationsdatei
config_file_path = 'api_config.yaml'
db_config_path = 'db/db_config.yaml'
db = load_config(db_config_path)
berlin_tz = pytz.timezone('Europe/Berlin')

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
        Startet auch Threads zur periodischen Vorhersage und Datenlöschung.
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
        self.thread_alive = True
        self.prediction_event = threading.Event()
        self.clear_event = threading.Event()
        self.prediction_thread = threading.Thread(target=self.run_periodic_predictions)
        self.prediction_thread.start()
        self.data_lock = threading.Lock()
        self.first_time = None
        self.first_topic_data = []

        self.clearing_thread = threading.Thread(target=self.periodic_clear)
        self.clearing_thread.start()

        self.conn = connect_to_database(db)

        logistic_regression_model = joblib.load('models/Logistic_Regression.pkl')
        random_forest_model = joblib.load('models/Random_Forest.pkl')

        self.models = {
            'Logistic Regression': logistic_regression_model,
            'Random Forest': random_forest_model
            }

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

        if not self.prediction_thread.is_alive():
            logging.warning("Der Thread wurde angehalten und wird neu gestartet...")
            self.restart_thread()

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
        while self.thread_alive:
            # 20 Minuten warten
            self.prediction_event.wait(1200)
            if not self.thread_alive:
                break
            self.prediction_event.clear()
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

    def restart_thread(self):
        """
        Startet den Vorhersage-Thread neu, falls er gestoppt wurde.
        """
        self.thread_alive = True
        self.prediction_thread = threading.Thread(target=self.run_periodic_predictions)
        self.prediction_thread.start()
        
        logging.info("Vorhersage-Thread erfolgreich neu gestartet.")

    def get_latest_sensor_data(self):
        """
        Gibt die neuesten gesammelten Sensordaten zurück.

        :return: Kopie der Datenpunkte
        """
        return self.data_points.copy()

    def periodic_clear(self):
        """
        Löscht periodisch die gesammelten Daten alle 1.5 Stunden.
        """
        while True:
            # 1.5 Stunden warten
            self.clear_event.wait(5400)
            self.clear_event.clear()
            with self.data_lock:
                self.data_points.clear()
                self.combined_data.clear()
                self.latest_predictions.clear()
            logging.info("Datenpunkte und kombinierte Daten wurden nach 1.5 Stunden gelöscht.")
            logging.info(f"Inhalt der Datenpunkte nach dem Löschen: {self.data_points}")
            logging.info(f"Inhalt der kombinierten Daten nach dem Löschen: {self.combined_data}")

    def store_first_topic_data(self, data_point):
        """
        Speichert die Sensordaten aus dem ersten Thema in der PostgreSQL-Datenbank 
        und stellt die Vollständigkeit der Daten sicher
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

    def fetch_data(self, timestamp):
        """
        Hilfsfunktion zum Abrufen von Daten auf der Grundlage eines Zeitstempels, 
        unter Berücksichtigung der letzten 30 Minuten.
        Ruft Daten aus der PostgreSQL-Datenbank ab und berechnet den Durchschnitt der Werte.
        """
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                timestamp = datetime.fromisoformat(timestamp)
                utc_datetime = pytz.utc.localize(timestamp)  # Assuming the stored timestamps are in UTC
                berlin_datetime = utc_datetime.astimezone(berlin_tz)

                # Den eingehenden Zeitstempel protokollieren, um sein Format zu überprüfen
                logging.info(f"Abrufen von Daten für Zeitstempel: {berlin_datetime}")

                # Abfrage zum Abruf von Daten innerhalb von 30 Minuten vor dem angegebenen Zeitstempel
                query = """ 
                SELECT 
                    AVG(co2_values) as co2_values, 
                    AVG(temperature) as temperature, 
                    AVG(humidity) as humidity
                FROM classroom_environmental_data 
                WHERE 
                    timestamp > CAST(%s AS timestamp); 
                """

                logging.info(f"Abfrage mit Zeitstempel ausführen:{berlin_datetime}")
                cursor.execute(query, (berlin_datetime,))

                result = cursor.fetchone()
                logging.info(f"Abfrage erfolgreich, Daten abgerufen:{result}")

                # Aufbereitung des Ergebnisses in einem Format, das der erwarteten Ausgabe entspricht
                if result:
                    averaged_data = {
                        'timestamp': berlin_datetime.strftime("%Y-%m-%d %H:%M"),
                        'co2_values': result[0],
                        'temperature': result[1],
                        'humidity': result[2],
                    }
                else:
                    averaged_data = {}
                return averaged_data

            except Exception as e:
                # Protokollierung von Fehlern, die während der Ausführung der Abfrage auftreten
                logging.error(f"Fehler beim Abrufen von Daten aus der Datenbank: {e}")

                return {}
            finally:
                # Cursor muss nach dem Vorgang geschlossen werden
                cursor.close()

    def fetch_future_data(self, timestamp):
        """
        Hilfsfunktion zum Abrufen von Daten auf der Grundlage eines Zeitstempels, 
        unter Berücksichtigung der nächsten 10 Minuten.
        Ruft Daten aus der PostgreSQL-Datenbank ab und berechnet den Durchschnitt der Werte
        """
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                timestamp = datetime.fromisoformat(timestamp)
                utc_datetime = pytz.utc.localize(timestamp)
                berlin_datetime = utc_datetime.astimezone(berlin_tz)
                logging.info(f"Abruf zukünftiger Daten ab dem Zeitstempel: {berlin_datetime}")

                # Den eingehenden Zeitstempel protokollieren, um sein Format zu überprüfen
                #adjusted_timestamp = timestamp + timedelta(hours=2)
                logging.info(f"Abruf zukünftiger Daten ab dem Zeitstempel: {timestamp}")

                # Abfrage zum Abrufen von Daten ab dem angegebenen Zeitstempel
                query = """
                    SELECT 
                        AVG(co2_values) as co2_values,
                        AVG(temperature) as temperature,
                        AVG(humidity) as humidity
                    FROM classroom_environmental_data
                    WHERE timestamp > CAST(%s AS timestamp);
                """
                logging.info(f"Abfrage mit Zeitstempel ausführen: {berlin_datetime}")
                cursor.execute(query, (berlin_datetime,))

                result = cursor.fetchone()
                logging.info(f"Abfrage erfolgreich, Daten geholt:{result}")

                # Aufbereitung des Ergebnisses in einem Format, das der erwarteten Ausgabe entspricht
                if result:
                    averaged_data = {
                        'timestamp': berlin_datetime.strftime("%Y-%m-%d %H:%M"),
                        'co2_values': float(result[0]) if result[0] is not None else None,
                        'temperature': float(result[1]) if result[1] is not None else None,
                        'humidity': float(result[2]) if result[2] is not None else None,
                    }
                else:
                    averaged_data = {
                        'timestamp': berlin_datetime.strftime("%Y-%m-%d %H:%M"),
                        'co2_values': None,
                        'temperature': None,
                        'humidity': None,
                    }

                return averaged_data

            except Exception as e:
                # Protokollierung von Fehlern, die während der Ausführung der Abfrage auftreten
                logging.error(f"Fehler beim Abrufen von Zukunftsdaten aus der Datenbank: {e}")
                return {
                    'timestamp': berlin_datetime.strftime("%Y-%m-%d %H:%M"),
                    'co2_values': None,
                    'temperature': None,
                    'humidity': None,
                }
            finally:
                # Cursor muss nach dem Vorgang geschlossen werden
                cursor.close()

    def save_analysis_data(self, current_data, future_data, co2_change, temperature_change, humidity_change, decision):
        """
        Speichert die aktuellen und zukünftigen Umweltdaten sowie die prozentualen Änderungen in der Datenbank.
        
        :param current_data: Aktuelle Umweltdaten
        :param future_data: Zukünftige Umweltdaten
        :param co2_change: Prozentuale Änderung des CO2-Wertes
        :param temperature_change: Prozentuale Änderung der Temperatur
        :param humidity_change: Prozentuale Änderung der Luftfeuchtigkeit
        """
        try:
            cursor = self.conn.cursor()

            query = """
            INSERT INTO environmental_data_analysis (
                    timestamp, current_co2, future_co2, co2_change, 
                    current_temperature, future_temperature, temperature_change, 
                    current_humidity, future_humidity, humidity_change, decision
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            logging.info(f"Statistische Auswertungen werden gespeichert!")

            timestamp = datetime.now()
            
            values = (
                timestamp,
                current_data['co2_values'], future_data['co2_values'], co2_change,
                current_data['temperature'], future_data['temperature'], temperature_change,
                current_data['humidity'], future_data['humidity'], humidity_change, decision
            )
            
            cursor.execute(query, values)

            self.conn.commit()

            cursor.close()

            logging.info("Daten in der Tabelle environmental_data_analysis erfolgreich gespeichert")

        except Exception as e:
            logging.error(f"Fehler beim Speichern von Daten in der Datenbank: {e}")

    def clear_predictions(self):
        """
        Löscht alte Vorhersagen
        """
        with self.data_lock:
            logging.info("Alte Vorhersagen werden gelöscht!")
            self.latest_predictions.clear()
            logging.info(f"lates_prediction: {self.latest_predictions}")

    def initialize(self):
        """
        Initialisiert die Verbindung zum MQTT-Broker und startet den Loop.
        """
        self.client.connect(CLOUD_SERVICE_URL, 8883)
        self.client.loop_start()
