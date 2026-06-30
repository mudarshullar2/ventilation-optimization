import base64
from flask_apscheduler import APScheduler
from flask import (
    Flask,
    jsonify,
    make_response,
    render_template,
    request,
    session,
)
import logging
import requests
from datetime import datetime, timedelta
from mqtt_client import (MQTTClient)
from config.api_config_loader import load_api_config
import numpy as np
import redis
import os
import time


logging.basicConfig(level=logging.INFO)
base_dir = os.path.abspath(os.path.dirname(__file__))
frontend_dir = os.path.join(base_dir, "..", "frontend")

app = Flask(
    __name__,
    template_folder=os.path.join(frontend_dir, "templates"),
    static_folder=os.path.join(frontend_dir, "static"),
)

app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_REDIS"] = redis.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6379")
)

config_file_path = "config/api_config.yaml"

api_config = load_api_config(config_file_path)

READ_API_KEY = api_config["READ_API_KEY"]
POST_API_KEY = api_config["POST_API_KEY"]
API_BASE_URL = api_config["API_BASE_URL"]
CONTENT_TYPE = api_config["CONTENT_TYPE"]

mqtt_client = MQTTClient()
mqtt_client.initialize()


class Config:
    SCHEDULER_API_ENABLED = True


app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if not hasattr(mqtt_client, "combined_data") or not mqtt_client.combined_data:
            sensor_data = {}
            temperature = 0
            humidity = 0
            co2 = 0
            tvoc = "currently not available"
            ambient_temp = 0
            predictions = {}
        else:
            sensor_data = mqtt_client.combined_data
            temperature = sensor_data.get("temperature", 0)
            humidity = sensor_data.get("humidity", 0)
            co2 = sensor_data.get("co2", 0)
            tvoc = sensor_data.get("tvoc", "currently not available")
            ambient_temp = sensor_data.get("ambient_temp", 0)
            predictions = sensor_data.get("predictions", {})

        response = make_response(
            render_template(
                "index.html",
                sensor_data=sensor_data,
                temperature=temperature,
                humidity=humidity,
                co2=co2,
                tvoc=tvoc,
                ambient_temp=ambient_temp,
                predictions=predictions,
                version=time.time(),
            )
        )

        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    except Exception as e:
        logging.error(
            "an error occurred in index(): %s. sensor data: %s",
            str(e),
            str(mqtt_client.combined_data),
        )
        return (
            "error while processing your request",
            500,
        )


@app.route("/plots")
def plots():
    try:
        sensor_data = mqtt_client.get_latest_sensor_data()

        if sensor_data:
            time_data = [data.get("time", None) for data in sensor_data]
            co2_data = [data.get("co2", None) for data in sensor_data]
            temperature_data = [data.get("temperature", None) for data in sensor_data]
            humidity_data = [data.get("humidity", None) for data in sensor_data]
            tvoc_data = [data.get("tvoc", None) for data in sensor_data]
            ambient_temp_data = [data.get("ambient_temp", None) for data in sensor_data]

            def fill_missing_with_last_known(data):
                last_known = None
                for i in range(len(data)):
                    if data[i] is not None:
                        last_known = data[i]
                    elif last_known is not None:
                        data[i] = last_known
                return data

            co2_data = fill_missing_with_last_known(co2_data)
            temperature_data = fill_missing_with_last_known(temperature_data)
            humidity_data = fill_missing_with_last_known(humidity_data)
            tvoc_data = fill_missing_with_last_known(tvoc_data)
            ambient_temp_data = fill_missing_with_last_known(ambient_temp_data)

            return render_template(
                "plots.html",
                co2_data=co2_data,
                temperature_data=temperature_data,
                humidity_data=humidity_data,
                tvoc_data=tvoc_data,
                ambient_temp_data=ambient_temp_data,
                time_data=time_data,
            )
        else:
            return render_template(
                "plots.html",
                co2_data=[],
                temperature_data=[],
                humidity_data=[],
                tvoc_data=[],
                ambient_temp_data=[],
                time_data=[],
            )

    except Exception as e:
        logging.error("error in plots(): %s", e)
        return "an error has occurred", 500


def convert_to_serializable(obj):
    if isinstance(obj, (np.int64, np.int32, np.float64, np.float32)):
        return obj.item()
    raise TypeError(
        "not serializable object {} of type {}".format(obj, type(obj))
    )


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        try:
            predictions = mqtt_client.latest_predictions
            if not predictions:
                return "no predictions are available", 400

            combined_data = mqtt_client.combined_data
            features_df = mqtt_client.latest_features_df

            logistic_prediction = predictions.get("Logistic Regression")
            user_feedback = int(request.form["accurate_prediction"])

            if user_feedback == 1:
                accurate_prediction = int(logistic_prediction)
            else:
                accurate_prediction = 1 - int(logistic_prediction)

            feedback_data = {
                "temperature": float(features_df["temperature"].iloc[0]),
                "humidity": float(features_df["humidity"].iloc[0]),
                "co2": float(features_df["co2"].iloc[0]),
                "timestamp": combined_data["time"][-1],
                "outdoor_temperature": float(features_df["ambient_temp"].iloc[0]),
                "accurate_prediction": accurate_prediction,
            }

            headers = {"X-Api-Key": POST_API_KEY, "Content-Type": CONTENT_TYPE}
            response = requests.post(API_BASE_URL, headers=headers, json=feedback_data)

            if response.status_code == 200:
                return render_template("thank_you.html")
            else:
                return (
                    jsonify(
                        {
                            "message": "no response was sent",
                            "status": response.status_code,
                            "response": response.text,
                        }
                    ),
                    400,
                )

        except Exception as e:
            logging.error("feedback: an unexpected error occurred: %s", e)
            return (
                jsonify(
                    {
                        "message": "an unexpected error occurred",
                        "error:": str(e),
                    }
                ),
                500,
            )

    else:
        try:
            predictions = mqtt_client.latest_predictions
            if not predictions:
                return render_template("feedback.html", error=True)

            features_df = mqtt_client.latest_features_df

            response = make_response(
                render_template(
                    "feedback.html",
                    predictions=predictions,
                    features=features_df.to_dict(orient="records")[0],
                    version=str(time.time()),
                )
            )

            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        except Exception as e:
            logging.error("feedback: error fetching predictions: %s", e)
            return str(e), 500


def get_data(timestamp):
    try:
        return mqtt_client.fetch_data(timestamp)
    except Exception as e:
        logging.error("get_data: could not fetch data: %s", e)
        return {}


@app.route("/leaderboard", methods=["GET", "POST"])
def leaderboard():
    try:
        if request.method == "POST":
            predictions = mqtt_client.latest_predictions
            logging.info("predictions in leaderboard: %s", predictions)
            if not predictions:
                logging.error("no predictions available in latest_predictions")
                return render_template("leaderboard.html", error=True)

            last_prediction = predictions.get("Logistic Regression")
            logging.debug("initial last_prediction: %s, type: %s", last_prediction, type(last_prediction))

            if isinstance(last_prediction, np.integer):
                last_prediction = int(last_prediction)
            elif not isinstance(last_prediction, int):
                last_prediction = int(last_prediction)

            combined_data = mqtt_client.combined_data
            latest_date = combined_data["time"][-1]

            logging.info("latest_date: within the leaderboard feature %s", latest_date)

            latest_date = datetime.strptime(latest_date, "%Y-%m-%d %H:%M")
            adjusted_date = latest_date - timedelta(minutes=1)

            adjusted_date_str = adjusted_date.strftime("%Y-%m-%d %H:%M")
            logging.info("adjusted date %s", adjusted_date_str)

            current_data = get_data(adjusted_date_str)
            logging.info("last current_date in the leaderboard function %s", current_data)

            formatted_current_data = [
                {
                    "timestamp": current_data.get("timestamp"),
                    "co2_values": (
                        float(current_data.get("co2_values"))
                        if current_data.get("co2_values") is not None
                        else None
                    ),
                    "temperature": (
                        float(current_data.get("temperature"))
                        if current_data.get("temperature") is not None
                        else None
                    ),
                    "humidity": (
                        float(current_data.get("humidity"))
                        if current_data.get("humidity") is not None
                        else None
                    ),
                }
            ]

            logging.info("predictions type: %s, value: %s", type(last_prediction), last_prediction)

            if last_prediction == 1:
                response = render_template(
                    "leaderboard2.html",
                    current_data=formatted_current_data,
                    future_data=None,
                    adjusted_date_str=adjusted_date_str,
                    error=False,
                )
            else:
                response = render_template(
                    "leaderboard.html",
                    current_data=formatted_current_data,
                    future_data=None,
                    adjusted_date_str=adjusted_date_str,
                    error=False,
                )

            return response

        elif request.method == "GET":
            predictions = mqtt_client.latest_predictions
            logging.info("last_prediction from the session: %s", predictions)

            if not predictions:
                logging.error(
                    "no data available in the session, please make a prediction first"
                )
                return (
                    "no data available in the session, please make a prediction first",
                    400,
                )

            combined_data = mqtt_client.combined_data
            logging.info(f"combined_data in leaderboard: {combined_data}")

            latest_date = combined_data["time"][-1]
            logging.info("latest_date: inside the leaderboard function %s", latest_date)

            latest_date = datetime.strptime(latest_date, "%Y-%m-%d %H:%M")
            adjusted_date = latest_date - timedelta(minutes=1)

            adjusted_date_str = adjusted_date.strftime("%Y-%m-%d %H:%M")
            logging.info("adjusted date: %s", adjusted_date_str)

            current_data = get_data(adjusted_date_str)
            logging.info("latest current_date in the leaderboard function %s", current_data)

            formatted_current_data = [
                {
                    "timestamp": current_data.get("timestamp"),
                    "co2_values": (
                        float(current_data.get("co2_values"))
                        if current_data.get("co2_values") is not None
                        else None
                    ),
                    "temperature": (
                        float(current_data.get("temperature"))
                        if current_data.get("temperature") is not None
                        else None
                    ),
                    "humidity": (
                        float(current_data.get("humidity"))
                        if current_data.get("humidity") is not None
                        else None
                    ),
                }
            ]

            future_data_response = get_future_data(adjusted_date_str)

            if future_data_response.status_code != 200:
                return future_data_response

            future_data = future_data_response.get_json()
            logging.info(
                "latest future_data in the leaderboard: %s", future_data
            )

            formatted_future_data = [
                {
                    "timestamp": future_data.get("timestamp"),
                    "co2_values": (
                        float(future_data.get("co2_values"))
                        if future_data.get("co2_values") is not None
                        else None
                    ),
                    "temperature": (
                        float(future_data.get("temperature"))
                        if future_data.get("temperature") is not None
                        else None
                    ),
                    "humidity": (
                        float(future_data.get("humidity"))
                        if future_data.get("humidity") is not None
                        else None
                    ),
                }
            ]

            last_prediction = predictions.get("Logistic Regression")

            logging.info("predictions type: %s and value: %s", type(last_prediction), last_prediction)

            if last_prediction == 1:
                response = render_template(
                    "leaderboard2.html",
                    current_data=formatted_current_data,
                    future_data=formatted_future_data,
                    adjusted_date_str=adjusted_date_str,
                    error=False,
                )
            else:
                response = render_template(
                    "leaderboard.html",
                    current_data=formatted_current_data,
                    future_data=formatted_future_data,
                    adjusted_date_str=adjusted_date_str,
                    error=False,
                )
            return response

    except Exception as e:
        logging.error("an unexpected error occurred %s", e)
        return (
            jsonify(
                {
                    "message": "an unexpected error occurred while getting data",
                    "error:": str(e),
                    "note": "please return to the main page",
                }
            ),
            500,
        )


@app.route("/future_data/<timestamp>")
def get_future_data(timestamp):
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            auth_type, auth_credentials = auth_header.split(" ", 1)
            if auth_type.lower() == "basic":
                benutzername, passwort = (
                    base64.b64decode(auth_credentials).decode("utf-8").split(":", 1)
                )
                if benutzername != "admin" or passwort != "HJ|*fS1i":
                    return make_response(
                        "verification failed",
                        401,
                        {"WWW-Authenticate": 'Basic realm="login is required!"'},
                    )
            else:
                return make_response(
                    "verification failed",
                    401,
                    {"WWW-Authenticate": 'Basic realm="login is required!"'},
                )
        else:
            return make_response(
                "verification failed",
                401,
                {"WWW-Authenticate": 'Basic realm="login is required!"'},
            )

        timestamp_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M")
        future_timestamp_dt = timestamp_dt + timedelta(minutes=5)
        future_timestamp_str = future_timestamp_dt.strftime("%Y-%m-%d %H:%M")
        logging.info("fetching future data for timestamp %s", future_timestamp_str)

        future_data = mqtt_client.fetch_future_data(future_timestamp_str)
        if not future_data:
            logging.info("no future dates available for timestamps: %s", future_timestamp_str)
            return jsonify({"error": "no future data available"}), 404

        formatted_future_data = {
            "timestamp": future_data.get("timestamp"),
            "co2_values": (
                float(future_data.get("co2_values"))
                if future_data.get("co2_values") is not None
                else None
            ),
            "temperature": (
                float(future_data.get("temperature"))
                if future_data.get("temperature") is not None
                else None
            ),
            "humidity": (
                float(future_data.get("humidity"))
                if future_data.get("humidity") is not None
                else None
            ),
        }

        logging.info("future data fetched successfully %s", formatted_future_data)
        return jsonify(formatted_future_data)

    except Exception as e:
        logging.error("get_future_data: error fetching future data: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/save_analysis_data", methods=["POST"])
def save_analysis_data():
    try:
        data = request.json
        current_data = {
            "co2_values": data["current_co2"],
            "temperature": data["current_temperature"],
            "humidity": data["current_humidity"],
        }
        future_data = {
            "co2_values": data["future_co2"],
            "temperature": data["future_temperature"],
            "humidity": data["future_humidity"],
        }
        co2_change = data["co2_change"]
        temperature_change = data["temperature_change"]
        humidity_change = data["humidity_change"]
        decision = data["decision"]

        mqtt_client.save_analysis_data(
            current_data,
            future_data,
            co2_change,
            temperature_change,
            humidity_change,
            decision,
        )

        return jsonify({"message": "data saved successfully"}), 200
    except Exception as e:
        logging.error("save_analysis_data: error saving analysis data %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/clear_session")
def clear_session():
    try:
        session.clear()
        return "session data has been successfully deleted", 200
    except Exception as e:
        logging.error("clear_session: error clearing session data %s", e)
        return jsonify({"error in clear_session()": str(e)}), 500


@app.route("/clear-predictions", methods=["POST"])
def clear_predictions_route():
    try:
        mqtt_client.clear_predictions()
        session.clear()
        return jsonify({"message": "predictions have been deleted"}), 200
    except Exception as e:
        return jsonify({"error in clear_predictions_route()": str(e)}), 500


@app.route("/latest_data", methods=["GET"])
def get_latest_data():
    latest_data = {
        "time": mqtt_client.latest_time,
        "humidity": (
            mqtt_client.combined_data.get("humidity")[-1]
            if mqtt_client.combined_data.get("humidity")
            else None
        ),
        "temperature": (
            mqtt_client.combined_data.get("temperature")[-1]
            if mqtt_client.combined_data.get("temperature")
            else None
        ),
        "co2": (
            mqtt_client.combined_data.get("co2")[-1]
            if mqtt_client.combined_data.get("co2")
            else None
        ),
    }
    return jsonify(latest_data)


@app.route("/thank_you")
def thank_you():
    return render_template("thank_you.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
