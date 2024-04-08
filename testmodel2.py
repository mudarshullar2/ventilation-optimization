import psycopg2
import pandas as pd
import pickle
import logging
import yaml
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load the trained model from the .pkl file
model_path = '/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl'
with open(model_path, 'rb') as f:
    model = pickle.load(f)


def load_database_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config['database']
    except FileNotFoundError:
        logging.error(f"Config file '{config_file}' not found")
        raise


def connect_to_database(config):
    try:
        # Connect to the PostgreSQL database using the provided configuration
        conn = psycopg2.connect(
            dbname=config['dbname'],
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=config['port']
        )
        logging.info("Connected to the database successfully")
        return conn
    except (Exception, psycopg2.Error) as error:
        logging.error("Error while connecting to PostgreSQL database:", error)


def fetch_latest_sensor_data(conn):
    try:
        # Query to fetch the latest sensor data from the database
        query = 'SELECT * FROM "SensorData" ORDER BY "timestamp" DESC LIMIT 1;'
        df = pd.read_sql(query, conn)
        logging.info("Fetched latest sensor data from the database")
        return df
    except (Exception, psycopg2.Error) as error:
        logging.error("Error while fetching sensor data from PostgreSQL database:", error)


def preprocess_sensor_data(df):
    # Assuming the columns are in the correct order as per the query result
    df = df.rename(columns={
        'timestamp': 'timestamp',
        'temperature': 'temperature',
        'humidity': 'humidity',
        'co2_values': 'co2',
        'tvoc_values': 'tvoc'
    })
    return df


def predict_window_state(model, df):
    # Extract features from the preprocessed data
    features = df[['co2', 'tvoc', 'temperature', 'humidity']]
    # Use the trained model to predict the window state
    # (0: windows should not be opened, 1: windows should be opened)
    prediction = model.predict(features)
    logging.info("Predicted window state: %s", prediction[0])
    return prediction[0]


if __name__ == "__main__":
    # Load database configuration from config.yaml
    config_file = '/Users/mudarshullar/PycharmProjects/BAProject/databaseConfig.yaml'
    db_config = load_database_config(config_file)

    while True:
        # Connect to the database
        conn = connect_to_database(db_config)

        if conn is not None:
            # Fetch the latest sensor data from the database
            latest_data = fetch_latest_sensor_data(conn)

            if latest_data is not None:
                # Preprocess the fetched sensor data
                preprocessed_data = preprocess_sensor_data(latest_data)

                # Print the current sensor values
                logging.info("Current sensor values:")
                logging.info(preprocessed_data)

                # Use the trained model to predict the window state
                window_state = predict_window_state(model, preprocessed_data)

                # Perform actions based on the predicted window state (e.g., control windows)
                if window_state == 1:
                    logging.info("Open windows based on the model prediction")
                else:
                    logging.info("Do not open windows based on the model prediction")

            # Close the database connection
            conn.close()
            logging.info("Database connection closed")

        # Wait for 25 seconds before fetching the next sensor data
        time.sleep(25)
