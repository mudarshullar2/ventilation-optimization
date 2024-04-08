from SmartSystem.config import load_database_config
from SmartSystem.database_management import connect_to_database, get_latest_sensor_data, close_connection
import psycopg2
import pandas as pd
import pickle
import logging
import time

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Das trainierte Modell aus der .pkl-Datei laden
model_path = "/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl"
with open(model_path, "rb") as f:
    model = pickle.load(f)


def fetch_latest_sensor_data(conn):
    """
    Ruft die neuesten Sensordaten aus der Datenbank ab.

    :param conn: Verbindungsobjekt zur PostgreSQL-Datenbank
    :return: DataFrame mit den abgerufenen Sensordaten oder None bei einem Fehler
    """
    try:
        # Abfrage, um die neuesten Sensordaten aus der Datenbank abzurufen
        query = 'SELECT * FROM "SensorData" ORDER BY "timestamp" DESC LIMIT 1;'
        df = pd.read_sql(query, conn)
        logging.info("Neueste Sensordaten aus der Datenbank abgerufen.")
        return df
    except (Exception, psycopg2.Error) as error:
        logging.error(
            "Fehler beim Abrufen der Sensordaten aus der PostgreSQL-Datenbank:", error
        )


def preprocess_sensor_data(df):
    """
    Vorverarbeitet die abgerufenen Sensordaten.

    :param df: DataFrame mit den abgerufenen Sensordaten
    :return: Vorverarbeiteter DataFrame
    """
    # Annahme: Die Spalten sind in der richtigen Reihenfolge gemäß dem Abfrageergebnis
    df = df.rename(
        columns={
            "timestamp": "timestamp",
            "temperature": "temperature",
            "humidity": "humidity",
            "co2_values": "co2",
            "tvoc_values": "tvoc",
        }
    )
    return df


def predict_window_state(model, df):
    """
    Verwendet das trainierte Modell, um den Zustand des Fensters vorherzusagen.

    :param model: Trainiertes Machine-Learning-Modell
    :param df: DataFrame mit den vorverarbeiteten Sensordaten
    :return: Vorhersage des Fensterzustands (0 oder 1)
    """
    # Merkmale aus den vorverarbeiteten Daten extrahieren
    features = df[["co2", "tvoc", "temperature", "humidity"]]
    # Das trainierte Modell verwenden, um den Zustand des Fensters vorherzusagen
    # (0: Fenster sollten nicht geöffnet werden, 1: Fenster sollten geöffnet werden)
    prediction = model.predict(features)
    logging.info("Predicted window state: %s", prediction[0])
    return prediction[0]


def main():
    # Datenbankkonfiguration aus config.yaml laden
    config_file = "/SmartSystem/database_config.yaml"
    db_config = load_database_config(config_file)

    while True:
        # Zur Datenbank verbinden
        conn = connect_to_database(db_config)

        if conn is not None:
            # Die neuesten Sensordaten aus der Datenbank abrufen
            latest_data = fetch_latest_sensor_data(conn)

            if latest_data is not None:
                # Sensordaten vorverarbeitena
                preprocessed_data = preprocess_sensor_data(latest_data)

                # Aktuelle Sensordaten ausgeben
                logging.info("Current sensor values:")
                logging.info(preprocessed_data)

                # Das trainierte Modell verwenden, um den Fensterzustand vorherzusagen
                window_state = predict_window_state(model, preprocessed_data)

                # Aktionen basierend auf der vorhergesagten Fensterzustand durchführen (z.B. Fenster steuern)
                if window_state == 1:
                    logging.info("Open windows based on the model prediction")
                else:
                    logging.info("Do not open windows based on the model prediction")

            # Datenbankverbindung schließen
            conn.close()
            logging.info("Database connection closed")

        # 25 Sekunden warten, bevor die nächsten Sensordaten abgerufen werden
        time.sleep(25)


if __name__ == "__main__":
    main()
