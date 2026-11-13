"""AI insights worker.

A standalone process (decoupled from the Flask app) that periodically reads
recent readings per room, computes a short-term forecast and anomaly flags, asks
a local Ollama model for a plain-language summary (optional), and writes the
result to the `insights` table. The dashboard reads from that table.

Run it in the same virtualenv as the backend (so it can reach the DB), after
installing ai/requirements.txt:

    python -m ai.worker

Config via env: AI_INTERVAL (seconds, default 300), AI_HISTORY_HOURS (default 6).
"""
import logging
import os
import time

from database.db import Database
from ai.forecasting import forecast_room
from ai.anomaly import detect_anomalies
from ai.summary import summarize

INTERVAL = int(os.environ.get("AI_INTERVAL", "300"))
HISTORY_HOURS = int(os.environ.get("AI_HISTORY_HOURS", "6"))


def run_once(db):
    rooms = db.rooms()
    if not rooms:
        logging.info("ai worker: no rooms with data yet")
        return
    for room in rooms:
        history = db.history(room, hours=HISTORY_HOURS)
        latest = history[-1] if history else {}
        forecast = forecast_room(history)
        anomalies = detect_anomalies(history)
        summary = summarize(room, latest, forecast, anomalies)
        db.insert_insight(room, forecast, anomalies, summary)
        has_anomaly = any(a.get("anomaly") for a in anomalies.values())
        logging.info(
            "insight written: room=%s forecast=%s anomaly=%s summary=%s",
            room, bool(forecast), has_anomaly, bool(summary),
        )


def main():
    logging.basicConfig(level=logging.INFO)
    db = Database()
    logging.info("AI worker started (interval=%ss, history=%sh)", INTERVAL, HISTORY_HOURS)
    while True:
        try:
            run_once(db)
        except Exception as e:
            logging.error("ai worker cycle failed: %s", e)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
