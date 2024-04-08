import psycopg2
from river import compose, preprocessing, linear_model, metrics
import logging
import time
import yaml


def load_database_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config['database']
    except FileNotFoundError:
        logging.error(f"Config file '{config_file}' not found")
        raise


config = load_database_config('/Users/mudarshullar/PycharmProjects/BAProject/databaseConfig.yaml')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Connect to PostgreSQL database
conn = psycopg2.connect(
    dbname=config['dbname'],
    user=config['user'],
    password=config['password'],
    host=config['host'],
    port=config['port']
)
cursor = conn.cursor()

# Initialize river model for CO2 prediction
model = compose.Pipeline(
    preprocessing.StandardScaler(),
    linear_model.LinearRegression()
)
metric = metrics.R2()

# Continuously fetch and process streaming data
while True:
    try:
        # Query latest sensor data from PostgreSQL
        cursor.execute('SELECT "timestamp", temperature, humidity, co2_values, tvoc_values FROM public."SensorData" '
                       'ORDER BY "timestamp" DESC LIMIT 1;')
        latest_data = cursor.fetchone()

        if latest_data:
            timestamp, temperature, humidity, co2, tvoc = latest_data

            # Prepare instance for prediction and training
            instance = {'temperature': temperature, 'humidity': humidity, 'tvoc': tvoc}

            # Predict CO2 using the model
            prediction = model.predict_one(instance)

            # Update the model with the new instance and true label (CO2)
            model.learn_one(instance, co2)

            # Update metric with the true label and prediction
            metric.update(co2, prediction)

            # Log the prediction and actual CO2 value
            logging.info(f"Timestamp: {timestamp}, Predicted CO2: {prediction:.2f}, Actual CO2: {co2}")

        else:
            logging.warning("No new data found in the database.")

    except Exception as e:
        logging.error(f"Error processing data: {e}")

    # Sleep for a specified duration (e.g., 1 minute) before querying new data
    time.sleep(23)

# Close database connection
cursor.close()
conn.close()
