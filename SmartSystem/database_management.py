from datetime import datetime, timedelta
from SmartSystem.config import load_database_config
import psycopg2
import logging
import yaml
import openpyxl


def connect_to_database():
    """
    Verbindet zur PostgreSQL-Datenbank unter Verwendung der Konfiguration aus der YAML-Datei.

    Returns:
        conn: Eine Verbindungsinstanz zur PostgreSQL-Datenbank.
    """
    try:
        # Datenbankkonfiguration aus der YAML-Datei laden
        config = load_database_config("database_config.yaml")

        # Verbindung zur PostgreSQL-Datenbank herstellen
        conn = psycopg2.connect(
            dbname=config["DBNAME"],  # Datenbankname
            user=config["DBUSER"],  # Benutzername
            password=config["DBPASSWORD"],  # Passwort
            host=config["DBHOST"],  # Hostname
            port=config["DBPORT"],  # Port
        )
        return conn
    except (psycopg2.Error, FileNotFoundError, yaml.YAMLError) as error:
        # Fehler beim Herstellen der Verbindung abfangen
        print(f"Fehler beim Verbinden zur Datenbank: {error}")
        return None


def close_connection(conn):
    """Schließt die PostgreSQL-Verbindung."""
    try:
        if conn:
            conn.close()
            logging.info("PostgreSQL-Verbindung geschlossen")
    except Exception as e:
        logging.error("Fehler beim Schließen der PostgreSQL-Verbindung: %s", str(e))


def get_latest_sensor_data():
    """
    Ruft die neuesten Sensordaten aus der Datenbank ab.

    Args:
        cursor: Ein Cursor-Objekt für die Datenbankverbindung.

    Returns:
        latest_data: Ein Tupel mit den neuesten Sensordaten (timestamp, temperature, humidity, co2_values, tvoc_values).
                     None, falls keine Daten vorhanden sind.
    """
    try:
        cursor = connect_to_database()
        # SQL-Abfrage, um die neuesten Sensordaten abzurufen
        cursor.execute(
            'SELECT "timestamp", temperature, humidity, co2_values, tvoc_values FROM public."SensorData" '
            'ORDER BY "timestamp" DESC LIMIT 1;'
        )

        # Die neuesten Sensordaten abrufen (einzelnes Tupel)
        latest_data = cursor.fetchone()

        return latest_data
    except Exception as e:
        logging.debug("Fehler beim Abrufen der neuesten Sensordaten: %s", str(e))
        return None


def get_sensor_data_last_hour():
    conn = None
    cursor = None
    sensor_data = None

    try:
        conn = connect_to_database()
        if conn is None:
            raise Exception("Verbindung zur Datenbank fehlgeschlagen")

        cursor = conn.cursor()

        # Calculate the start time for the last one hour
        last_hour_start = datetime.now() - timedelta(hours=1)

        # Execute SQL query using the cursor
        query = 'SELECT "timestamp", temperature, humidity, co2_values, tvoc_values FROM public."SensorData" WHERE "timestamp" >= %s'
        cursor.execute(query, (last_hour_start,))

        sensor_data = cursor.fetchall()

    except Exception as e:
        print(f"Error fetching sensor data: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return sensor_data


def get_sensor_data_last_month():
    conn = None
    cursor = None
    sensor_data = None

    try:
        conn = connect_to_database()
        if conn is None:
            raise Exception("Verbindung zur Datenbank fehlgeschlagen")

        cursor = conn.cursor()

        # Berechne den Startzeitpunkt für den Beginn des letzten Monats (30 Tage zurück)
        today = datetime.today()
        start_of_last_month = today - timedelta(days=30)

        # SQL-Abfrage ausführen, um Sensor-Daten für den letzten Monat abzurufen
        query = 'SELECT "timestamp", temperature, humidity, co2_values, tvoc_values FROM public."SensorData" WHERE "timestamp" >= %s'
        cursor.execute(query, (start_of_last_month,))

        sensor_data = cursor.fetchall()

    except Exception as e:
        print(f"Fehler beim Abrufen der Sensor-Daten: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return sensor_data
