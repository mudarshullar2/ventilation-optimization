"""Flask JSON API for the home-climate-control system.

Serves JSON for the React SPA and, in production, the built static bundle.
The whole API requires login (Flask-Login session).

Endpoints:
    POST /api/login                 authenticate (username, password)
    POST /api/logout                end the session
    GET  /api/me                    current auth status
    GET  /api/csrf-token            CSRF token for the SPA to send on POSTs
    GET  /api/rooms                 latest readings + status + insight + radiator per room
    GET  /api/history?room=&hours=  per-room time series
    POST /api/radiator/<room>/set   set a room's target temperature
"""
import logging
import os
from datetime import timedelta

from flask import Flask, jsonify, request, session, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import check_password_hash

from mqtt_client import MQTTClient
from database.db import Database
from sensors.models import METRICS, classify
from control.models import clamp_target
from auth.service import User

logging.basicConfig(level=logging.INFO)
base_dir = os.path.abspath(os.path.dirname(__file__))
dist_dir = os.path.join(base_dir, "..", "frontend", "dist")

app = Flask(__name__, static_folder=None)
app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]

# Secure session cookies. SECURE requires HTTPS, so it's opt-in via env
# (set COOKIE_SECURE=true in production behind TLS; leave unset for local http dev).
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
# Sessions expire after this many days of inactivity (sliding; refreshed each request).
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=int(os.environ.get("SESSION_LIFETIME_DAYS", "7")))

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

login_manager = LoginManager(app)


@login_manager.user_loader
def load_user(user_id):
    try:
        row = db.get_user_by_id(int(user_id))
    except (TypeError, ValueError):
        return None
    return User(row["id"], row["username"], row["role"]) if row else None


@login_manager.unauthorized_handler
def unauthorized():
    # API clients get JSON 401, not a redirect.
    return jsonify({"error": "authentication required"}), 401


# --- Auth endpoints ---
@app.route("/api/login", methods=["POST"])
@limiter.limit("5 per minute; 30 per hour")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    row = db.get_user_by_username(username)
    if row and check_password_hash(row["password_hash"], password):
        login_user(User(row["id"], row["username"], row["role"]))
        session.permanent = True
        db.insert_audit(row["username"], "login", {})
        return jsonify({"username": row["username"], "role": row["role"]})
    db.insert_audit(username or None, "login_failed", {})
    return jsonify({"error": "invalid credentials"}), 401


@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    db.insert_audit(current_user.username, "logout", {})
    logout_user()
    return jsonify({"ok": True})


@app.route("/api/me")
def me():
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "username": current_user.username,
            "role": current_user.role,
        })
    return jsonify({"authenticated": False})


@app.route("/api/csrf-token")
def csrf_token():
    # The SPA fetches this once and sends it back as the X-CSRFToken header on POSTs.
    return jsonify({"csrf_token": generate_csrf()})


# --- Protected data + control endpoints ---
@app.route("/api/rooms")
@login_required
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
@login_required
def api_history():
    room = request.args.get("room")
    hours = request.args.get("hours", default=24, type=int)
    if not room:
        return jsonify({"error": "room required"}), 400
    return jsonify({"room": room, "history": db.history(room, hours=hours)})


@app.route("/api/radiator/<room>/set", methods=["POST"])
@login_required
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
    db.insert_audit(current_user.username, "radiator_set", {"room": room, "target_temp": target})
    return jsonify({"room": room, "target_temp": target}), 200


@app.route("/api/audit")
@login_required
def api_audit():
    # Read vs. control authorization: the audit trail is admin-only.
    if current_user.role != "admin":
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"entries": db.recent_audit(200)})


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
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    app.run(host=host, port=port)
