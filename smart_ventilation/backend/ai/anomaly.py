"""Per-metric anomaly detection using scikit-learn's IsolationForest.

Flags whether the most recent reading of each metric is anomalous relative to
the room's recent history. Open source, runs locally, no cost.
"""
import numpy as np
from sklearn.ensemble import IsolationForest

from sensors.models import METRICS


def detect_anomalies(history, min_points=20, contamination=0.03):
    """Return {metric: {anomaly: bool, score: float}} for the latest reading."""
    result = {}
    if len(history) < min_points:
        return result

    for metric in METRICS:
        values = [h.get(metric) for h in history if h.get(metric) is not None]
        if len(values) < min_points:
            continue

        x = np.array(values, dtype=float).reshape(-1, 1)
        model = IsolationForest(contamination=contamination, random_state=0)
        model.fit(x)
        latest = x[-1].reshape(1, -1)
        is_anomaly = model.predict(latest)[0] == -1
        score = float(model.score_samples(latest)[0])

        result[metric] = {"anomaly": bool(is_anomaly), "score": round(score, 3)}
    return result
