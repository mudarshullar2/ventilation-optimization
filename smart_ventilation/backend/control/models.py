"""Domain model for a smart radiator valve (TRV).

Hardware-agnostic: the mock TRV and a real Zigbee TRV (via Zigbee2MQTT) both
publish the same state payload and accept the same set command.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

# Target temperature bounds (°C) accepted from the UI / API.
MIN_TARGET = 5.0
MAX_TARGET = 30.0


@dataclass
class RadiatorState:
    room: str
    timestamp: datetime
    current_temp: Optional[float] = None
    target_temp: Optional[float] = None
    valve: Optional[float] = None      # 0..100 (% open)
    mode: Optional[str] = None         # "heat" | "off"

    @classmethod
    def from_payload(cls, payload: dict) -> "RadiatorState":
        room = payload.get("room")
        if not room:
            raise ValueError("payload missing required field 'room'")
        ts_raw = payload.get("timestamp")
        timestamp = datetime.fromisoformat(ts_raw) if ts_raw else datetime.now(timezone.utc)

        def num(key):
            value = payload.get(key)
            return float(value) if value is not None else None

        return cls(
            room=str(room),
            timestamp=timestamp,
            current_temp=num("current_temp"),
            target_temp=num("target_temp"),
            valve=num("valve"),
            mode=payload.get("mode"),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


def clamp_target(value) -> float:
    """Clamp a requested target temperature into the allowed range."""
    v = float(value)
    return max(MIN_TARGET, min(MAX_TARGET, v))
