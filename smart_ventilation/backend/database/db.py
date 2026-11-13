"""Data access for air-quality readings.

Thin wrapper around a psycopg2 connection with reconnect handling. Writer
(the MQTT client) and readers (the Flask routes) each hold their own Database
instance, since psycopg2 connections are not safe to share across threads.
"""
import logging

from psycopg2.extras import Json

from database.database_connection import load_config, connect_to_database

CONFIG_PATH = "config/db_config.yaml"


class Database:
    def __init__(self, config_path=CONFIG_PATH):
        self.config = load_config(config_path)
        self.conn = connect_to_database(self.config) if self.config else None

    def _ensure(self):
        if self.conn is None or getattr(self.conn, "closed", 1):
            self.conn = connect_to_database(self.config) if self.config else None
        return self.conn is not None

    def insert_reading(self, reading):
        if not self._ensure():
            logging.error("insert_reading: no database connection")
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO readings (ts, room, co2, pm25, voc, temperature, humidity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        reading.timestamp,
                        reading.room,
                        reading.co2,
                        reading.pm25,
                        reading.voc,
                        reading.temperature,
                        reading.humidity,
                    ),
                )
            self.conn.commit()
        except Exception as e:
            logging.error("insert_reading failed: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def latest_per_room(self):
        if not self._ensure():
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (room)
                        room, ts, co2, pm25, voc, temperature, humidity
                    FROM readings
                    ORDER BY room, ts DESC
                    """
                )
                rows = cur.fetchall()
            return [
                {
                    "room": r[0],
                    "timestamp": r[1].isoformat() if r[1] else None,
                    "co2": r[2],
                    "pm25": r[3],
                    "voc": r[4],
                    "temperature": r[5],
                    "humidity": r[6],
                }
                for r in rows
            ]
        except Exception as e:
            logging.error("latest_per_room failed: %s", e)
            return []

    def history(self, room, hours=24):
        if not self._ensure() or not room:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ts, co2, pm25, voc, temperature, humidity
                    FROM readings
                    WHERE room = %s AND ts > now() - make_interval(hours => %s)
                    ORDER BY ts ASC
                    """,
                    (room, hours),
                )
                rows = cur.fetchall()
            return [
                {
                    "ts": r[0].isoformat() if r[0] else None,
                    "co2": r[1],
                    "pm25": r[2],
                    "voc": r[3],
                    "temperature": r[4],
                    "humidity": r[5],
                }
                for r in rows
            ]
        except Exception as e:
            logging.error("history failed: %s", e)
            return []

    def rooms(self):
        if not self._ensure():
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT DISTINCT room FROM readings ORDER BY room")
                return [r[0] for r in cur.fetchall()]
        except Exception as e:
            logging.error("rooms failed: %s", e)
            return []

    def insert_insight(self, room, forecast, anomalies, summary):
        if not self._ensure():
            logging.error("insert_insight: no database connection")
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO insights (room, forecast, anomalies, summary)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (room, Json(forecast), Json(anomalies), summary),
                )
            self.conn.commit()
        except Exception as e:
            logging.error("insert_insight failed: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def latest_insights_per_room(self):
        """Return {room: {generated_at, forecast, anomalies, summary}}."""
        if not self._ensure():
            return {}
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (room)
                        room, generated_at, forecast, anomalies, summary
                    FROM insights
                    ORDER BY room, generated_at DESC
                    """
                )
                rows = cur.fetchall()
            return {
                r[0]: {
                    "generated_at": r[1].isoformat() if r[1] else None,
                    "forecast": r[2] or {},
                    "anomalies": r[3] or {},
                    "summary": r[4] or "",
                }
                for r in rows
            }
        except Exception as e:
            logging.error("latest_insights_per_room failed: %s", e)
            return {}
