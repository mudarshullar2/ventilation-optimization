# Optimizing Ventilation Behavior in Educational Facilities

## Overview

This control system is a core part of my thesis and was developed in cooperation with Stadtwerke Potsdam, who provided the sensors. The project is tested in practice at the Schule am Schloss in Potsdam.

The system collects sensor data, analyzes it, and generates predictions. Results are shown through a web interface for interactive use. It is built with Flask for the web interface and MQTT for data collection.

## Features

- Real-time sensor data collection via MQTT.
- Data visualization through a web interface.
- Periodic predictions using pre-trained machine learning models.
- Collection of user feedback on the predictions.

## Installation and Running

### Option 1: Docker

From the `smart_ventilation` directory:

```
docker build --no-cache -t smart_ventilation .
docker run -p 8000:8000 smart_ventilation
```

Then open `http://127.0.0.1:8000` to access the web interface.

### Option 2: Manual

This project was developed with Python 3.10.10; using this version is recommended to avoid compatibility issues.

```
git clone <repository_url>
cd <repository_directory>

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

cd smart_ventilation
pip install -r requirements.txt
python application.py
```

Then open `http://127.0.0.1:5000` to access the web interface.

> **Note:** Before starting, check the session-management configuration in `application.py` (originally documented as commenting out lines 20–22 and enabling line 19, required for correct session handling in the Docker container). Verify these line numbers against the current file, as they may be outdated.

## Configuration

Create an `api_config.yaml` file in the `smart_ventilation` directory with the following structure:

```
READ_API_KEY: ""      # API key for read access
POST_API_KEY: ""      # API key for write access
API_BASE_URL: ""      # Base URL of the API
CONTENT_TYPE: ""      # Content type used for API requests
CLOUD_SERVICE_URL: "" # URL of your cloud service
USERNAME: ""          # Username for cloud service access
PASSWORD: ""          # Password for cloud service access
```

## Models

The `smart_ventilation/models/` directory contains the following pre-trained machine learning models in `.pkl` format, serialized for fast loading at runtime:

- `Logistic_Regression.pkl` — a logistic regression model.
- `Random_Forest.pkl` — a random forest model.

## Endpoints

- `/` — Main dashboard with real-time sensor data.
- `/plots` — Charts of real-time sensor data.
- `/feedback` — Lets users submit feedback on predictions.
- `/thank_you` — Confirmation page shown after feedback submission.
- `/contact` — Contact page.
- `/leaderboard` — Leaderboard based on predicted data.
- `/future_data/<timestamp>` — Returns future data for a given timestamp.
- `/save_analysis_data` — Saves analysis data.
- `/clear_session` — Clears session data.

## Logging

The application logs key events and errors to the console. Ensure logging is configured appropriately via the `logging` module in `application.py`.

## Notes

Ensure all paths in `application.py` and `mqtt_client.py` match your project structure. The application expects sensor data to be published to specific MQTT topics; adjust the topics and data handling in `mqtt_client.py` as needed.

## Troubleshooting

If the application does not start, check the console logs for errors related to missing configuration files, models, or dependencies. Ensure your MQTT broker is running and reachable with the correct credentials.
