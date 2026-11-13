"""Optional natural-language summary via a local Ollama model.

Calls a locally running Ollama server (open source, no cost). If Ollama isn't
running, this degrades gracefully to an empty summary so the worker never
depends on it.

    OLLAMA_URL   (default http://localhost:11434)
    OLLAMA_MODEL (default llama3.2:3b)
"""
import logging
import os

import requests

from sensors.models import METRICS, METRIC_META

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")


def _readings_line(latest):
    parts = []
    for m in METRICS:
        v = latest.get(m)
        if v is not None:
            label, unit = METRIC_META[m]
            parts.append(f"{label} {v} {unit}")
    return ", ".join(parts) if parts else "no readings"


def _trends_line(forecast):
    parts = []
    for m in METRICS:
        f = forecast.get(m)
        if f:
            parts.append(f"{METRIC_META[m][0]} {f['trend']}")
    return ", ".join(parts) if parts else "no trend data"


def _anomaly_line(anomalies):
    flagged = [METRIC_META[m][0] for m in METRICS
               if anomalies.get(m) and anomalies[m].get("anomaly")]
    return ", ".join(flagged) if flagged else "none"


def _build_prompt(room, latest, forecast, anomalies):
    return (
        "You are an indoor air-quality assistant. Write a 1-2 sentence summary of "
        "the room's air quality for a non-technical person.\n"
        "Rules: use plain language; do NOT output numbers, scores, or units; do NOT "
        "mention 'anomaly scores' or model internals; if any metric is flagged as "
        "unusual, say so plainly and suggest the obvious action (e.g. ventilate for "
        "high CO2); if nothing is unusual, say the air quality looks normal. Be brief "
        "and factual.\n\n"
        f"Room: {room.replace('_', ' ')}\n"
        f"Current readings: {_readings_line(latest)}\n"
        f"30-minute trend: {_trends_line(forecast)}\n"
        f"Metrics flagged as unusual: {_anomaly_line(anomalies)}\n"
    )


def summarize(room, latest, forecast, anomalies, timeout=30):
    prompt = _build_prompt(room, latest, forecast, anomalies)
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 120},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logging.info("summary: Ollama unavailable (%s); skipping NL summary", e)
        return ""
