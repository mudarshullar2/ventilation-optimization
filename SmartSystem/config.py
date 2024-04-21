import yaml
import logging


def load_database_config(config_file):
    """
    Lädt die Konfiguration der Datenbank aus einer YAML-Konfigurationsdatei.

    :param config_file: Pfad zur YAML-Konfigurationsdatei
    :return: Datenbankkonfigurationsdaten als Dictionary
    """
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
        return config["database"]
    except FileNotFoundError:
        logging.error(f"Konfigurationsdatei '{config_file}' nicht gefunden")
        raise

