"""Short-term per-metric forecasting.

Fits a simple linear trend to each metric's recent history and projects it
`horizon_min` minutes ahead. Deliberately lightweight and robust with few data
points; with real sensor data (which has genuine daily/occupancy structure)
this can later be swapped for a stronger time-series model behind the same
function signature.
"""
from datetime import datetime

import numpy as np

from sensors.models import METRICS

# Per-metric "rising/falling" sensitivity, in units-per-hour.
_TREND_EPS = {
    "co2": 20.0,
    "pm25": 1.0,
    "voc": 10.0,
    "temperature": 0.3,
    "humidity": 1.0,
}


def forecast_room(history, horizon_min=30, min_points=5):
    """Return {metric: {horizon_min, predicted, trend}} for a room's history.

    `history` is a list of dicts (ascending by ts) with an ISO 'ts' and metric keys.
    """
    result = {}
    if len(history) < min_points:
        return result

    for metric in METRICS:
        pairs = [
            (datetime.fromisoformat(h["ts"]), h.get(metric))
            for h in history
            if h.get("ts") and h.get(metric) is not None
        ]
        if len(pairs) < min_points:
            continue

        t0 = pairs[0][0]
        x = np.array([(t - t0).total_seconds() for t, _ in pairs], dtype=float)
        y = np.array([v for _, v in pairs], dtype=float)

        slope, intercept = np.polyfit(x, y, 1)
        horizon_s = x[-1] + horizon_min * 60
        predicted = slope * horizon_s + intercept
        per_hour = slope * 3600

        eps = _TREND_EPS.get(metric, 0.0)
        if per_hour > eps:
            trend = "rising"
        elif per_hour < -eps:
            trend = "falling"
        else:
            trend = "stable"

        result[metric] = {
            "horizon_min": horizon_min,
            "predicted": round(float(predicted), 1),
            "trend": trend,
        }
    return result
