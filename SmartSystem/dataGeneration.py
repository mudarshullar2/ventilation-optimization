import psycopg2
import joblib
import random
import logging
from datetime import datetime
from SmartSystem.config import load_database_config
from SmartSystem.databaseManagement import connect_to_database

# Datenbankkonfiguration laden
config_file = "./databaseConfig.yaml"
db_config = load_database_config(config_file)

# Das vortrainierte Machine-Learning-Modell laden
model = joblib.load("/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl")


def get_latest_sensor_data():
    try:
        conn = connect_to_database()
        cursor = conn.cursor()

        # Aktuellste Sensordaten abrufen
        query = (
            'SELECT "timestamp", temperature, humidity, co2_values, tvoc_values '
            'FROM public."SensorData" ORDER BY "timestamp" DESC LIMIT 100;'
        )
        cursor.execute(query)
        sensor_data = cursor.fetchall()

        conn.close()
        return sensor_data

    except psycopg2.Error as e:
        print("Fehler bei der Verbindung zur PostgreSQL-Datenbank:", e)
        return None


def generate_sensor_data():
    """
    Generiert zufällige Sensordaten.
    :return: Tuple mit Zeitstempel, Temperatur, Luftfeuchtigkeit, CO2-Werte und TVOC-Werte
    """
    try:
        temperature = round(random.uniform(10, 27), 2)
        humidity = round(random.uniform(30, 62), 2)
        co2_values = round(random.uniform(402, 600), 2)
        tvoc_values = round(random.uniform(100, 380), 2)
        timestamp = datetime.now()

        return timestamp, temperature, humidity, co2_values, tvoc_values
    except Exception as e:
        logging.error("Fehler beim Generieren von Sensordaten: %s", str(e))
        return None