import time
import psycopg2
import pytz
from db.database_connection import load_config, connect_to_database
import paho.mqtt.client as mqtt
import pandas as pd
import threading
import uuid
import copy
import joblib
import json
import logging
import datetime as dt
from datetime import datetime, timedelta
from api_config_loader import load_api_config

config_file_path = "api_config.yaml"
db_config_path = "db/db_config.yaml"
db = load_config(db_config_path)

api_config = load_api_config(config_file_path)

CLOUD_SERVICE_URL = api_config["CLOUD_SERVICE_URL"]
USERNAME = api_config["USERNAME"]
PASSWORD = api_config["PASSWORD"]


class MQTTClient:
    def __init__(self):
        try:
            self.client = mqtt.Client()
            self.client.tls_set()
            self.client.username_pw_set(username=USERNAME, password=PASSWORD)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.parameters = {}
            self.latest_predictions = {}
            self.combined_data = {}
            self.data_points = []
            self.thread_alive = True
            self.predictions_cleared = False

            self.prediction_event = threading.Event()
            self.prediction_thread = threading.Thread(
                target=self.run_periodic_predictions
            )
            self.prediction_thread.start()
            self.data_lock = threading.Lock()
            self.first_time = None
            self.first_topic_data = []
            self.latest_time = None
            self.last_clear_date = datetime.now().replace(
                minute=0, second=0, microsecond=0
            )
            self.conn = connect_to_database(db)

            logistic_regression_model = joblib.load("models/Logistic_Regression.pkl")
            random_forest_model = joblib.load("models/Random_Forest.pkl")

            self.models = {
                "Logistic Regression": logistic_regression_model,
                "Random Forest": random_forest_model,
            }
        except Exception as e:
            logging.error("initialization error %s", e)

    def on_connect(self, client, userdata, flags, rc):
        try:
            logging.info("connected with result code %s", str(rc))

            # for datetime and TVOC
            self.client.subscribe(
                "application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up"
            )

            # for Co2, temperature, etc.
            # self.client.subscribe(
            #    "application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b00fca900/event/up"
            #)

            self.client.subscribe(
                "application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up"
            )

            # for outdoor temperature
            self.client.subscribe(
                "application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up"
            )

            if not self.prediction_thread.is_alive():
                logging.warning("the thread was stopped and is being restarted")
                self.restart_thread()
        except Exception as e:
            logging.error("on_connect: error establishing connection %s", e)

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            def adjust_and_format_time(raw_time):
                try:
                    utc_time = dt.datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S.%f%z")
                    berlin_tz = pytz.timezone("Europe/Berlin")
                    berlin_time = utc_time.astimezone(berlin_tz)
                    return berlin_time.strftime("%Y-%m-%d %H:%M")
                except Exception as e:
                    logging.error(f"error while adjusting datetime: %s", e)
                    return None

            if topic.endswith("0004a30b01045883/event/up"):
                formatted_time = adjust_and_format_time(payload["time"])
                self.latest_time = formatted_time
                logging.info(f"self.latest_time: {self.latest_time}")
                humidity_values = payload["object"].get("humidity")
                temperature_values = payload["object"].get("temperature")
                co2_values = payload["object"].get("co2")

                if (
                    formatted_time is not None
                    and formatted_time not in self.combined_data.get("time", [])
                ):
                    self.combined_data.setdefault("time", []).append(formatted_time)

                if humidity_values is not None:
                    self.combined_data.setdefault("humidity", []).append(
                        round(humidity_values, 2)
                    )

                if temperature_values is not None:
                    self.combined_data.setdefault("temperature", []).append(
                        round(temperature_values, 2)
                    )

                if co2_values is not None:
                    self.combined_data.setdefault("co2", []).append(
                        round(co2_values, 2)
                    )

                data_point = {
                    "time": formatted_time,
                    "humidity": (
                        round(humidity_values, 2)
                        if humidity_values is not None
                        else None
                    ),
                    "temperature": (
                        round(temperature_values, 2)
                        if temperature_values is not None
                        else None
                    ),
                    "co2": round(co2_values, 2) if co2_values is not None else None,
                }

                if all(value is not None for value in data_point.values()):
                    logging.info(f"data_point is {data_point}")
                    self.store_first_topic_data(data_point)
            else:
                formatted_time = self.latest_time

            if topic.endswith("24e124707c481005/event/up"):
                tvoc_value = payload["object"].get("tvoc")

                if tvoc_value is not None:
                    self.combined_data.setdefault("tvoc", []).append(
                        round(tvoc_value, 2)
                    )

            elif topic.endswith("647fda000000aa92/event/up"):
                ambient_temp_value = payload["object"].get("ambient_temp")

                if ambient_temp_value is not None:
                    self.combined_data.setdefault("ambient_temp", []).append(
                        round(ambient_temp_value, 2)
                    )

            if (
                formatted_time is not None
                and formatted_time not in self.combined_data.get("time", [])
            ):
                self.combined_data.setdefault("time", []).append(formatted_time)

            required_keys = {"humidity", "temperature", "co2", "tvoc", "ambient_temp"}

            if any(len(self.combined_data.get(key, [])) > 0 for key in required_keys):
                self.collect_data(self.combined_data)

            self.check_and_clear_data()

        except Exception as e:
            logging.error(f"on_message: error receiving message %s", e)

    def collect_data(self, combined_data):
        with self.data_lock:
            try:
                required_keys = [
                    "time",
                    "humidity",
                    "temperature",
                    "co2",
                    "tvoc",
                    "ambient_temp",
                ]
                max_length = max(
                    len(combined_data[key])
                    for key in combined_data
                    if isinstance(combined_data[key], list)
                )

                for i in range(max_length):
                    data = {}
                    for key in combined_data:
                        if isinstance(combined_data[key], list) and i < len(
                            combined_data[key]
                        ):
                            data[key] = combined_data[key][i]
                        else:
                            data[key] = None
                    for key in required_keys:
                        if key not in data:
                            data[key] = None
                    self.data_points.append(data)
                    logging.debug(f"collected data points %s", data)

            except Exception as e:
                logging.error("collect_data: unexpected error during data collection %s", e)
                logging.error("collect_data: contents of combined data %s", combined_data)
                logging.error("collect_data: content of data points %s", self.data_points)

    def run_periodic_predictions(self):
        while self.thread_alive:
            # wait 10min
            self.prediction_event.wait(600)
            if not self.thread_alive:
                break
            self.prediction_event.clear()

            if self.predictions_cleared:
                logging.info("predictions were cleared")
                continue

            if self.data_points:
                try:
                    data_points_copy = copy.deepcopy(self.data_points)
                    df = pd.DataFrame(data_points_copy)
                    df["parsed_time"] = pd.to_datetime(df["time"])
                    avg_time = df["parsed_time"].mean()
                    logging.info(
                        "timestamp parsing and average calculation successful"
                    )

                    avg_data = df.mean(numeric_only=True).to_dict()
                    avg_data["avg_time"] = avg_time.timestamp()
                    logging.info("average date prepared successfully")

                    avg_data["hour"] = avg_time.hour
                    avg_data["day_of_week"] = avg_time.dayofweek
                    avg_data["month"] = avg_time.month

                    features_df = pd.DataFrame([avg_data])
                    logging.info("features prepared for predictions %s", features_df)

                    correct_order = [
                        "co2",
                        "temperature",
                        "humidity",
                        "tvoc",
                        "ambient_temp",
                        "hour",
                        "day_of_week",
                        "month",
                    ]
                    for feature in correct_order:
                        if feature not in features_df.columns:
                            if feature == "tvoc":
                                features_df[feature] = 100
                            elif feature == "ambient_temp":
                                features_df[feature] = avg_data.get("temperature", 0)
                            else:
                                features_df[feature] = 0

                    features_df = features_df[correct_order]
                    features_array = features_df.to_numpy()

                    restricted_model_order = ["co2", "temperature"]
                    restricted_features_df = features_df[restricted_model_order]
                    restricted_features_array = restricted_features_df.to_numpy()

                    predictions = {}
                    for name, model in self.models.items():
                        if "Random Forest" in name:
                            predictions[name] = model.predict(
                                restricted_features_array
                            )[0]
                        else:
                            predictions[name] = model.predict(features_array)[0]

                    self.combined_data["predictions"] = predictions
                    self.latest_predictions = predictions
                    self.latest_predictions["prediction_time"] = (
                        datetime.now().strftime("%H:%M")
                    )
                    logging.info(f"latest predictions are: {self.latest_predictions}")
                    self.predictions_cleared = False

                    prediction_id = str(uuid.uuid4())
                    self.latest_predictions["id"] = prediction_id

                    self.latest_features_df = features_df

                    data_points_copy.clear()
                except Exception as e:
                    logging.error("run_periodic_predictions: error while processing predictions %s", e)
            else:
                logging.info("run_periodic_predictions: no data collected in the last 10 minutes")

    def check_and_clear_data(self):
        try:
            current_time = datetime.now()

            if current_time >= self.last_clear_date + timedelta(hours=1):
                next_clear_date = self.last_clear_date + timedelta(hours=1)
                self.clear_data(next_clear_date)
                self.last_clear_date = next_clear_date
        except Exception as e:
            logging.error("check_and_clear_data: error %s", e)

    def clear_data(self, clear_time):
        try:
            with self.data_lock:
                self.data_points.clear()
                self.combined_data.clear()
                self.latest_predictions.clear()
                logging.info(f"data cleared at {clear_time.strftime('%H:%M Uhr')}")
        except Exception as e:
            logging.error("clear_data: error while deleting the data %s", e)

    def restart_thread(self):
        try:
            self.thread_alive = True
            self.prediction_thread = threading.Thread(
                target=self.run_periodic_predictions
            )
            self.prediction_thread.start()

            logging.info("prediction thread restarted successfully")
        except Exception as e:
            logging.error("restart_thread: error restarting thread %s", e)

    def get_latest_sensor_data(self):
        try:
            return self.data_points.copy()
        except Exception as e:
            logging.error("get_latest_sensor_data: error fetching the latest sensor data %s", e)
            return []

    def store_first_topic_data(self, data_point):
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                if all(
                    data_point.get(key) is not None
                    for key in ["time", "co2", "temperature", "humidity"]
                ):
                    query = """
                        INSERT INTO classroom_environmental_data
                        (timestamp, co2_values, temperature, 
                        humidity, classroom_number)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(
                        query,
                        (
                            data_point["time"],
                            data_point["co2"],
                            data_point["temperature"],
                            data_point["humidity"],
                            "10c",
                        ),
                    )
                self.conn.commit()
                data_point = None

            except psycopg2.OperationalError as e:
                logging.error(
                    f"store_first_topic_data: error saving data to db %s", e)
                self.reconnect_db()
                self.store_first_topic_data(data_point)

            except Exception as e:
                logging.error(
                    f"store_first_topic_data: error saving data to db %s", e)
                self.conn.rollback()
            finally:
                cursor.close()

    def store_feedback_data(self, feedback_data):
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                if all(
                    feedback_data.get(key) is not None
                    for key in [
                        "temperature",
                        "humidity",
                        "co2",
                        "timestamp",
                        "outdoor_temperature",
                        "accurate_prediction",
                    ]
                ):
                    query = """
                        INSERT INTO feedback_tabelle
                        (temperature, humidity, co2, timestamp, outdoor_temperature, accurate_prediction)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(
                        query,
                        (
                            feedback_data["temperature"],
                            feedback_data["humidity"],
                            feedback_data["co2"],
                            feedback_data["timestamp"],
                            feedback_data["outdoor_temperature"],
                            feedback_data["accurate_prediction"],
                        ),
                    )
                    self.conn.commit()
                else:
                    logging.error(
                        "not all required data is present in feedback_data"
                    )
                    self.conn.rollback()

            except psycopg2.OperationalError as e:
                logging.error("store_feedback_data: db connection error while saving feedback data %s", e)
                self.reconnect_db()

            except Exception as e:
                logging.error("store_feedback_data: error while saving feedback_data %s", e)
                self.conn.rollback()
            finally:
                cursor.close()

    def fetch_data(self, timestamp):
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                logging.info("fetching data for timestamp %s", timestamp)
                query = """ 
                SELECT 
                    AVG(co2_values) as co2_values, 
                    AVG(temperature) as temperature, 
                    AVG(humidity) as humidity
                FROM classroom_environmental_data 
                WHERE 
                    timestamp > CAST(%s AS timestamp); 
                """
                cursor.execute(query, (timestamp,))
                result = cursor.fetchone()
                logging.info("Query successful, data fetched !")

                if result:
                    averaged_data = {
                        "timestamp": timestamp,
                        "co2_values": result[0],
                        "temperature": result[1],
                        "humidity": result[2],
                    }
                else:
                    averaged_data = {}
                return averaged_data

            except psycopg2.OperationalError as e:
                logging.error("fetch_data: db connection error %s", e)
                self.reconnect_db()
                return {}

            except Exception as e:
                logging.error("fetch_data: error while fetching data %s", e)
                return {}
            finally:
                cursor.close()

    def fetch_future_data(self, timestamp):
        with self.data_lock:
            cursor = self.conn.cursor()
            try:
                query = """
                    SELECT 
                        AVG(co2_values) as co2_values,
                        AVG(temperature) as temperature,
                        AVG(humidity) as humidity
                    FROM classroom_environmental_data
                    WHERE timestamp > CAST(%s AS timestamp);
                """

                max_attempts = 30
                wait_time = 10
                result = None

                for attempt in range(max_attempts):
                    logging.info(
                        f"Query attempt {attempt + 1} at {timestamp}"
                    )
                    cursor.execute(query, (timestamp,))
                    result = cursor.fetchone()

                    if result and any(val is not None for val in result):
                        break

                    logging.info(f"no data, please wait for {wait_time} seconds")
                    time.sleep(wait_time)

                if result:
                    averaged_data = {
                        "timestamp": timestamp,
                        "co2_values": (
                            float(result[0]) if result[0] is not None else None
                        ),
                        "temperature": (
                            float(result[1]) if result[1] is not None else None
                        ),
                        "humidity": float(result[2]) if result[2] is not None else None,
                    }
                else:
                    averaged_data = {
                        "timestamp": timestamp,
                        "co2_values": None,
                        "temperature": None,
                        "humidity": None,
                    }

                return averaged_data

            except psycopg2.OperationalError as e:
                logging.error("fetch_future_data: database connection error while fetching future data:",e)
                self.reconnect_db()
                return {
                    "timestamp": timestamp,
                    "co2_values": None,
                    "temperature": None,
                    "humidity": None,
                }

            except Exception as e:
                logging.error(
                    "fetch_future_data: Error fetching future data from the database: %s", e)
                return {
                    "timestamp": timestamp,
                    "co2_values": None,
                    "temperature": None,
                    "humidity": None,
                }
            finally:
                cursor.close()

    def save_analysis_data(
        self,
        current_data,
        future_data,
        co2_change,
        temperature_change,
        humidity_change,
        decision,
    ):
        try:
            cursor = self.conn.cursor()

            query = """
            INSERT INTO environmental_data_analysis (
                    timestamp, current_co2, future_co2, co2_change, 
                    current_temperature, future_temperature, temperature_change, 
                    current_humidity, future_humidity, humidity_change, decision
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            logging.info("saving statistical analysis!")

            timestamp = datetime.now()

            values = (
                timestamp,
                current_data["co2_values"],
                future_data["co2_values"],
                co2_change,
                current_data["temperature"],
                future_data["temperature"],
                temperature_change,
                current_data["humidity"],
                future_data["humidity"],
                humidity_change,
                decision,
            )

            cursor.execute(query, values)

            self.conn.commit()

            cursor.close()

            logging.info("data saved successfully to the environmental_data_analysis table")

        except psycopg2.OperationalError as e:
            logging.error(
                "save_analysis_data: Database connection error while saving data: %s", e)
            self.reconnect_db()

        except Exception as e:
            logging.error(
                "save_analysis_data: Error saving data to the database: %s", e)

    def stop(self):
        try:
            self.thread_alive = False
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logging.error("stop: Error stopping the client: %s", e)

    def reconnect_db(self):
        try:
            logging.info("attempting to re-establish the database connection...")
            self.conn.close()
            self.conn = connect_to_database(db)
            logging.info("database connection re-established successfully.")
        except Exception as e:
            logging.error(
                "reconnect_db: Error re-establishing the database connection: %s", e)

    def clear_predictions(self):
        try:
            logging.info("clearing the old predictions!")
            with self.data_lock:
                self.latest_predictions.clear()
                if "predictions" in self.combined_data:
                    del self.combined_data["predictions"]

                self.predictions_cleared = True

            logging.info("predictions cleared successfully.")
        except Exception as e:
            logging.error("Error in clear_predictions %s", e)

    def initialize(self):
        try:
            self.client.connect(CLOUD_SERVICE_URL, 8883)
            self.client.loop_start()
        except Exception as e:
            logging.error("initialize: Initialization error: %s", e)
