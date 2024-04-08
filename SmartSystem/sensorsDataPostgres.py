import random
from datetime import datetime
import schedule
import time
import logging
from SmartSystem.config import load_database_config
from SmartSystem.databaseManagement import connect_to_database, close_connection


# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

config = load_database_config("/SmartSystem/databaseConfig.yaml")


def generate_sensor_data():
    """
    Generiert zufällige Sensordaten.

    :return: Tuple mit Zeitstempel, Temperatur, Luftfeuchtigkeit, CO2-Werte und TVOC-Werte
    """
    temperature = round(random.uniform(10, 27), 2)
    humidity = round(random.uniform(30, 62), 2)
    co2_values = round(random.uniform(402, 600), 2)
    tvoc_values = round(random.uniform(100, 380), 2)
    timestamp = datetime.now()

    return timestamp, temperature, humidity, co2_values, tvoc_values


def insert_sensor_data(cursor):
    """
    Fügt zufällig generierte Sensordaten in die PostgreSQL-Datenbank ein.

    Args:
        cursor: Ein Cursor-Objekt für die Datenbankverbindung.
    """
    try:
        timestamp, temperature, humidity, co2_values, tvoc_values = generate_sensor_data()

        insert_query = (
            'INSERT INTO public."SensorData" ("timestamp", temperature, humidity, co2_values, tvoc_values) '
            "VALUES (%s, %s, %s, %s, %s)"
        )

        cursor.execute(
            insert_query, (timestamp, temperature, humidity, co2_values, tvoc_values)
        )
        cursor.connection.commit()

        logging.info(
            f"Daten eingefügt: Zeitstempel={timestamp}, Temperatur={temperature}"
            f", Luftfeuchtigkeit={humidity}, CO2={co2_values}, TVOC={tvoc_values}"
        )

    except Exception as e:
        logging.error(f"Fehler beim Einfügen von Daten in PostgreSQL: {e}")


def main():
    conn = None
    cursor = None

    try:
        conn = connect_to_database()
        cursor = conn.cursor()

        # Zeitplan für die Daten-Einfügeaufgabe
        schedule.every(20).seconds.do(insert_sensor_data, cursor=cursor)

        # Hauptschleife zum Ausführen des Zeitplans
        while True:
            schedule.run_pending()
            time.sleep(1)

    except Exception as e:
        logging.error(f"Allgemeiner Fehler in der Hauptausführung: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            close_connection(conn)


if __name__ == "__main__":
    main()
