from database.database_connection import load_config, connect_to_database
import psycopg2
import pytz
import paho.mqtt.client as mqtt
import threading
import json
import logging
import datetime as dt
from datetime import datetime, timedelta
from config.api_config_loader import load_api_config

config_file_path = "config/api_config.yaml"
db_config_path = "config/db_config.yaml"
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
            self.combined_data = {}
            self.data_points = []
            self.data_lock = threading.Lock()
            self.latest_time = None
            self.last_clear_date = datetime.now().replace(
                minute=0, second=0, microsecond=0
            )
            self.conn = connect_to_database(db)
        except Exception as e:
            logging.error("initialization error %s", e)

    def on_connect(self, client, userdata, flags, rc):
        try:
            logging.info("connected with result code %s", str(rc))

            # datetime and TVOC
            self.client.subscribe(
                "application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/24e124707c481005/event/up"
            )

            # CO2, temperature, humidity
            self.client.subscribe(
                "application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/0004a30b01045883/event/up"
            )

            # outdoor temperature
            self.client.subscribe(
                "application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/device/647fda000000aa92/event/up"
            )
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
                logging.info(f"data cleared at {clear_time.strftime('%H:%M')}")
        except Exception as e:
            logging.error("clear_data: error while deleting the data %s", e)

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
                        (timestamp, co2_values, temperature, humidity)
                        VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(
                        query,
                        (
                            data_point["time"],
                            data_point["co2"],
                            data_point["temperature"],
                            data_point["humidity"],
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

    def stop(self):
        try:
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

    def initialize(self):
        try:
            self.client.connect(CLOUD_SERVICE_URL, 8883)
            self.client.loop_start()
        except Exception as e:
            logging.error("initialize: Initialization error: %s", e)
