from SmartSystem.config import load_database_config
from SmartSystem.database_management import (
    connect_to_database,
    get_sensor_data_last_hour,
    get_sensor_data_last_month,
)
from SmartSystem.data_generation import get_latest_sensor_data
from SmartSystem.generating_plots import generate_plot
from flask import Flask, render_template, request, redirect, url_for, send_file
import psycopg2
import joblib
import pandas as pd

app = Flask(__name__)

# Datenbankkonfiguration laden
config_file = "database_config.yaml"
db_config = load_database_config(config_file)

# Das vortrainierte Machine-Learning-Modell laden
model = joblib.load("/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl")


@app.route("/")
def index():
    sensor_data = get_latest_sensor_data()

    if sensor_data:
        # Empfehlung mit Hilfe des Machine-Learning-Modells generieren
        latest_data = sensor_data[
            0
        ]  # Verwendung des neuesten Datenpunkts für die Empfehlung
        features = [[latest_data[1], latest_data[2], latest_data[3], latest_data[4]]]
        prediction = model.predict(features)[0]

        if prediction == 1:
            recommendation = "Das KI-System empfiehlt, die Fenster zu öffnen."
        else:
            recommendation = "Das KI-System empfiehlt, die Fenster zu schließen."

        return render_template(
            "index.html", sensor_data=latest_data, recommendation=recommendation
        )

    else:
        return render_template("index.html", sensor_data=None, recommendation=None)


@app.route("/plots")
def plots():
    sensor_data = get_latest_sensor_data()

    if sensor_data:
        # Individuelle Plots generieren
        temperature_plot = generate_plot(
            sensor_data, 0, 1, "Temperature Plot"
        )  # (timestamp, temperature)
        humidity_plot = generate_plot(
            sensor_data, 0, 2, "Humidity Plot"
        )  # (timestamp, humidity)
        co2_plot = generate_plot(
            sensor_data, 0, 3, "CO2 Level Plot"
        )  # (timestamp, co2_values)
        tvoc_plot = generate_plot(
            sensor_data, 0, 4, "TVOC Level Plot"
        )  # (timestamp, tvoc_values)

        return render_template(
            "plots.html",
            temperature_plot=temperature_plot,
            humidity_plot=humidity_plot,
            co2_plot=co2_plot,
            tvoc_plot=tvoc_plot,
        )

    else:
        return "No sensor data available for plots."


@app.route("/feedback", methods=["POST"])
def feedback():
    """
    Verarbeitet das Feedback, das über ein Formular gesendet wurde.
    :return: Weiterleitung zur Indexseite nach erfolgreicher Verarbeitung des Feedbacks
    """
    is_correct = int(request.form["is_correct"])

    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE public."SensorData" SET accurate_prediction = %s WHERE "timestamp" = (SELECT MAX('
            '"timestamp") FROM public."SensorData");',
            (is_correct,),
        )
        conn.commit()
        conn.close()
        if is_correct == 1:
            feedback_message = (
                "Vielen Dank! Dein Feedback wird die Genauigkeit "
                "des Modells verbessern!"
            )
        else:
            feedback_message = (
                "Vielen Dank! Dein Feedback wird die Genauigkeit "
                "des Modells verbessern!"
            )

        return render_template("feedback.html", feedback_message=feedback_message)

    except psycopg2.Error as e:
        print("Fehler beim Aktualisieren des Feedbacks:", e)

    return redirect(url_for("index"))


@app.route("/download_co2_data", methods=["GET"])
def download_co2_data():
    sensor_data = get_sensor_data_last_hour()
    # sensor_data = get_sensor_data_last_month()

    if sensor_data:
        # Create DataFrame from sensor data
        df = pd.DataFrame(
            sensor_data, columns=["Timestamp", "Temperature", "Humidity", "CO2", "TVOC"]
        )

        # Calculate descriptive statistics
        descriptive_stats = df.describe()

        # Create Excel file
        output_path = "co2_data_last_month.xlsx"
        with pd.ExcelWriter(output_path) as writer:
            df.to_excel(writer, index=False, sheet_name="Sensor Data")
            descriptive_stats.to_excel(writer, sheet_name="Descriptive Statistics")

        # Send Excel file as download
        return send_file(output_path, as_attachment=True)

    else:
        return "No sensor data available for the last month."


if __name__ == "__main__":
    app.run(debug=True)
