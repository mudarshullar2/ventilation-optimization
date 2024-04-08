import psycopg2
import random
from datetime import datetime
import schedule
import time
import logging
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_database_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config['database']
    except FileNotFoundError:
        logging.error(f"Config file '{config_file}' not found")
        raise


config = load_database_config('/Users/mudarshullar/PycharmProjects/BAProject/databaseConfig.yaml')


def generate_sensor_data():
    temperature = round(random.uniform(10, 27), 2)
    humidity = round(random.uniform(30, 62), 2)
    co2_values = round(random.uniform(402, 600), 2)
    tvoc_values = round(random.uniform(100, 380), 2)
    timestamp = datetime.now()

    return timestamp, temperature, humidity, co2_values, tvoc_values


def insert_sensor_data():
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=config['DBNAME'],
            user=config['DBUSER'],
            password=config['DBPASSWORD'],
            host=config['DBHOST'],
            port=config['DBPORT']
        )
        logging.info("Successfully connected to PostgreSQL.")

        cursor = conn.cursor()

        timestamp, temperature, humidity, co2_values, tvoc_values = generate_sensor_data()

        insert_query = 'INSERT INTO public."SensorData" ("timestamp", temperature, humidity, co2_values, tvoc_values) ' \
                       'VALUES (%s, %s, %s, %s, %s)'

        cursor.execute(insert_query, (timestamp, temperature, humidity, co2_values, tvoc_values))
        conn.commit()

        logging.info(
            f"Data inserted: Timestamp={timestamp}, Temperature={temperature}"
            f", Humidity={humidity}, CO2={co2_values}, TVOC={tvoc_values}")

    except psycopg2.Error as e:
        logging.error(f"Error connecting to PostgreSQL: {e}")

    finally:
        if conn:
            conn.close()
            logging.info("PostgreSQL connection closed")


# Schedule data insertion job
schedule.every(20).seconds.do(insert_sensor_data)

# Main loop to run the scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
