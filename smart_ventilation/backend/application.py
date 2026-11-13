import base64
from flask_apscheduler import APScheduler
from flask import (
    Flask,
    jsonify,
    make_response,
    render_template,
    request,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import hmac
from functools import wraps
import logging
from mqtt_client import (MQTTClient)
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

app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_REDIS"] = redis.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6379")
)

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)

mqtt_client = MQTTClient()
mqtt_client.initialize()


class Config:
    SCHEDULER_API_ENABLED = True


app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


def require_basic_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
                user, _, pw = decoded.partition(":")
            except Exception:
                user, pw = "", ""
            if (hmac.compare_digest(user, os.environ["BASIC_AUTH_USER"])
                    and hmac.compare_digest(pw, os.environ["BASIC_AUTH_PASS"])):
                return view(*args, **kwargs)
        return make_response(
            "verification failed",
            401,
            {"WWW-Authenticate": 'Basic realm="login is required!"'},
        )
    return wrapper


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
        else:
            sensor_data = mqtt_client.combined_data
            temperature = sensor_data.get("temperature", 0)
            humidity = sensor_data.get("humidity", 0)
            co2 = sensor_data.get("co2", 0)
            tvoc = sensor_data.get("tvoc", "currently not available")
            ambient_temp = sensor_data.get("ambient_temp", 0)

        response = make_response(
            render_template(
                "index.html",
                sensor_data=sensor_data,
                temperature=temperature,
                humidity=humidity,
                co2=co2,
                tvoc=tvoc,
                ambient_temp=ambient_temp,
                predictions={},
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


@app.route("/latest_data", methods=["GET"])
@require_basic_auth
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


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
