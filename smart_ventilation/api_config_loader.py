import yaml

def load_api_config(config_file_path):
    """
    Diese Funktion lädt die API-Konfiguration aus einer YAML-Datei.

    :param config_file_path: Pfad zur YAML-Konfigurationsdatei
    :return: API-Konfiguration als Dictionary
    """
    with open(config_file_path, 'r') as file:
        # Öffnet die YAML-Konfigurationsdatei im Lesemodus
        api_config = yaml.safe_load(file)
        # Lädt den Inhalt der YAML-Datei sicher
    return api_config
    # Gibt die geladene API-Konfiguration zurück

