# Hinweis: Dieses Beispiel für ein inkrementelles Machine-Learning-Modell hat keine direkte Verbindung zur Anwendung `app.py`.
# Es dient lediglich zur Veranschaulichung eines Systems, das in Echtzeit aus den Sensor-Daten lernt und sich entsprechend anpasst.
# Das Modell wird kontinuierlich aktualisiert, um Vorhersagen basierend auf den aktuellen Daten zu verbessern.

import psycopg2
from river import compose, preprocessing, linear_model, metrics
import logging
import time
import yaml


def load_database_config(config_file):
    """
    Lädt die Konfiguration der Datenbank aus einer YAML-Konfigurationsdatei.

    :param config_file: Pfad zur YAML-Konfigurationsdatei
    :return: Datenbankkonfigurationsdaten als Dictionary
    """
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config['database']
    except FileNotFoundError:
        logging.error(f"Konfigurationsdatei '{config_file}' nicht gefunden")
        raise

# Datenbankkonfiguration laden
config = load_database_config('/SmartSystem/databaseConfig.yaml')

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mit der PostgreSQL-Datenbank verbinden
conn = psycopg2.connect(
    dbname=config['dbname'],
    user=config['user'],
    password=config['password'],
    host=config['host'],
    port=config['port']
)
cursor = conn.cursor()

# River-Modell für CO2-Vorhersage initialisieren
model = compose.Pipeline(
    preprocessing.StandardScaler(),
    linear_model.LinearRegression()
)
metric = metrics.R2()

# Kontinuierlich Daten abrufen und verarbeiten
while True:
    try:
        # Aktuellste Sensordaten aus PostgreSQL abfragen
        cursor.execute('SELECT "timestamp", temperature, humidity, co2_values, tvoc_values FROM public."SensorData" '
                       'ORDER BY "timestamp" DESC LIMIT 1;')
        latest_data = cursor.fetchone()

        if latest_data:
            timestamp, temperature, humidity, co2, tvoc = latest_data

            # Instanz für Vorhersage und Training vorbereiten
            instance = {'temperature': temperature, 'humidity': humidity, 'tvoc': tvoc}

            # CO2 mithilfe des Modells vorhersagen
            prediction = model.predict_one(instance)

            # Modell mit neuer Instanz und echtem Wert (CO2) aktualisieren
            model.learn_one(instance, co2)

            # Metrik mit echtem Wert und Vorhersage aktualisieren
            metric.update(co2, prediction)

            # Vorhersage und tatsächlichen CO2-Wert protokollieren
            logging.info(f"Timestamp: {timestamp}, Predicted CO2: {prediction:.2f}, Actual CO2: {co2}")

        else:
            logging.warning("No new data found in the database.")

    except Exception as e:
        logging.error(f"Error processing data: {e}")

    # Vor dem Abrufen neuer Daten eine bestimmte Zeit warten (z.B. 23 Sekunden)
    time.sleep(23)

# Datenbankverbindung schließen
cursor.close()
conn.close()
