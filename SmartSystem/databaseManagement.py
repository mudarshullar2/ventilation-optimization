import psycopg2
import logging
from SmartSystem.config import load_database_config


def connect_to_database():
    """
    Verbindet zur PostgreSQL-Datenbank unter Verwendung der Konfiguration aus der YAML-Datei.

    Returns:
        conn: Eine Verbindungsinstanz zur PostgreSQL-Datenbank.
    """
    try:
        # Datenbankkonfiguration aus der YAML-Datei laden
        config = load_database_config("./databaseConfig.yaml")

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


def get_latest_sensor_data(cursor):
    """
    Ruft die neuesten Sensordaten aus der Datenbank ab.

    Args:
        cursor: Ein Cursor-Objekt für die Datenbankverbindung.

    Returns:
        latest_data: Ein Tupel mit den neuesten Sensordaten (timestamp, temperature, humidity, co2_values, tvoc_values).
                     None, falls keine Daten vorhanden sind.
    """
    try:
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
