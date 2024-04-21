"""
Hinweis: Dieses Beispiel für ein inkrementelles Machine-Learning-Modell hat keine direkte Verbindung zur Anwendung
`application.py`. Es dient lediglich zur Veranschaulichung eines Systems, das in Echtzeit aus den Sensor-Daten lernt und
sich entsprechend anpasst. Das Modell wird kontinuierlich aktualisiert, um Vorhersagen basierend auf den aktuellen
Daten zu verbessern.
"""

from database_management import connect_to_database, get_latest_sensor_data
from river import compose, preprocessing, linear_model, metrics
import logging
import time

# River-Modell für CO2-Vorhersage initialisieren
model = compose.Pipeline(
    preprocessing.StandardScaler(), linear_model.LinearRegression()
)
metric = metrics.R2()

# Kontinuierlich Daten abrufen und verarbeiten
while True:
    try:
        # Verbindung zur PostgreSQL-Datenbank herstellen
        conn = connect_to_database()
        cursor = conn.cursor()

        # Die neuesten Sensordaten aus der Datenbank abrufen
        latest_data = get_latest_sensor_data(cursor)

        if latest_data:
            timestamp, temperature, humidity, co2, tvoc = latest_data

            # Instanz für Vorhersage und Training vorbereiten
            instance = {"temperature": temperature, "humidity": humidity, "tvoc": tvoc}

            # CO2 mithilfe des Modells vorhersagen
            prediction = model.predict_one(instance)

            # Modell mit neuer Instanz und echtem Wert (CO2) aktualisieren
            model.learn_one(instance, co2)

            # Metrik mit echtem Wert und Vorhersage aktualisieren
            metric.update(co2, prediction)

            # Vorhersage und tatsächlichen CO2-Wert protokollieren
            logging.info(
                f"Timestamp: {timestamp}, Vorhergesagtes CO2: {prediction:.2f}, Tatsächliches CO2: {co2}"
            )

        else:
            logging.warning("Keine neuen Daten in der Datenbank gefunden.")
            # Datenbankverbindungen schließen
            cursor.close()
            conn.close()

    except Exception as e:
        logging.error(f"Fehler bei der Datenverarbeitung: {e}")

    # Vor dem Abrufen neuer Daten eine bestimmte Zeit warten (z.B. 23 Sekunden)
    time.sleep(23)
