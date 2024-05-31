import paho.mqtt.client as mqtt
import pandas as pd
import threading
import copy
import joblib
import json
import logging
import time
import datetime as dt
from api_config_loader import load_api_config

# Pfad zu Ihrer YAML-Konfigurationsdatei
config_file_path = 'smart-ventilation/api_config.yaml'

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

        # Modelle laden
        self.models = {
            'Logistic Regression': joblib.load('smart-ventilation/models/Logistic_Regression.pkl'),
            'Decision Tree': joblib.load('smart-ventilation/models/Decision_Tree.pkl'),
            'Random Forest': joblib.load('smart-ventilation/models/Random_Forest.pkl')
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
        logging.info("Connected with result code " + str(rc))
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up")
        self.client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up")

        if not self.prediction_thread.is_alive():
            logging.warning("Prediction thread has stopped, restarting...")
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

        #elif topic.endswith("647fda000000aa92/event/up"):
        #    formatted_time = adjust_and_format_time(payload["time"])
        #    self.combined_data.setdefault("time", []).append(formatted_time)
        #    self.combined_data.setdefault("ambient_temp", []).append(round(payload["object"]["ambient_temp"], 2))

        elif topic.endswith("24e124707c481005/event/up"):
            formatted_time = adjust_and_format_time(payload["time"])
            tvos_value = payload["object"].get("tvoc")
            self.combined_data.setdefault("time", []).append(formatted_time)
            if tvos_value is not None:
                self.combined_data.setdefault("tvoc", []).append(tvos_value)

        # Überprüfen, ob alle erforderlichen Schlüssel vorhanden sind
        required_keys = {"time", "humidity", "temperature", "co2", "tvoc"}
        if all(key in self.combined_data for key in required_keys):
            self.collect_data(self.combined_data)
            logging.info("Alle erforderlichen Daten sind vorhanden.")


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
        except Exception as e:
            logging.error(f"Unerwarteter Fehler bei der Datensammlung: {e}")
            logging.error(f"Inhalt der kombinierten Daten: {combined_data}")
            logging.error(f"Inhalt der Datenpunkte: {self.data_points}")


    def run_periodic_predictions(self):
        """
        Führt periodisch Vorhersagen durch, indem Sensordaten gesammelt und Modelle verwendet werden.
        """
        while self.thread_alive:
            # 45 Minuten warten
            time.sleep(2700)
            if self.data_points:
                try:
                    # Tiefe Kopie der Datenpunkte erstellen
                    data_points_copy = copy.deepcopy(self.data_points)
                    df = pd.DataFrame(data_points_copy)
                    logging.info("DataFrame wurde erfolgreich erstellt.")

                    df['parsed_time'] = pd.to_datetime(df['time'])
                    avg_time = df['parsed_time'].mean()
                    logging.info("Zeitstempel-Parsing und Durchschnittsberechnung erfolgreich.")

                    avg_data = df.mean(numeric_only=True).to_dict()
                    avg_data['avg_time'] = avg_time.timestamp()
                    logging.info("Vorbereitung der Durchschnittsdaten erfolgreich.")
                    
                    # Prepare features for prediction
                    features_df = pd.DataFrame([avg_data])
                    logging.info("Features prepared for prediction: %s", features_df)
                    
                    # Generate predictions with each model
                    predictions = {name: model.predict(features_df)[0] for name, model in self.models.items()}
                    self.combined_data['predictions'] = predictions
                    self.latest_predictions = predictions

                    # Store features_df for later use in feedback
                    self.latest_features_df = features_df

                    data_points_copy.clear()
                except Exception as e:
                    logging.error(f"Fehler während der Verarbeitung der Vorhersagen: {e}")
            else:
                logging.info("In den letzten 45 Minuten wurden keine Daten gesammelt.")


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
            # 2 Stunden warten
            time.sleep(3600)
            with self.data_lock:
                self.data_points.clear()
                self.combined_data.clear()
            logging.info("Datenpunkte und kombinierte Daten wurden nach 2 Stunden gelöscht.")
            logging.info(f"Inhalt der Datenpunkte nach dem Löschen: {self.data_points}")
            logging.info(f"Inhalt der kombinierten Daten nach dem Löschen: {self.combined_data}")


    def initialize(self):
        """
        Initialisiert die Verbindung zum MQTT-Broker und startet den Loop.
        """
        self.client.connect(CLOUD_SERVICE_URL, 8883)
        self.client.loop_start()
