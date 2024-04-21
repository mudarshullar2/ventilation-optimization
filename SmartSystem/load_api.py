import yaml


def load_api_config(config_file_path):
    """
    Lädt die API-Konfiguration aus einer YAML-Datei.

    Args:
        config_file_path (str): Der Pfad zur YAML-Konfigurationsdatei.

    Returns:
        dict: Ein Python-Wörterbuch, das die geladene Konfiguration enthält.

    Raises:
        FileNotFoundError: Falls die angegebene Datei nicht gefunden wird.
        yaml.YAMLError: Falls beim Laden der YAML-Datei ein Fehler auftritt.
    """
    with open(config_file_path, 'r') as file:
        config = yaml.safe_load(file)
    return config