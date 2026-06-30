import psycopg2
import logging
import yaml

logger = logging.getLogger(__name__)

def load_config(config_file_path):
    try:
        with open(config_file_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
            return config["DATABASES"]["default"]
    except Exception as e:
        logging.error("failed to load config file: %s", e)
        return None


def connect_to_database(config):
    try:
        connection = psycopg2.connect(
            dbname=config["NAME"],
            user=config["USER"],
            password=config["PASSWORD"],
            host=config["HOST"],
            port=config["PORT"],
        )
        logging.info("successfully connected to database")
        return connection
    except Exception as e:
        logging.error("failed to connect to database: %s", e)
        return None