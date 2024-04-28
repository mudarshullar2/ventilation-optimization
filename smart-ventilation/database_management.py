import requests
import psycopg2
import logging
import yaml
from datetime import datetime, timedelta
from load_api import load_api_config
from config import load_database_config

# Pfad zu Ihrer YAML-Konfigurationsdatei
config_file_path = 'smart-ventilation/api_config.yaml'

# API-Konfiguration aus YAML-Datei laden
api_config = load_api_config(config_file_path)

# API-Schlüssel und Basis-URL extrahieren
READ_API_KEY = api_config['READ_API_KEY']
POST_DELETE_API_KEY = api_config['POST_DELETE_API_KEY']
API_BASE_URL = api_config['API_BASE_URL']


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
        logging.info(f"Fehler beim Verbinden zur Datenbank: {error}")
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
    Ruft die neuesten Sensordaten von der API-Endpunkt ab.

    Rückgabewerte:
        latest_data: Ein Wörterbuch mit den neuesten Sensordaten oder None, falls keine Daten verfügbar sind.
    """
    try:
        # Ein GET-Request an den API-Endpunkt senden, um die neuesten Sensordaten abzurufen
        # response = requests.get(f"{API_BASE_URL}/latest", headers={"X-API-Key": READ_API_KEY})

        # HTTP-Header mit dem API-Schlüssel definieren
        headers = {"X-Api-Key": READ_API_KEY}
        # GET-Anfrage an die API senden
        response = requests.get(API_BASE_URL, headers=headers)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            latest_data = response.json()  # Parse JSON response
            return latest_data
        else:
            logging.debug("Abrufen der neuesten Sensordaten fehlgeschlagen. Statuscode: %s", response.status_code)
            return None
    except Exception as e:
        logging.debug("Fehler beim Abrufen der neuesten Sensordaten: %s", str(e))
        return None


def get_sensor_data_last_hour():
    """
    Ruft Sensordaten der letzten Stunde von der API ab.

    Rückgabewerte:
        start_of_last_hour: Eine Liste mit den Sensordaten der letzten Stunde oder None, falls keine Daten verfügbar sind.
    """
    try:
        headers = {"X-Api-Key": READ_API_KEY}  # HTTP-Header mit dem API-Schlüssel definieren
        response = requests.get(API_BASE_URL, headers=headers) # GET-Anfrage an die API senden

        if response.status_code == 200:
            data = response.json()
            # Zeitpunkt für vor eine Stunde festlegen
            start_of_last_hour = datetime.now() - timedelta(hours=1)
            # Sensordaten der letzten Stunde filtern
            start_of_last_hour = [
                item for sublist in data for item in sublist
                if datetime.fromisoformat(item['time']) >= start_of_last_hour]
            return start_of_last_hour
        else:
            logging.debug(f"Abrufen der Sensordaten fehlgeschlagen. Statuscode: {response.status_code}")
            return None

    except Exception as e:
        logging.debug(f"Fehler beim Abrufen der Sensordaten: {e}")
        return None


def get_sensor_data_last_month():
    """
    Ruft Sensordaten des letzten Monats von der API ab.

    Rückgabewerte:
        sensor_data_last_month: Eine Liste mit den Sensordaten des letzten Monats oder None, falls keine Daten verfügbar sind.
    """
    try:
        headers = {"X-Api-Key": READ_API_KEY} # HTTP-Header mit dem API-Schlüssel definieren
        response = requests.get(API_BASE_URL, headers=headers) # GET-Anfrage an die API senden

        if response.status_code == 200:
            data = response.json()

            today = datetime.today()
            # Zeitpunkt für vor einem Monat festlegen
            start_of_last_month = today - timedelta(days=30)

            sensor_data_last_month = [
                item for sublist in data for item in sublist
                if datetime.fromisoformat(item['time']) >= start_of_last_month]
            return sensor_data_last_month
        else:
            logging.debug(f"Abrufen der Sensordaten fehlgeschlagen. Statuscode: {response.status_code}")
            return None

    except Exception as e:
        logging.debug(f"Fehler beim Abrufen der Sensordaten: {e}")
        return None
