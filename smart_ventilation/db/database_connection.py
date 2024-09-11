import psycopg2
import logging
import yaml

# Konfigurieren des Loggings
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_config(config_file_path):
    """
    Lädt die Datenbankkonfiguration aus einer YAML-Datei.

    :param config_file_path: Der Pfad zur Konfigurationsdatei.
    :return: Ein Dictionary mit den Datenbankverbindungseinstellungen.
    """
    try:
        with open(config_file_path, "r") as file:
            config = yaml.safe_load(file)
            return config["DATABASES"]["default"]
    except Exception as e:
        logging.error(f"Fehler beim Laden der Konfigurationsdatei: {e}")
        return None


def connect_to_database(config):
    """
    Stellt eine Verbindung zur PostgreSQL-Datenbank her und gibt das Connection-Objekt zurück.

    :param config: Ein Dictionary mit den Datenbankverbindungseinstellungen.
    :return: Das Connection-Objekt zur Datenbank
    """
    try:
        # Verbindungsdaten
        connection = psycopg2.connect(
            dbname=config["NAME"],  # Name der Datenbank
            user=config["USER"],  # Benutzername
            password=config["PASSWORD"],  # Passwort
            host=config["HOST"],  # Hostname
            port=config["PORT"],  # Portnummer
        )

        # Erfolgreiche Verbindung loggen
        logging.info("Erfolgreiche Verbindung zur Datenbank.")
        return connection

    except Exception as e:
        # Fehler loggen
        logging.error(f"Fehler beim Verbinden zur Datenbank: {e}")
        return None
