"""Flask JSON API for the home-climate-control system.

Serves JSON for the React SPA and, in production, the built static bundle.
Endpoints:
    GET  /api/rooms                 latest readings + status + insight + radiator per room
    GET  /api/history?room=&hours=  per-room time series
    POST /api/radiator/<room>/set   set a room's target temperature (CSRF-protected)
    GET  /api/csrf-token            CSRF token for the SPA to send on POSTs
"""
import logging
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf

from mqtt_client import MQTTClient
from database.db import Database
from sensors.models import METRICS, classify
from control.models import clamp_target

logging.basicConfig(level=logging.INFO)
base_dir = os.path.abspath(os.path.dirname(__file__))
dist_dir = os.path.join(base_dir, "..", "frontend", "dist")

app = Flask(__name__, static_folder=None)
app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)

db = Database()
mqtt_client = MQTTClient(db=db)
mqtt_client.initialize()


@app.route("/api/csrf-token")
def csrf_token():
    # The SPA fetches this once and sends it back as the X-CSRFToken header on POSTs.
    return jsonify({"csrf_token": generate_csrf()})


@app.route("/api/rooms")
def api_rooms():
    try:
        readings = db.latest_per_room() or list(mqtt_client.latest.values())
        insights = db.latest_insights_per_room()
        radiators = db.latest_radiator_per_room() or mqtt_client.latest_radiator

        rooms = []
        for r in sorted(readings, key=lambda x: x.get("room", "")):
            room = r.get("room")
            rooms.append({
                "room": room,
                "timestamp": r.get("timestamp"),
                "readings": {m: r.get(m) for m in METRICS},
                "status": {m: classify(m, r.get(m)) for m in METRICS},
                "insight": insights.get(room),
                "radiator": radiators.get(room),
            })
        return jsonify({"rooms": rooms})
    except Exception as e:
        logging.error("api_rooms failed: %s", e)
        return jsonify({"error": "internal error"}), 500


@app.route("/api/history")
def api_history():
    room = request.args.get("room")
    hours = request.args.get("hours", default=24, type=int)
    if not room:
        return jsonify({"error": "room required"}), 400
    return jsonify({"room": room, "history": db.history(room, hours=hours)})


@app.route("/api/radiator/<room>/set", methods=["POST"])
def set_radiator(room):
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


# --- Serve the built SPA in production (dev uses the Vite dev server) ---
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    if not os.path.isdir(dist_dir):
        return (
            "Frontend not built. Run the Vite dev server (npm run dev) or `npm run build`.",
            200,
        )
    full = os.path.join(dist_dir, path)
    if path and os.path.isfile(full):
        return send_from_directory(dist_dir, path)
    return send_from_directory(dist_dir, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
