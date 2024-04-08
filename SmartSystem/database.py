import psycopg2
import logging
from SmartSystem.config import load_database_config


def connect_to_database():
    """
    Verbindet zur PostgreSQL-Datenbank unter Verwendung der Konfiguration aus der YAML-Datei.

    Returns:
        conn: Eine Verbindungsinstanz zur PostgreSQL-Datenbank.
    """
    # Datenbankkonfiguration aus der YAML-Datei laden
    config = load_database_config("/SmartSystem/databaseConfig.yaml")

    # Verbindung zur PostgreSQL-Datenbank herstellen
    conn = psycopg2.connect(
        dbname=config["dbname"],  # Datenbankname
        user=config["user"],  # Benutzername
        password=config["password"],  # Passwort
        host=config["host"],  # Hostname
        port=config["port"],  # Port
    )
    return conn


def close_connection(conn):
    """Schließt die PostgreSQL-Verbindung."""
    if conn:
        conn.close()
        logging.info("PostgreSQL-Verbindung geschlossen")


def get_latest_sensor_data(cursor):
    """
    Ruft die neuesten Sensordaten aus der Datenbank ab.

    Args:
        cursor: Ein Cursor-Objekt für die Datenbankverbindung.

    Returns:
        latest_data: Ein Tupel mit den neuesten Sensordaten (timestamp, temperature, humidity, co2_values, tvoc_values).
                     None, falls keine Daten vorhanden sind.
    """
    # SQL-Abfrage, um die neuesten Sensordaten abzurufen
    cursor.execute(
        'SELECT "timestamp", temperature, humidity, co2_values, tvoc_values FROM public."SensorData" '
        'ORDER BY "timestamp" DESC LIMIT 1;'
    )

    # Die neuesten Sensordaten abrufen (einzelnes Tupel)
    latest_data = cursor.fetchone()

    return latest_data
