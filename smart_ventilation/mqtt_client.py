from db.database_connection import load_config, connect_to_database
import paho.mqtt.client as mqtt
import pandas as pd
import threading
import uuid
import copy
import joblib
import json
import logging
import time
import datetime as dt
from api_config_loader import load_api_config

# Pfad zu YAML-Konfigurationsdatei
config_file_path = '/Users/mudarshullar/Desktop/ventilation-optimization/api_config.yaml'
db_config_path = 'smart_ventilation/db/db_config.yaml'
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
        self.prediction_thread = threading.Thread(target=self.run_periodic_predictions)
        self.prediction_thread.start()
        self.data_lock = threading.Lock()

        self.clearing_thread = threading.Thread(target=self.periodic_clear)
        self.clearing_thread.start()

        self.conn = connect_to_database(db)

        # Modelle laden
        self.models = {
            'Logistic Regression': joblib.load('smart_ventilation/models/Logistic_Regression.pkl'),
            'Decision Tree': joblib.load('smart_ventilation/models/Decision_Tree.pkl'),
            'Random Forest': joblib.load('smart_ventilation/models/Random_Forest.pkl')
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
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up")

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
        
        if topic.endswith("0004a30b01045883/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)
            self.combined_data.setdefault("humidity", []).append(round(payload["object"]["humidity"], 2))
            self.combined_data.setdefault("temperature", []).append(round(payload["object"]["temperature"], 2))
            self.combined_data.setdefault("co2", []).append(round(payload["object"]["co2"], 2))

            formatted_time = adjust_and_format_time(payload["time"])
            self.combined_data.setdefault("time", []).append(formatted_time)
            ambient_temp = 14
            self.combined_data.setdefault("ambient_temp", []).append(ambient_temp)
            tvos_value = 100
            self.combined_data.setdefault("tvoc", []).append(tvos_value)

        #elif topic.endswith("647fda000000aa92/event/up"):
        #    formatted_time = adjust_and_format_time(payload["time"])
        #    self.combined_data.setdefault("time", []).append(formatted_time)
        #    self.combined_data.setdefault("ambient_temp", []).append(round(payload["object"]["ambient_temp"], 2))

        #elif topic.endswith("24e124707c481005/event/up"):
        #    formatted_time = adjust_and_format_time(payload["time"])
        #    tvos_value = payload["object"].get("tvoc")
        #    self.combined_data.setdefault("time", []).append(formatted_time)
        #    if tvos_value is not None:
        #        self.combined_data.setdefault("tvoc", []).append(tvos_value)

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
                    logging.debug(f"data_points within collect_data function!: {data}")
                    self.store_into_db()
        except Exception as e:
            logging.error(f"Unerwarteter Fehler bei der Datensammlung: {e}")
            logging.error(f"Inhalt der kombinierten Daten: {combined_data}")
            logging.error(f"Inhalt der Datenpunkte: {self.data_points}")


    def run_periodic_predictions(self):
        """
        Führt periodisch Vorhersagen durch, indem Sensordaten gesammelt und Modelle verwendet werden.
        """
        while self.thread_alive:
            # 10 Minuten warten
            time.sleep(720)
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

                    # Merkmale für die Vorhersage vorbereiten
                    features_df = pd.DataFrame([avg_data])
                    logging.info("Merkmale für die Vorhersage vorbereitet: %s", features_df)
                    
                    # Reihenfolge der DataFrame-Spalten an die Trainingsreihenfolge anpassen
                    correct_order = ['temperature', 'co2', 'tvoc', 'humidity', 'ambient_temp']
                    features_df = features_df[correct_order]
                    features_array = features_df.to_numpy()

                    # Vorhersagen mit jedem Modell erstellen
                    predictions = {name: model.predict(features_array)[0] for name, model in self.models.items()}
                    self.combined_data['predictions'] = predictions
                    self.latest_predictions = predictions

                    # Einen eindeutigen Bezeichner zur Vorhersage hinzufügen
                    prediction_id = str(uuid.uuid4())
                    self.latest_predictions['id'] = prediction_id

                    # features_df zur späteren Verwendung im Feedback speichern
                    self.latest_features_df = features_df

                    data_points_copy.clear()
                except Exception as e:
                    logging.error(f"Fehler während der Verarbeitung der Vorhersagen: {e}")
            else:
                logging.info("In den letzten 10 Minuten wurden keine Daten gesammelt.")


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
        Löscht periodisch die gesammelten Daten alle 20 Minuten.
        """
        while True:
            # 1.5 Stunden warten
            time.sleep(5400)
            with self.data_lock:
                self.data_points.clear()
                self.combined_data.clear()
            logging.info("Datenpunkte und kombinierte Daten wurden nach 1.5 Stunden gelöscht.")
            logging.info(f"Inhalt der Datenpunkte nach dem Löschen: {self.data_points}")
            logging.info(f"Inhalt der kombinierten Daten nach dem Löschen: {self.combined_data}")
    

    def store_into_db(self):
        """Stores collected sensor data into the PostgreSQL database, ensuring data completeness."""
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                # Iterate through each collected data point
                for data in self.data_points:
                    # Ensure all required fields are present and contain no None values
                    if all(data.get(key) is not None for key in ['time', 'co2', 'temperature', 'humidity', 'ambient_temp', 'tvoc']):
                        query = """
                            INSERT INTO classroom_environment_data
                            (timestamp, co2_values, temperature, humidity, outdoor_temperature, tvoc_values, classroom_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        # Execute the insert query with the required values
                        cursor.execute(query, (
                            data['time'], 
                            data['co2'], 
                            data['temperature'],
                            data['humidity'], 
                            data['ambient_temp'], 
                            data['tvoc'],
                            '10c'  # Fixed classroom number '10c'
                        ))
                # Commit the transaction to ensure data is saved to the database
                self.conn.commit()
                logging.info("Data successfully stored in the database.")
            except Exception as e:
                logging.error(f"Error storing data in the database: {e}")
                self.conn.rollback()
            finally:
                cursor.close()
    

    def fetch_data(self, timestamp):
        """
        Helper function to fetch data based on a timestamp, considering the previous 30 minutes.
        Retrieves data from the PostgreSQL database and calculates the average of the values.
        """
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                # Log the incoming timestamp to check its format
                logging.info(f"Fetching data for timestamp: {timestamp}")

                # Query to fetch data within 30 minutes prior to the given timestamp
                query = """
                    SELECT 
                        AVG(co2_values) as co2_values,
                        AVG(temperature) as temperature,
                        AVG(humidity) as humidity,
                        AVG(outdoor_temperature) as outdoor_temperature,
                        AVG(tvoc_values) as tvoc_values
                    FROM classroom_environment_data
                    WHERE timestamp >= (CAST(%s AS timestamp) - INTERVAL '30 minutes')
                    AND timestamp <= CAST(%s AS timestamp);
                """
                logging.info(f"Executing query with timestamp: {timestamp}")
                cursor.execute(query, (timestamp, timestamp))

                result = cursor.fetchone()
                logging.info(f"Query successful, fetched data: {result}")

                # Prepare the result in a format that matches the expected output
                if result:
                    averaged_data = {
                        'timestamp': timestamp,
                        'co2_values': result[0],
                        'temperature': result[1],
                        'humidity': result[2],
                        'outdoor_temperature': result[3],
                        'tvoc_values': result[4]
                    }
                else:
                    averaged_data = {}

                return averaged_data

            except Exception as e:
                # Log any errors that occur during the query execution
                logging.error(f"Error fetching data from database: {e}")
                return {}
            finally:
                # Ensure cursor is closed after operation
                cursor.close()


    def fetch_future_data(self, timestamp):
        """
        Helper function to fetch data based on a timestamp, considering the next 10 minutes.
        Retrieves data from the PostgreSQL database and calculates the average of the values.
        """
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                # Log the incoming timestamp to check its format
                logging.info(f"Fetching future data starting from timestamp: {timestamp}")

                # Query to fetch data starting from the given timestamp
                query = """
                    SELECT 
                        AVG(co2_values) as co2_values,
                        AVG(temperature) as temperature,
                        AVG(humidity) as humidity,
                        AVG(outdoor_temperature) as outdoor_temperature,
                        AVG(tvoc_values) as tvoc_values
                    FROM classroom_environment_data
                    WHERE timestamp >= CAST(%s AS timestamp);
                """
                logging.info(f"Executing query with timestamp: {timestamp}")
                cursor.execute(query, (timestamp,))

                result = cursor.fetchone()
                logging.info(f"Query successful, fetched data: {result}")

                # Prepare the result in a format that matches the expected output
                if result:
                    averaged_data = {
                        'timestamp': timestamp,
                        'co2_values': float(result[0]) if result[0] is not None else None,
                        'temperature': float(result[1]) if result[1] is not None else None,
                        'humidity': float(result[2]) if result[2] is not None else None,
                        'outdoor_temperature': float(result[3]) if result[3] is not None else None,
                        'tvoc_values': float(result[4]) if result[4] is not None else None
                    }
                else:
                    averaged_data = {
                        'timestamp': timestamp,
                        'co2_values': None,
                        'temperature': None,
                        'humidity': None,
                        'outdoor_temperature': None,
                        'tvoc_values': None
                    }

                return averaged_data

            except Exception as e:
                # Log any errors that occur during the query execution
                logging.error(f"Error fetching future data from database: {e}")
                return {
                    'timestamp': timestamp,
                    'co2_values': None,
                    'temperature': None,
                    'humidity': None,
                    'outdoor_temperature': None,
                    'tvoc_values': None
                }
            finally:
                # Ensure cursor is closed after operation
                cursor.close()


    def initialize(self):
        """
        Initialisiert die Verbindung zum MQTT-Broker und startet den Loop.
        """
        self.client.connect(CLOUD_SERVICE_URL, 8883)
        self.client.loop_start()
