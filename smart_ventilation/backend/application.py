import base64
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
import os
import time

from mqtt_client import MQTTClient
from database.db import Database
from sensors.models import METRICS, METRIC_META, classify
from control.models import clamp_target

logging.basicConfig(level=logging.INFO)
base_dir = os.path.abspath(os.path.dirname(__file__))
frontend_dir = os.path.join(base_dir, "..", "frontend")

app = Flask(
    __name__,
    template_folder=os.path.join(frontend_dir, "templates"),
    static_folder=os.path.join(frontend_dir, "static"),
)

app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)

db = Database()
mqtt_client = MQTTClient(db=db)
mqtt_client.initialize()


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


def _with_status(rooms):
    """Attach a per-metric good/moderate/poor status to each room reading."""
    for room in rooms:
        room["status"] = {m: classify(m, room.get(m)) for m in METRICS}
    return rooms


@app.route("/")
def index():
    try:
        rooms = db.latest_per_room()
        if not rooms:
            # Fall back to in-memory latest if the DB has no rows yet.
            rooms = list(mqtt_client.latest.values())
        rooms = _with_status(sorted(rooms, key=lambda r: r.get("room", "")))
        insights = db.latest_insights_per_room()
        radiators = db.latest_radiator_per_room()
        if not radiators:
            radiators = mqtt_client.latest_radiator

        response = make_response(
            render_template(
                "index.html",
                rooms=rooms,
                insights=insights,
                radiators=radiators,
                metrics=METRICS,
                metric_meta=METRIC_META,
                version=time.time(),
            )
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        logging.error("error in index(): %s", e)
        return "error while processing your request", 500


@app.route("/plots")
def plots():
    try:
        rooms = db.rooms()
        room = request.args.get("room") or (rooms[0] if rooms else None)
        history = db.history(room, hours=24) if room else []
        return render_template(
            "plots.html",
            rooms=rooms,
            room=room,
            history=history,
            metrics=METRICS,
            metric_meta=METRIC_META,
        )
    except Exception as e:
        logging.error("error in plots(): %s", e)
        return "an error has occurred", 500


@app.route("/latest_data", methods=["GET"])
@require_basic_auth
def latest_data():
    return jsonify(list(mqtt_client.latest.values()))


@app.route("/api/radiator/<room>/set", methods=["POST"])
def set_radiator(room):
    """Set a room's target temperature. CSRF-protected (same-origin dashboard)."""
    data = request.get_json(silent=True) or {}
    target = data.get("target_temp")
    if target is None:
        return jsonify({"error": "target_temp required"}), 400
    try:
        target = clamp_target(target)
    except (TypeError, ValueError):
        return jsonify({"error": "target_temp must be a number"}), 400
    mqtt_client.publish_radiator_command(room, target)
    return jsonify({"room": room, "target_temp": target}), 200


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
