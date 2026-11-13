"""Domain model for a home air-quality reading.

A reading is hardware-agnostic: whether it comes from the mock publisher or a
real ESPHome/Zigbee2MQTT device, it arrives as the same JSON payload and is
represented here as a SensorReading.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

# The metrics a reading can carry, in display order.
METRICS = ("co2", "pm25", "voc", "temperature", "humidity")

# Human-readable labels and units for the UI.
METRIC_META = {
    "co2": ("CO₂", "ppm"),
    "pm25": ("PM2.5", "µg/m³"),
    "voc": ("VOC", "index"),
    "temperature": ("Temperature", "°C"),
    "humidity": ("Humidity", "%"),
}


@dataclass
class SensorReading:
    room: str
    timestamp: datetime
    co2: Optional[float] = None
    pm25: Optional[float] = None
    voc: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None

    @classmethod
    def from_payload(cls, payload: dict) -> "SensorReading":
        """Build a reading from an incoming MQTT JSON payload."""
        room = payload.get("room")
        if not room:
            raise ValueError("payload missing required field 'room'")

        ts_raw = payload.get("timestamp")
        if ts_raw:
            timestamp = datetime.fromisoformat(ts_raw)
        else:
            timestamp = datetime.now(timezone.utc)

        def num(key):
            value = payload.get(key)
            return float(value) if value is not None else None

        return cls(
            room=str(room),
            timestamp=timestamp,
            co2=num("co2"),
            pm25=num("pm25"),
            voc=num("voc"),
            temperature=num("temperature"),
            humidity=num("humidity"),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


def classify(metric: str, value) -> str:
    """Classify a metric value as 'good', 'moderate', or 'poor' for the UI.

    Thresholds are rough, standard indoor-air-quality bands; tune later.
    """
    if value is None:
        return "unknown"
    v = float(value)
    if metric == "co2":
        return "good" if v < 800 else "moderate" if v < 1200 else "poor"
    if metric == "pm25":
        return "good" if v < 12 else "moderate" if v < 35 else "poor"
    if metric == "voc":
        return "good" if v < 150 else "moderate" if v < 300 else "poor"
    if metric == "temperature":
        if 20 <= v <= 24:
            return "good"
        if 18 <= v < 20 or 24 < v <= 26:
            return "moderate"
        return "poor"
    if metric == "humidity":
        if 40 <= v <= 60:
            return "good"
        if 30 <= v < 40 or 60 < v <= 70:
            return "moderate"
        return "poor"
    return "unknown"
