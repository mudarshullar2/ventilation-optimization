from SmartSystem.config import load_database_config
from flask import Flask, render_template, request, redirect, url_for
import psycopg2
import joblib
import plotly.graph_objs as go
from SmartSystem.databaseManagement import (
    connect_to_database,
    close_connection,
    get_latest_sensor_data,
)

app = Flask(__name__)

# Datenbankkonfiguration laden
config_file = "./databaseConfig.yaml"
db_config = load_database_config(config_file)

# Vortrainiertes Machine Learning Modell laden
model_file = "/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl"
model = joblib.load(model_file)


@app.route("/")
def index():
    conn = None
    try:
        # Datenbankverbindung herstellen
        conn = connect_to_database()
        cursor = conn.cursor()

        # Aktuellste Sensordaten abrufen
        latest_data = get_latest_sensor_data(cursor)

        if latest_data:
            # Empfehlung mit Machine Learning Modell generieren
            features = [
                [latest_data[1], latest_data[2], latest_data[3], latest_data[4]]
            ]
            prediction = model.predict(features)[0]

            # Empfehlungstext erstellen
            recommendation = (
                "Das KI-System empfiehlt, die Fenster zu öffnen."
                if prediction == 1
                else "Das KI-System empfiehlt, die Fenster zu schließen."
            )

            return render_template(
                "index.html", sensor_data=latest_data, recommendation=recommendation
            )

        else:
            return render_template("index.html", sensor_data=None, recommendation=None)

    except psycopg2.Error as e:
        print("Fehler bei der Verbindung zur PostgreSQL-Datenbank:", e)

    finally:
        if conn:
            close_connection(conn)


@app.route("/plots")
def plots():
    conn = None
    try:
        # Datenbankverbindung herstellen
        conn = connect_to_database()
        cursor = conn.cursor()

        # Aktuellste Sensordaten für Plots abrufen
        sensor_data = get_latest_sensor_data(cursor)

        if sensor_data:
            # Individuelle Plots generieren
            plots = {}
            for index, (label, y_index, title) in enumerate(
                zip(
                    ["temperature", "humidity", "co2_values", "tvoc_values"],
                    range(1, 5),
                    [
                        "Temperature Plot",
                        "Humidity Plot",
                        "CO2 Level Plot",
                        "TVOC Level Plot",
                    ],
                )
            ):
                plots[label] = generate_plot(sensor_data, 0, y_index, title)

            return render_template("plots.html", plots=plots)

        else:
            return "Keine Sensordaten für Plots verfügbar."

    except psycopg2.Error as e:
        print("Fehler bei der Verbindung zur PostgreSQL-Datenbank:", e)

    finally:
        if conn:
            close_connection(conn)


@app.route("/feedback", methods=["POST"])
def feedback():
    conn = None
    try:
        # Datenbankverbindung herstellen
        conn = connect_to_database()
        cursor = conn.cursor()

        # Feedback-Daten aus dem Formular erhalten
        is_correct = int(request.form["is_correct"])

        # Feedback in der Datenbank aktualisieren
        cursor.execute(
            'UPDATE public."SensorData" SET accurate_prediction = %s WHERE "timestamp" = (SELECT MAX("timestamp") FROM public."SensorData");',
            (is_correct,),
        )
        conn.commit()

        # Erfolgsmeldung für das Feedback generieren
        feedback_message = (
            "Vielen Dank! Dein Feedback wird die Genauigkeit des Modells verbessern!"
        )

        return render_template("feedback.html", feedback_message=feedback_message)

    except psycopg2.Error as e:
        print("Fehler beim Aktualisieren des Feedbacks:", e)

    finally:
        if conn:
            close_connection(conn)

    return redirect(url_for("index"))


def generate_plot(data, x_label, y_label, plot_title):
    # Extrahiere x- und y-Daten aus dem übergebenen Daten-Array
    x_data = [
        row[0] for row in data
    ]  # x-Daten sind die ersten Elemente jeder Zeile im Daten-Array
    y_data = [
        row[y_label] for row in data
    ]  # y-Daten sind die Werte unter dem angegebenen y_label in jedem Daten-Eintrag

    # Erstelle eine Linien- und Marker-Darstellung (Trace) für das Plot mit den extrahierten Daten
    trace = go.Scatter(x=x_data, y=y_data, mode="lines+markers", name=y_label)

    # Definiere das Layout des Plots mit Titel, x-Achsenbeschriftung und y-Achsenbeschriftung
    layout = go.Layout(
        title=plot_title,  # Titel des Plots
        xaxis=dict(title=x_label),  # Beschriftung der x-Achse
        yaxis=dict(title=y_label),  # Beschriftung der y-Achse
    )
    # Erstelle die gesamte Figure für den Plot, die den Trace und das definierte Layout enthält
    fig = go.Figure(data=[trace], layout=layout)

    # Konvertiere die Figure in HTML-Code, jedoch ohne das gesamte HTML-Dokument zu generieren
    return fig.to_html(full_html=False)


if __name__ == "__main__":
    app.run(debug=True)
