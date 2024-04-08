import random
import logging
from datetime import datetime


def generate_sensor_data():
    """
    Generiert zufällige Sensordaten.

    :return: Tuple mit Zeitstempel, Temperatur, Luftfeuchtigkeit, CO2-Werte und TVOC-Werte
    """
    try:
        temperature = round(random.uniform(10, 27), 2)
        humidity = round(random.uniform(30, 62), 2)
        co2_values = round(random.uniform(402, 600), 2)
        tvoc_values = round(random.uniform(100, 380), 2)
        timestamp = datetime.now()

        return timestamp, temperature, humidity, co2_values, tvoc_values
    except Exception as e:
        logging.error("Fehler beim Generieren von Sensordaten: %s", str(e))
        return None
